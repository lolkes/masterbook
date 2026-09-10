import csv
import hashlib
import hmac
import io
import json
import os
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, Update

from database import *

VERSION = "8.1"
BASE = Path(__file__).parent
TOKEN = os.getenv("BOT_TOKEN", "").strip()
DEMO = os.getenv("DEMO_MODE", "0") == "1"
PUBLIC_URL = (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "") or (hashlib.sha256(TOKEN.encode()).hexdigest()[:32] if TOKEN else "masterbook-demo")

app = FastAPI(title="MasterBook API", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

dp = Dispatcher()
router = Router()
dp.include_router(router)
bot = Bot(TOKEN) if TOKEN else None

@router.message(CommandStart())
async def start(message: Message):
    if not PUBLIC_URL:
        await message.answer("👋 MasterBook запущен, но адрес Mini App ещё не настроен.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📱 Открыть MasterBook", web_app=WebAppInfo(url=PUBLIC_URL))
    ]])
    await message.answer(
        "👋 <b>Добро пожаловать в MasterBook!</b>\n\n"
        "Учёт клиентов, работ, доходов и расходов — прямо в Telegram.\n\n"
        "Нажмите кнопку ниже, чтобы открыть приложение.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

def auth(data):
    if not data:
        if DEMO:
            return "demo"
        raise HTTPException(401, "Откройте приложение через Telegram")
    if not TOKEN:
        raise HTTPException(500, "BOT_TOKEN не настроен")
    vals = dict(parse_qsl(data, keep_blank_values=True))
    received = vals.pop("hash", "")
    check = "\n".join(f"{k}={vals[k]}" for k in sorted(vals))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received):
        raise HTTPException(401, "Недействительные данные Telegram")
    try:
        age = time.time() - int(vals.get("auth_date", "0"))
    except ValueError:
        age = 10**9
    if age > 86400:
        raise HTTPException(401, "Сессия Telegram устарела")
    try:
        user = json.loads(vals.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(401, "Некорректные данные пользователя Telegram")
    user_id = str(user.get("id") or "")
    if not user_id:
        raise HTTPException(401, "Не удалось определить пользователя Telegram")
    return user_id

def uid(header):
    return auth(header)

def validate_status(status, payment):
    if status not in STATUSES or payment not in PAYMENTS:
        raise HTTPException(400, "Недопустимый статус или способ оплаты")

def valid_date(value: str):
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("Дата должна быть в формате YYYY-MM-DD")
    return value

class Client(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=300)

class Job(BaseModel):
    client_id: int | None = None
    service: str = Field(min_length=1, max_length=200)
    price: float = Field(ge=0)
    expenses: float = Field(default=0, ge=0)
    address: str = Field(default="", max_length=300)
    job_date: str
    comment: str = Field(default="", max_length=1000)
    status: str = "done"
    payment_status: str = "paid"

    @field_validator("job_date")
    @classmethod
    def check_date(cls, v):
        return valid_date(v)

class Expense(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    amount: float = Field(ge=0)
    expense_date: str
    comment: str = Field(default="", max_length=1000)

    @field_validator("expense_date")
    @classmethod
    def check_date(cls, v):
        return valid_date(v)

@app.on_event("startup")
async def startup():
    init_db()
    if bot and PUBLIC_URL:
        await bot.set_webhook(
            url=f"{PUBLIC_URL}{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
        )

@app.on_event("shutdown")
async def shutdown():
    if bot:
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()

@app.middleware("http")
async def version_header(request, call_next):
    response = await call_next(request)
    response.headers["X-MasterBook-Version"] = VERSION
    return response

@app.get("/")
def index():
    return FileResponse(BASE / "web" / "index.html")

@app.get("/style.css")
def css():
    return FileResponse(BASE / "web" / "style.css", media_type="text/css")

@app.get("/app.js")
def js():
    return FileResponse(BASE / "web" / "app.js", media_type="application/javascript")

@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "service": "MasterBook", "telegram": bool(bot), "webhook": bool(bot and PUBLIC_URL)}

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if not bot:
        raise HTTPException(503, "Telegram bot is not configured")
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", WEBHOOK_SECRET):
        raise HTTPException(403, "Invalid webhook secret")
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/api/me")
def me(x_telegram_init_data: str | None = Header(None)):
    return {"user_id": uid(x_telegram_init_data)}

@app.get("/api/stats")
def stats(period: str = "all", x_telegram_init_data: str | None = Header(None)):
    if period not in {"all", "month", "week"}:
        raise HTTPException(400, "Неверный период")
    return get_stats(uid(x_telegram_init_data), period)

@app.get("/api/summary")
def summary(x_telegram_init_data: str | None = Header(None)):
    return get_summary(uid(x_telegram_init_data))

@app.get("/api/clients")
def clients(x_telegram_init_data: str | None = Header(None)):
    return get_clients(uid(x_telegram_init_data))

@app.post("/api/clients")
def add_client(x: Client, x_telegram_init_data: str | None = Header(None)):
    return {"id": create_client(uid(x_telegram_init_data), x.name, x.phone, x.address)}

@app.put("/api/clients/{i}")
def edit_client(i: int, x: Client, x_telegram_init_data: str | None = Header(None)):
    if not update_client(uid(x_telegram_init_data), i, x.name, x.phone, x.address):
        raise HTTPException(404, "Клиент не найден")
    return {"ok": True}

@app.delete("/api/clients/{i}")
def rem_client(i: int, x_telegram_init_data: str | None = Header(None)):
    if not delete_client(uid(x_telegram_init_data), i):
        raise HTTPException(404, "Клиент не найден")
    return {"ok": True}

@app.get("/api/jobs")
def jobs(limit: int = 100, x_telegram_init_data: str | None = Header(None)):
    return get_jobs(uid(x_telegram_init_data), max(1, min(limit, 500)))

@app.post("/api/jobs")
def add_job(x: Job, x_telegram_init_data: str | None = Header(None)):
    u = uid(x_telegram_init_data)
    try:
        validate_client(u, x.client_id)
    except ValueError:
        raise HTTPException(400, "Выбранный клиент недоступен")
    validate_status(x.status, x.payment_status)
    return {"id": create_job(u, x.client_id, x.service, x.price, x.expenses, x.address, x.job_date, x.comment, x.status, x.payment_status)}

@app.put("/api/jobs/{i}")
def edit_job(i: int, x: Job, x_telegram_init_data: str | None = Header(None)):
    u = uid(x_telegram_init_data)
    try:
        validate_client(u, x.client_id)
    except ValueError:
        raise HTTPException(400, "Выбранный клиент недоступен")
    validate_status(x.status, x.payment_status)
    if not update_job(u, i, x.client_id, x.service, x.price, x.expenses, x.address, x.job_date, x.comment, x.status, x.payment_status):
        raise HTTPException(404, "Работа не найдена")
    return {"ok": True}

@app.delete("/api/jobs/{i}")
def rem_job(i: int, x_telegram_init_data: str | None = Header(None)):
    if not delete_job(uid(x_telegram_init_data), i):
        raise HTTPException(404, "Работа не найдена")
    return {"ok": True}

@app.get("/api/expenses")
def expenses(limit: int = 100, x_telegram_init_data: str | None = Header(None)):
    return get_expenses(uid(x_telegram_init_data), max(1, min(limit, 500)))

@app.post("/api/expenses")
def add_expense(x: Expense, x_telegram_init_data: str | None = Header(None)):
    return {"id": create_expense(uid(x_telegram_init_data), x.title, x.amount, x.expense_date, x.comment)}

@app.put("/api/expenses/{i}")
def edit_expense(i: int, x: Expense, x_telegram_init_data: str | None = Header(None)):
    if not update_expense(uid(x_telegram_init_data), i, x.title, x.amount, x.expense_date, x.comment):
        raise HTTPException(404, "Расход не найден")
    return {"ok": True}

@app.delete("/api/expenses/{i}")
def rem_expense(i: int, x_telegram_init_data: str | None = Header(None)):
    if not delete_expense(uid(x_telegram_init_data), i):
        raise HTTPException(404, "Расход не найден")
    return {"ok": True}

@app.get("/api/export")
def export_data(x_telegram_init_data: str | None = Header(None)):
    u = uid(x_telegram_init_data)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Тип", "Дата", "Название/Услуга", "Клиент", "Сумма", "Расходы", "Статус", "Оплата", "Комментарий"])
    for j in get_jobs(u, 5000):
        w.writerow(["Работа", j["job_date"], j["service"], j.get("client_name") or "", j["price"], j["expenses"], j.get("status", "done"), j.get("payment_status", "paid"), j.get("comment", "")])
    for e in get_expenses(u, 5000):
        w.writerow(["Расход", e["expense_date"], e["title"], "", -e["amount"], e["amount"], "", "", e.get("comment") or ""])
    data = io.BytesIO(("\ufeff" + out.getvalue()).encode("utf-8"))
    return StreamingResponse(data, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="masterbook-export.csv"'})

@app.get("/api/backup")
def backup(x_telegram_init_data: str | None = Header(None)):
    return JSONResponse(get_backup(uid(x_telegram_init_data)))

@app.get("/api/version")
def api_version():
    return {"version": VERSION, "features": ["dashboard", "telegram-auth", "per-user-data", "job-status", "payment-status", "search", "csv-export", "json-backup", "crud", "telegram-webhook"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

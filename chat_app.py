import hashlib
import hmac
import secrets
from pathlib import Path

from fastapi import Cookie, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from database import _fetchall, _fetchone, _execute, _insert_id

BASE = Path(__file__).parent
app = FastAPI(title="ChatGo", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
SESSIONS: dict[str, int] = {}
SOCKETS: dict[int, set[WebSocket]] = {}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex()
    return f"{salt}${digest}"


def check_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex()
    return hmac.compare_digest(actual, digest)


def user_from_token(token: str | None) -> dict:
    if not token or token not in SESSIONS:
        raise HTTPException(401, "Требуется вход")
    user = _fetchone("SELECT id, username, display_name, avatar_url, last_seen, created_at FROM chat_users WHERE id=%s", (SESSIONS[token],))
    if not user:
        raise HTTPException(401, "Пользователь не найден")
    return user


def raw_token(token: str | None, authorization: str | None) -> str | None:
    return token or (authorization.removeprefix("Bearer ").strip() if authorization else None)


def touch(user_id: int):
    _execute("UPDATE chat_users SET last_seen=NOW() WHERE id=%s", (user_id,))


class Register(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class Login(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


@app.get("/")
def index(): return FileResponse(BASE / "web" / "chat" / "index.html")

@app.get("/style.css")
def css(): return FileResponse(BASE / "web" / "chat" / "style.css", media_type="text/css")

@app.get("/app.js")
def js(): return FileResponse(BASE / "web" / "chat" / "app.js", media_type="application/javascript")

@app.get("/health")
def health(): return {"status":"ok","service":"ChatGo","version":"1.0"}

@app.post("/api/register")
def register(data: Register):
    username = data.username.lower()
    if _fetchone("SELECT id FROM chat_users WHERE username=%s", (username,)):
        raise HTTPException(409, "Такой логин уже занят")
    display = data.display_name.strip()
    uid = _insert_id("INSERT INTO chat_users(username,display_name,password_hash,last_seen) VALUES (%s,%s,%s,NOW()) RETURNING id", (username, display, hash_password(data.password)))
    token = secrets.token_urlsafe(32); SESSIONS[token] = uid
    return {"token":token,"user":{"id":uid,"username":username,"display_name":display}}

@app.post("/api/login")
def login(data: Login):
    user = _fetchone("SELECT id,username,display_name,avatar_url,password_hash FROM chat_users WHERE username=%s", (data.username.lower(),))
    if not user or not check_password(data.password, user["password_hash"]): raise HTTPException(401,"Неверный логин или пароль")
    touch(user["id"]); token=secrets.token_urlsafe(32); SESSIONS[token]=user["id"]
    return {"token":token,"user":{"id":user["id"],"username":user["username"],"display_name":user["display_name"],"avatar_url":user.get("avatar_url")}}

@app.get("/api/me")
def me(token: str|None=Cookie(default=None), authorization: str|None=Header(default=None)):
    return user_from_token(raw_token(token,authorization))

@app.get("/api/users")
def users(q: str="", token: str|None=Cookie(default=None), authorization: str|None=Header(default=None)):
    me_user=user_from_token(raw_token(token,authorization)); like=f"%{q.strip()}%"
    return _fetchall("SELECT id,username,display_name,avatar_url,last_seen FROM chat_users WHERE id<>%s AND (username ILIKE %s OR display_name ILIKE %s) ORDER BY display_name LIMIT 50", (me_user["id"],like,like))

@app.post("/api/conversations/{other_id}")
def conversation(other_id:int, token:str|None=Cookie(default=None), authorization:str|None=Header(default=None)):
    me_user=user_from_token(raw_token(token,authorization))
    if other_id==me_user["id"] or not _fetchone("SELECT id FROM chat_users WHERE id=%s",(other_id,)): raise HTTPException(404,"Пользователь не найден")
    existing=_fetchone("SELECT c.id FROM chat_conversations c JOIN chat_conversation_members a ON a.conversation_id=c.id JOIN chat_conversation_members b ON b.conversation_id=c.id WHERE a.user_id=%s AND b.user_id=%s LIMIT 1",(me_user["id"],other_id))
    if existing:return {"id":existing["id"]}
    cid=_insert_id("INSERT INTO chat_conversations DEFAULT VALUES RETURNING id")
    _execute("INSERT INTO chat_conversation_members(conversation_id,user_id) VALUES (%s,%s),(%s,%s)",(cid,me_user["id"],cid,other_id))
    return {"id":cid}

@app.get("/api/conversations")
def conversations(token:str|None=Cookie(default=None), authorization:str|None=Header(default=None)):
    me_user=user_from_token(raw_token(token,authorization))
    return _fetchall("""SELECT c.id,u.id AS user_id,u.username,u.display_name,u.avatar_url,
    (SELECT body FROM chat_messages m WHERE m.conversation_id=c.id AND m.deleted_at IS NULL ORDER BY m.created_at DESC LIMIT 1) AS last_message,
    (SELECT created_at FROM chat_messages m WHERE m.conversation_id=c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message_at
    FROM chat_conversations c JOIN chat_conversation_members cm ON cm.conversation_id=c.id AND cm.user_id=%s
    JOIN chat_conversation_members other ON other.conversation_id=c.id AND other.user_id<>%s JOIN chat_users u ON u.id=other.user_id
    ORDER BY COALESCE((SELECT created_at FROM chat_messages m WHERE m.conversation_id=c.id ORDER BY m.created_at DESC LIMIT 1),c.created_at) DESC""",(me_user["id"],me_user["id"]))

@app.get("/api/conversations/{cid}/messages")
def messages(cid:int, limit:int=100, token:str|None=Cookie(default=None), authorization:str|None=Header(default=None)):
    me_user=user_from_token(raw_token(token,authorization))
    if not _fetchone("SELECT 1 FROM chat_conversation_members WHERE conversation_id=%s AND user_id=%s",(cid,me_user["id"])): raise HTTPException(403,"Нет доступа к чату")
    rows=_fetchall("SELECT m.id,m.sender_id,u.display_name AS sender_name,m.body,m.created_at,m.deleted_at FROM chat_messages m JOIN chat_users u ON u.id=m.sender_id WHERE m.conversation_id=%s ORDER BY m.created_at DESC LIMIT %s",(cid,max(1,min(limit,200))))
    return rows[::-1]

async def broadcast(cid:int,payload:dict):
    for ws in list(SOCKETS.get(cid,set())):
        try: await ws.send_json(payload)
        except Exception: SOCKETS.get(cid,set()).discard(ws)

@app.websocket("/ws/{cid}")
async def websocket_chat(websocket:WebSocket,cid:int):
    token=websocket.query_params.get("token")
    if not token or token not in SESSIONS: await websocket.close(code=1008); return
    uid=SESSIONS[token]
    if not _fetchone("SELECT 1 FROM chat_conversation_members WHERE conversation_id=%s AND user_id=%s",(cid,uid)): await websocket.close(code=1008); return
    await websocket.accept(); SOCKETS.setdefault(cid,set()).add(websocket); touch(uid)
    try:
        while True:
            data=await websocket.receive_json(); body=str(data.get("body","")).strip()
            if not body or len(body)>4000: continue
            row=_fetchone("INSERT INTO chat_messages(conversation_id,sender_id,body) VALUES (%s,%s,%s) RETURNING id,conversation_id,sender_id,body,created_at",(cid,uid,body))
            await broadcast(cid,row)
    except WebSocketDisconnect: pass
    finally: SOCKETS.get(cid,set()).discard(websocket); touch(uid)

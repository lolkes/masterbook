import asyncio
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN environment variable.")
if not WEBAPP_URL.startswith("https://"):
    raise RuntimeError("Set WEBAPP_URL to the public HTTPS address of MasterBook.")

bot = Bot(TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(CommandStart())
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📱 Открыть MasterBook", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await message.answer(
        "👋 <b>MasterBook</b>\n\n"
        "Клиенты, работы, расходы и прибыль — в одном месте.\n\n"
        "Нажмите кнопку ниже, чтобы открыть приложение.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

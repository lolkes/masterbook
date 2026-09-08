import os,asyncio
from aiogram import Bot,Dispatcher,Router
from aiogram.filters import CommandStart
from aiogram.types import Message,InlineKeyboardMarkup,InlineKeyboardButton,WebAppInfo
TOKEN=os.getenv('BOT_TOKEN','').strip(); WEBAPP_URL=os.getenv('WEBAPP_URL','').strip()
if not TOKEN: raise RuntimeError('Set BOT_TOKEN environment variable.')
if not WEBAPP_URL: raise RuntimeError('Set WEBAPP_URL environment variable.')
bot=Bot(TOKEN); dp=Dispatcher(); r=Router(); dp.include_router(r)
@r.message(CommandStart())
async def start(m:Message):
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📱 Открыть MasterBook',web_app=WebAppInfo(url=WEBAPP_URL))]])
    await m.answer('👋 <b>Добро пожаловать в MasterBook!</b>\n\nУчёт клиентов, работ, доходов и расходов — прямо в Telegram.\n\nНажмите кнопку ниже, чтобы открыть приложение.',reply_markup=kb,parse_mode='HTML')
async def main(): await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main())

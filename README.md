# MasterBook 7.0

Telegram Mini App для мастеров и небольших сервисных бизнесов.

### Что умеет
- 📊 Дашборд доходов, расходов и чистой прибыли
- 👥 Клиенты с телефоном, адресом и историей работ
- 🔧 Работы: цена, расходы, статус и оплата
- 💸 Отдельный учёт расходов
- 🔎 Поиск по работам, клиентам и расходам
- ✏️ Редактирование и удаление записей
- 📤 CSV-экспорт
- 🔐 Telegram initData и изоляция данных пользователей
- 📱 Mobile-first интерфейс для Telegram

### Render
Build:
`pip install -r requirements.txt`

Start:
`uvicorn app:app --host 0.0.0.0 --port $PORT`

### Переменные окружения
- `BOT_TOKEN` — токен Telegram-бота, хранить только в Render Environment Variables.
- `WEBAPP_URL` — HTTPS-адрес опубликованного Mini App.
- `DEMO_MODE=1` — только для локального демо без Telegram auth.

### Структура
```text
MasterBook/
├── web/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── app.py
├── bot.py
├── database.py
├── requirements.txt
└── README.md
```

### Важно
SQLite подходит для MVP/демо. Для реальных клиентов следующий шаг — PostgreSQL + постоянное хранилище на Render.

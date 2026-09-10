# MasterBook 8.2 — Telegram Mini App для мастеров

MasterBook — рабочий кабинет частного мастера прямо внутри Telegram: клиенты, заказы, расходы и прибыль.

## Что уже работает
- 👤 Клиенты: имя, телефон, адрес, редактирование и удаление.
- 🔧 Работы: услуга, цена, расходы, адрес, дата, статус, оплата и комментарий.
- 💰 Дашборд: доход, расходы, прибыль, количество клиентов и работ.
- 💸 Отдельные расходы.
- 📊 Периоды: всё время / 30 дней / 7 дней.
- 🔎 Поиск по работам, клиентам и расходам.
- 📥 CSV-экспорт.
- 💾 JSON-резервная копия.
- 🔐 Telegram initData HMAC-проверка.
- 👤 Изоляция данных каждого мастера по Telegram user ID.
- 🤖 Telegram-бот встроен прямо в FastAPI-сервис.
- 📱 Кнопка открытия Mini App в сообщении `/start`.
- 📌 Кнопка `MasterBook` в меню Telegram-бота.
- `/start` и `/help`.
- 🔗 Webhook Telegram вместо постоянного polling-процесса.
- 💽 SQLite на постоянном Render Disk для текущего сервиса.

## Как работает сервер
Render запускает только `app.py` как один Web Service.

Внутри него одновременно работают:
1. FastAPI и Mini App.
2. API MasterBook.
3. Telegram Bot API webhook.
4. Telegram-команды `/start` и `/help`.

Поэтому держать компьютер включённым не требуется. Telegram отправляет обновления бота на HTTPS webhook сервера. Это соответствует официальной модели Telegram webhook. 

## Структура
```text
MasterBook/
├── bot.py                 # локальный fallback для тестирования
├── app.py                 # основной сервер + Telegram webhook
├── database.py            # SQLite и данные мастеров
├── requirements.txt
├── render.yaml            # конфигурация Render
├── README.md
└── web/
    ├── index.html
    ├── style.css
    └── app.js
```

## Переменные окружения
- `BOT_TOKEN` — токен бота из BotFather. Хранится только в Render Environment, не в GitHub.
- `DB_PATH` — путь к SQLite. В Render используется `/var/data/masterbook.db`.
- `WEBHOOK_SECRET` — необязательно; если не задан, сервер создаёт детерминированный секрет из токена.
- `PUBLIC_URL` — необязательно. Render сам предоставляет `RENDER_EXTERNAL_URL`, и MasterBook использует его автоматически.
- `DEMO_MODE=1` — только для локального демо без Telegram auth.

## Render
`render.yaml` уже задаёт:
- Python Web Service;
- запуск `uvicorn app:app --host 0.0.0.0 --port $PORT`;
- автоматический deploy из GitHub;
- `/health` как health check;
- постоянный диск для SQLite;
- `BOT_TOKEN` как секрет.

После создания сервиса в Render нужно добавить только `BOT_TOKEN`, если Blueprint не запросит его автоматически.

## Локальный запуск
Для тестирования:
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

`bot.py` оставлен только как отдельный polling-вариант для локальных тестов. На Render его запускать не нужно: там используется webhook внутри `app.py`.

## Следующий этап MasterBook
- 📅 календарь и расписание;
- 🔔 напоминания о заказах;
- 📸 фото заказа;
- 🧾 сметы и PDF;
- 📍 быстрый адрес заказа;
- 💬 шаблоны сообщений клиенту;
- 🔁 повторный заказ;
- 👨‍🔧 профиль мастера;
- ⭐ рейтинг/отзывы;
- 💳 подписка 299/499 ₽;
- 🏪 white-label версия для отдельных мастеров.

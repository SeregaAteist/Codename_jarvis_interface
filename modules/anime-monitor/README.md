# J.A.R.V.I.S. Anime Monitor

Персональный мониторинг аниме: animevost.org + Jikan API + Ollama + Telegram.

## Быстрый старт

### 1. Зависимости
```bash
cd anime_monitor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Ollama (рекомендации локально)
```bash
brew install ollama
ollama serve
ollama pull llama3.2
```

### 3. Telegram Bot
1. Откройте @BotFather в Telegram
2. `/newbot` → получите токен
3. Напишите боту `/start` → узнайте chat_id через @userinfobot

### 4. Конфигурация
```bash
cp .env.example .env
# Заполните TELEGRAM_TOKEN и TELEGRAM_CHAT_ID
```

### 5. Запуск
```bash
python main.py
```

### 6. Mini App в Telegram
1. @BotFather → `/newapp` → укажите URL: `http://ВАШ_IP:8000`
2. Для доступа с iPhone используйте ngrok:
```bash
brew install ngrok
ngrok http 8000
# Скопируйте https://xxx.ngrok.io в BotFather
```

## Команды бота (кнопки)
| Кнопка | Действие |
|--------|----------|
| 📋 Список | Ваш вотчлист с inline-кнопками |
| 🆕 Новинки | Последние обновления серий |
| 🤖 Рекомендации | Ollama анализирует вотчлист |
| 🔍 Скан | Ручной запуск сканирования |
| ➕ Добавить | Добавить тайтл в вотчлист |
| ➖ Убрать | Удалить из вотчлиста |

## Структура
```
anime_monitor/
├── config.py           — конфигурация
├── main.py             — точка входа
├── agents/
│   ├── db_agent.py     — SQLite
│   ├── scraper_agent.py — парсинг animevost.org
│   ├── jikan_agent.py  — метаданные MAL
│   ├── notify_agent.py — Telegram уведомления
│   └── recommend_agent.py — Ollama рекомендации
├── bot/
│   ├── telegram_bot.py — бот с кнопками
│   └── mini_app/
│       └── index.html  — HUD интерфейс
├── api/
│   └── server.py       — FastAPI
└── data/
    └── anime.db        — SQLite БД
```

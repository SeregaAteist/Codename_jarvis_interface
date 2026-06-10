# J.A.R.V.I.S. Media Analyzer

Telegram-бот для анализа медиаконтента (видео, фото, голосовые) через whisper.cpp + Claude Vision.
Часть системы J.A.R.V.I.S. HUD OS.

## Назначение

Мониторит тему "📥 Медиа" в Telegram-группе. Собирает медиафайлы батчами (30 сек),
транскрибирует через whisper.cpp, анализирует через Claude API, предлагает: приступить / отложить / игнорировать.

## Стек

- Python 3.11 (`/opt/homebrew/bin/python3.11`)
- python-telegram-bot 21.3 (async polling)
- anthropic SDK (AsyncAnthropic)
- whisper.cpp (C++ бинарь, subprocess)
- SQLite (deferred_pool)
- ffmpeg (извлечение аудио из видео)

## Структура файлов

```
media_analyzer/
├── main.py              — точка входа, запуск polling
├── config.py            — загрузка .env, пути, константы
├── .env                 — секреты (не коммитить)
├── .env.example         — шаблон с пояснениями
├── requirements.txt
├── agents/
│   ├── transcriber.py   — extract_audio() + transcribe() через whisper.cpp subprocess
│   ├── analyzer.py      — analyze_media() + generate_implementation() через Claude API
│   └── db_agent.py      — init_db(), save_deferred(), get_deferred_list()
├── bot/
│   └── telegram_bot.py  — handle_media, handle_callback, build_app, батч-логика
├── tmp/                 — скачанные медиафайлы (авто-удаление после обработки)
└── data/
    └── deferred.db      — SQLite база
```

## Переменные окружения (.env)

| Переменная       | Описание                                                         |
|------------------|------------------------------------------------------------------|
| TELEGRAM_TOKEN   | Токен бота от @BotFather                                         |
| TELEGRAM_CHAT_ID | ID супергруппы (отрицательное число)                             |
| TOPIC_ID         | ID темы "📥 Медиа" (message_thread_id)                           |
| ANTHROPIC_API_KEY| Ключ Anthropic API                                               |
| WHISPER_BIN      | Путь к бинарю whisper.cpp (default: ~/jarvis/voice/main)         |
| WHISPER_MODEL    | Путь к модели ggml-base.bin (default: ~/jarvis/voice/models/...) |

## Установка и запуск

```bash
cd ~/jarvis/modules/media_analyzer

# Установить зависимости
/opt/homebrew/bin/pip3.11 install -r requirements.txt

# Заполнить .env
nano .env

# Запустить
/opt/homebrew/bin/python3.11 main.py
```

## Настройка whisper.cpp

Если бинарь ещё не скомпилирован:
```bash
cd ~/jarvis/voice
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make
# Скачать модель base
bash ./models/download-ggml-model.sh base
# Скопировать в нужные места
cp main ~/jarvis/voice/main
cp models/ggml-base.bin ~/jarvis/voice/models/ggml-base.bin
```

## Получение TOPIC_ID

1. Правой кнопкой по теме "📥 Медиа" → Copy Link
2. Ссылка вида `https://t.me/c/1234567890/123` → последнее число (123) = TOPIC_ID
3. Или: переслать сообщение из темы боту @userinfobot — он покажет message_thread_id

## Логика батчинга

- Первый медиафайл → запускает 30-секундный таймер
- Последующие файлы в течение 30 сек → добавляются в тот же батч
- После 30 сек → весь батч обрабатывается вместе одним запросом к Claude

## Схема SQLite (deferred_pool)

```sql
CREATE TABLE deferred_pool (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,       -- первые 80 символов транскрипции
    analysis   TEXT NOT NULL,       -- полный анализ от Claude
    media_path TEXT,                -- путь к первому медиафайлу (может устареть)
    created_at TEXT NOT NULL        -- ISO 8601
);
```

## Claude модель

`claude-sonnet-4-20250514` — задана в `config.py::CLAUDE_MODEL`

## Важные ограничения

- Telegram: максимальный размер скачиваемого файла через Bot API = 20 MB
- Claude Vision: изображения > 4 MB пропускаются (логируются)
- Telegram сообщение: максимум 4096 символов (длинные ответы разбиваются на чанки)
- callback_data: максимум 64 байта → используем `s:`, `d:`, `x:` + 32-символьный hex-ключ = 34 байта

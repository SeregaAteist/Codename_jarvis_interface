# J.A.R.V.I.S.
Personal Agentic AI OS — MacBook Air M2 (Iron Man style)

## Architecture

```
jarvis/
├── core/              # Reasoning Core, Intent, Memory, Event Bus
├── hud/               # Electron + Vite/React HUD (port 3000)
│   └── backend/       # FastAPI backend (port 7734)
├── agents/            # Specialist agents (voice, browser, game, system)
├── modules/
│   ├── rafail/        # Корпоративная БЗ LK Energy + Telegram бот
│   ├── anime-monitor/ # Anime tracker + Telegram бот
│   ├── kommo/         # Kommo CRM client + задачи реанимации
│   └── ringostat/     # Webhook-обработчик звонков
├── mcp/               # MCP сервер (port 7735)
├── shared/            # Config, LLM router, errors, models
├── automation/        # n8n workflows
└── data/              # ChromaDB, SQLite (gitignored)
```

## Active Services (launchd)

| Label | Schedule | Description |
|---|---|---|
| com.jarvis.tg-media-analyzer | KeepAlive | Основной Telegram бот (media + work) |
| com.jarvis.rafail-bot | KeepAlive | Рафаил — управление БЗ через топик 205 |
| com.jarvis.anime-monitor | KeepAlive | Anime tracker бот |
| com.jarvis.ringostat | KeepAlive | Ringostat webhook сервер |
| com.jarvis.morning-briefing | 08:00 ежедневно | Утренний брифинг в TG |
| com.jarvis.rafail-cron | каждые 6ч | Сбор материалов для Рафаила |
| com.jarvis.kommo-reactivation | пн 09:00 | Реанимация старых сделок Kommo |
| com.jarvis.sqlite-backup | по расписанию | Резервное копирование БД |
| com.jarvis.task-watcher | KeepAlive | Фоновый task watcher |
| com.jarvis.work-bot | KeepAlive | Work бот (work-related commands) |

```bash
# Управление сервисами
launchctl load ~/Library/LaunchAgents/com.jarvis.<name>.plist
launchctl unload ~/Library/LaunchAgents/com.jarvis.<name>.plist
launchctl list | grep jarvis
```

## Quick Start

```bash
# HUD
cd hud && npm install && npm run dev

# Anime monitor
cd modules/anime-monitor && source venv/bin/activate && python main.py

# Рафаил бот
/opt/homebrew/bin/python3.11 -m modules.rafail.bot.rafail_bot

# Тесты
/opt/homebrew/bin/python3.11 -m pytest tests/ -v
```

## Как добавить новый профиль компании (Рафаил)

1. В Telegram, топик 205: `створи профіль: Назва компанії, напрямок`
2. Или программно:
```python
from modules.rafail.core.profile_manager import get_profile_manager
pm = get_profile_manager()
profile = pm.create("profile_id", "Назва компанії", "напрямок")
```
3. Файл создаётся в `data/rafail/profiles/<profile_id>/`

## Как добавить новый RSS-источник (Рафаил)

```sql
-- В rafail.db, таблица sources
INSERT INTO sources (name, url, type, domain, enabled)
VALUES ('Назва', 'https://example.com/feed.xml', 'rss', 'solar', 1);
```

## Как добавить нового менеджера в ringostat.yaml

```yaml
# modules/ringostat/ringostat.yaml
managers:
  "380931234567":
    name: "Іваненко Петро"
    kommo_user_id: 12345
    telegram_id: 987654321
```

## Команды Telegram ботов

### Рафаил (топик 205)
| Команда | Действие |
|---|---|
| `покажи реєстр обладнання` | Список всего оборудования |
| `знайди мануал Deye SUN-10K` | WebResearcher ищет PDF |
| `покажи скрипти по запереченню дорого` | Лучшие скрипты |
| `статистика скриптів` | Рейтинги всех скриптов |
| `переключись на профіль solar` | Сменить профиль компании |
| `створи профіль: Назва, напрямок` | Создать профиль |
| `збери матеріали` | Запустить сбор из всех источников |
| `обробити 10 матеріалів` | Обработать N материалов через LLM |
| `покажи pending` | Очередь на одобрение |
| `одобри всі` | Одобрить все pending материалы |
| `статистика` | Общая статистика БЗ |
| `що нового в СЕС?` | Последние собранные материалы |

### Anime бот (топик 7)
| Команда | Действие |
|---|---|
| `добавь Слизь в список` | Добавить в вотчлист |
| `отметь Берсерк как просмотрено` | Изменить статус |
| `що виходить цього тижня?` | Текущий сезон из Jikan |
| `знайди Hunter x Hunter` | Поиск через Jikan API |
| `що нового вийшло?` | Последние новинки из каталога |

## Runtime

- Python: `/opt/homebrew/bin/python3.11` (НЕ Anaconda 3.13)
- Ollama: `localhost:11434` (model: llama3.2)
- Groq: 14,400 req/day free tier

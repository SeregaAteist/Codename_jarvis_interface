# JARVIS — Полный аудит проекта

**Дата:** 2026-06-10
**Аудитор:** Claude Code (анализ без изменения кода)
**Объём:** все исходники, кроме `node_modules`, `.git`, `venv`, `dist`, `__pycache__`, `tmp`
**Файлов Python проверено:** ~110 (синтаксис — 0 ошибок компиляции)

---

## TL;DR — критичное

| # | Категория | Находка | Серьёзность |
|---|-----------|---------|-------------|
| 1 | Безопасность | Telegram-бот выполняет **произвольный код** через `claude --dangerously-skip-permissions` из любого чата (проверка chat_id отключается при `=0`) | 🔴 CRITICAL |
| 2 | Ошибка | Кнопка «Одобрить» в task-боте не работает — несовпадение `callback_data` (`approve:`) и паттерна хендлера (`^(exec\|cancel):`) | 🔴 BUG |
| 3 | Безопасность | Аллоулист команд в `mac_control` пропускает интерпретаторы (`osascript`, `python3`, `pip`, `brew`) → обход песочницы | 🟠 HIGH |
| 4 | Архитектура | Полное дублирование дерева: `core/`+`agents/` (новое) ↔ `hud/system/`+`hud/system/agents/` (старое), ~30 почти идентичных файлов | 🟠 HIGH |
| 5 | Приватность | `hud/data/memory.json`, `preferences.json`, кэш-файл с запросом — **закоммичены в git** (личные данные) | 🟠 HIGH |
| 6 | Мёртвый код | Плагины регистрируются, но `plugin_manager.handle()` не вызывается нигде — диспетчеризация плагинов мертва | 🟡 MED |
| 7 | Мёртвый код | `BaseAgent` (abstract) не наследуется ни одним агентом; `pool/`, `claude_connector/` не импортируются нигде | 🟡 MED |
| 8 | Архитектура | `docs/`, `shared/`, `mcp/*`, `infra/`, `automation/cron`, `automation/workflows` — пустые заглушки. `docs/ARCHITECTURE.md` не существует | 🟡 MED |
| 9 | Несоответствие | Все пути захардкожены на `~/jarvis`, тогда как репозиторий в `~/Projects/jarvis` | 🟡 MED |

---

## 1. БЕЗОПАСНОСТЬ

### 1.1 🔴 CRITICAL — Удалённое выполнение кода через Telegram task-бот
**Файлы:**
- `modules/tg-media-analyzer/bot/task_handler.py:26-79` (`handle_manual_task`)
- `modules/tg-media-analyzer/executor/ssh_executor.py:41-64`
- `automation/scripts/task_watcher.sh:15-22`
- `modules/tg-media-analyzer/config.py:18`

**Цепочка:** любое текстовое сообщение в Telegram → `build_task()` оборачивает его в промпт → `execute_task()` пишет файл в `tasks/pending/` → `task_watcher.sh` запускает:
```bash
"$CLAUDE" --model claude-fable-5 --dangerously-skip-permissions --print "$(cat "$task_file")"
```
→ результат + **автоматический `git add -A && git commit`** (`task_handler.py:133-142`).

**Что не так:**
- `--dangerously-skip-permissions` даёт Claude Code полный доступ к ФС/shell без подтверждений.
- Источник задачи — текст из Telegram, т.е. фактически RCE для любого, кто пишет в чат.
- Проверка отправителя: `config.py:18` `TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))`. В `.env` `TELEGRAM_CHAT_ID` **пустой** → `0`. В хендлере (`task_handler.py:31`, `handlers.py:145`) условие `if config.TELEGRAM_CHAT_ID and ...` при `0` пропускается → **проверка чата отключена, принимаются сообщения откуда угодно**.
- Кнопка одобрения сломана (см. 2.1), но `handle_manual_task` всё равно генерирует план через `get_plan()` без подтверждения.

**Как исправить:**
- Сделать `TELEGRAM_CHAT_ID` **обязательным**; при отсутствии — отказывать в обслуживании, а не открывать всем.
- Убрать `--dangerously-skip-permissions` или запускать watcher в изолированном контейнере/пользователе с whitelisted-командами.
- Не делать авто-`git commit` от имени бота; требовать ручного подтверждения с проверкой `from_user.id` против явного allowlist.

### 1.2 🟠 HIGH — Аллоулист `execute_terminal_command` пропускает интерпретаторы
**Файл:** `agents/mac_control.py:11-17, 87-143` (и копия `hud/system/mac_control.py`)

`_CMD_ALLOWLIST` содержит `osascript`, `python3`, `python`, `pip`, `pip3`, `brew`. Даже с `shell=False` и `shlex.split` это даёт обход:
```
osascript -e 'do shell script "rm -rf ~"'
python3 -c "import os; os.system('...')"
```
`_BLOCK_PAT` (строки 20-24) ловит `rm -rf`, `sudo`, `curl|bash` и т.п. как подстроки, но не покрывает аргументы внутри `osascript -e`/`python3 -c`.

Достижимо через `POST /mac {action:"terminal", params:{cmd:..., confirm:false}}` (`core/main.py:590-594`). По умолчанию `confirm=True` (возвращает `CONFIRM_REQUIRED`), но клиент может передать `confirm:false`.

**Как исправить:** убрать интерпретаторы и пакетные менеджеры из аллоулиста; либо запретить аргументы `-e`/`-c`/`--eval`; рассматривать аллоулист как «только полностью предопределённые команды без свободных аргументов».

### 1.3 ✅ shell=True / инъекции — не найдено
- `grep shell=True` по `*.py` — **0 совпадений**.
- Все `subprocess.run/Popen/create_subprocess_exec` используют список аргументов (`shell=False`).
- `mac_control.run_applescript`/`_as_str` корректно экранируют AppleScript-строки; `_safe_name` валидирует имена приложений regex-аллоулистом.
- `TerminalAgent._run` (`agents/terminal.py:41`) — только предопределённые списки аргументов.

### 1.4 Секреты
- ✅ Хардкод ключей не найден (grep по api_key/token/secret/sk-/ghp_ — только `os.getenv`/`process.env`/`.env.example` плейсхолдеры).
- ✅ `.env` и любые `.env` в подкаталогах git-игнорируются (`.gitignore: .env`); в трекинге только `*.env.example`.
- ✅ Токены HTTP-API: `core/main.py:60` `secrets.token_urlsafe(32)`, Electron `randomUUID()` (`hud/electron/main.js:13`) — в памяти, не на диске; сравнение через `secrets.compare_digest` (`main.py:287,293`). Лог намеренно не пишет тело запросов (`main.py:277-279`).
- ⚠️ `ssh_executor.py:9-13` и `config.py:54-55` — захардкожены IP (`100.84.234.120`, Tailscale), пользователь, путь к приватному ключу. Не секрет сам по себе, но инфраструктура зашита в код.

### 1.5 Прочее
- ✅ CORS ограничен localhost (`core/main.py:267-272, 305-307`) — фолбэк на `http://localhost:7734`.
- ✅ Rate limiting на все эндпоинты (`main.py:71-81`), лимит размера тела (`_MAX_BODY=8192`), очистка управляющих символов и обрезка длины (`_clean`, `_MAX_TEXT=2000`).
- ⚠️ `electron/main.js:84` `webSecurity: false` и `sandbox: false` — осознанно (file://→localhost), но ослабляет защиту рендерера; задокументировано в комментарии.
- ⚠️ SSRF-поверхность: `agents/browser.py fetch_page/open_url_in_browser` принимают произвольный URL без фильтрации внутренних адресов. Для персонального инструмента риск низкий, но стоит запретить `localhost`/private-ranges.

---

## 2. ОШИБКИ И КОНФЛИКТЫ

### 2.1 🔴 BUG — Сломана кнопка «Одобрить» в task-боте
**Файлы:** `modules/tg-media-analyzer/main.py:41` ↔ `bot/task_handler.py:17, 102`

- `approve_keyboard()` создаёт кнопки с `callback_data="approve:{key}"` и `"cancel:{key}"` (`task_handler.py:17-18`).
- Хендлер зарегистрирован с паттерном `pattern=r"^(exec|cancel):"` (`main.py:41`).
- `approve:` **не матчит** `^(exec|cancel):` → нажатие «Одобрить» ничего не делает. `handle_task_callback` при этом ждёт `action == "approve"` (`task_handler.py:102`), который никогда не приходит из зарегистрированного паттерна.

**Как исправить:** привести в соответствие — заменить паттерн на `r"^(approve|cancel):"` в `main.py:41`.

### 2.2 ⚠️ Перекрытие text-хендлеров в task-боте
**Файл:** `modules/tg-media-analyzer/main.py:34-37`

Два `MessageHandler` в группе 0:
- `filters.TEXT & filters.Entity("url")` → `handle_url`
- `filters.TEXT & ~filters.COMMAND` → `handle_manual_task`

В PTB в одной группе срабатывает только первый подходящий. Любой нетекст-URL идёт в `handle_manual_task` (генерация Claude-задачи). То есть **обычная переписка в чате превращается в задачи для Claude Code** (усугубляет 1.1). Нужно ограничить `handle_manual_task` строго топиком задач через фильтр, а не только проверкой внутри функции.

### 2.3 Дубли логики core/ ↔ hud/system/
**Сравнение деревьев:**

Идентичные (байт-в-байт): `cache.py`, `memory.py`, `monitor.py`, `preferences.py`, `core/reasoning.py`↔`hud/system/core.py`, `core/security.py`↔`hud/system/security_log.py`, `plugin_registry.py`↔`plugin_manager.py`, агенты `base/claude/gemini/groq/morning/rss/terminal/wot/xai`.

Отличаются **только строкой импорта** (`from core.*` ↔ `from system.*`): `personality.py`, `proactive.py`, `router.py`, `agents/browser.py`, `ollama.py`, `weather.py`, `mac_control.py`, `main.py`.

**Вывод:** последний коммit `feat: restructure project` создал новое плоское дерево (`core/`, `agents/`, `connectors/`, `pool/`), но **не удалил** старое (`hud/system/`, `hud/system/agents/`, `hud/voice` как источник). Сейчас существуют два параллельных рантайма:
- `core/main.py` → `core.*` / `agents.*` / `connectors.voice` (который проксирует в `hud/voice`).
- `hud/main.py` → `system.*` / `voice.*`.

Electron (`hud/electron/main.js:61`) запускает `~/jarvis/main.py` — то есть какой именно из двух исполняется, зависит от того, куда указывает `~/jarvis`. Это источник будущих рассинхронов: правка в одном дереве не попадает в другое.

**Как исправить:** выбрать одно дерево (судя по коммиту — верхнеуровневое `core/`+`agents/`), удалить `hud/system/`, `hud/system/agents/`; оставить в `hud/` только UI/electron/voice. `connectors/voice.py` уже проксирует в `hud/voice` — оставить voice там.

### 2.4 Sync/async контракт — `BaseAgent` не соблюдается
**Файл:** `agents/base.py` (+ копия)

`BaseAgent.execute()` — `@abstractmethod async`, есть машинерия `run()` с таймаутами/ретраями. Но **ни один агент не наследует `BaseAgent`** (`grep "(BaseAgent)"` — 0). Все агенты — обычные классы с синхронным `ask()`. Router вызывает синхронный `.ask()` (`core/router.py:111-155`). То есть заявленный async-контракт и retry-обвязка не используются вовсе (см. также 3).

### 2.5 Зависимость core от hud
`connectors/voice.py:5-10` вставляет `hud/` в `sys.path` и импортирует `voice.*`. «Новое» дерево `core/` не самодостаточно — тянет `hud/voice`. При удалении/переносе `hud/` сломается core.

### 2.6 Несоответствие путей рантайма
Все модули используют `os.path.expanduser("~/jarvis/...")` (`core/memory.py:8`, `cache.py:8`, `security.py:7`, `plugin_registry.py:8`, `preferences.py`, `main.py:363/517`), а репозиторий — `~/Projects/jarvis`. Данные (`memory.json`, кэш, логи, плагины) пишутся в `~/jarvis/...`, а не в `data/` репозитория. Если `~/jarvis` — отдельная копия/симлинк, правки кода и данные живут в разных местах.

---

## 3. МЁРТВЫЙ КОД И РУДИМЕНТЫ

| Что | Файл | Подтверждение |
|-----|------|---------------|
| `plugin_manager.handle()` / `find_handler()` не вызываются | `core/plugin_registry.py:59-79` | `grep` call-sites — 0. Плагины только регистрируются (`_register_builtins`), листятся и тоглятся через API, но **не диспетчеризуются** в пайплайне запроса |
| `Router.get_best_agent()` | `core/router.py:86-98` | не вызывается нигде |
| `WotAgent` | `agents/wot.py`, экспорт в `agents/__init__.py:11,16` | в `core/main.py:181` `wot=None`, в `ReasoningCore._INTENTS` нет интента `wot`, `route_intent` его не маршрутизирует → агент недостижим |
| `BaseAgent` весь класс + `run()`/`handle_error()` | `agents/base.py` | нет наследников (2.4) |
| `pool/manager.py` (`APIPool`, singleton `pool`) | `pool/manager.py:181` | `grep "from pool"` ссылается только на `modules/tg-media-analyzer/pool/api_pool.py` (другой класс `SimplePool`). Верхнеуровневый `pool.manager` не импортируется нигде, но при импорте **создаёт sqlite-БД** |
| `claude_connector/selector.py` (`ClaudeSelector`, singleton) | весь файл | не импортируется нигде; дублирует логику `agents/claude.py`; использует устаревшую модель `claude-sonnet-4-20250514` |
| Дублирующее дерево `hud/system/**` | ~30 файлов | см. 2.3 |
| Дублирующий модуль `hud/modules/media_analyzer/` | весь каталог | старая параллельная копия `modules/tg-media-analyzer/` (другая структура: `agents/` vs `analyzers/`, нет url_downloader/executor/task_builder) |
| `Cache memory_cache` | `core/cache.py:83` | определён, но не используется (memory.py ведёт собственный TTL-кэш) |
| Пустые каталоги-заглушки | `docs/{agents,api,architecture}`, `shared/{config,constants,types,utils}`, `mcp/{animevost,calendar,telegram}/__init__.py` (0 строк), `mcp/system/`, `infra/{docker,scripts}`, `automation/{cron,workflows}` | физически пустые |

Рудименты в комментариях: `Router.route()` помечен «Legacy shim» (`core/router.py:162-164`) — вызывается? `grep .route(` показывает только определения; вероятно не используется (пайплайн идёт через `route_intent`).

---

## 4. АРХИТЕКТУРА

### 4.1 docs/ARCHITECTURE.md — отсутствует
Задание требует сверки с `docs/ARCHITECTURE.md`, но файла нет — весь `docs/` пуст. Сверять не с чем. Единственный источник «архитектуры» — `CLAUDE.md`.

### 4.2 Соответствие CLAUDE.md (DIRECTORY MAP) факту

| Заявлено в CLAUDE.md | Факт |
|----------------------|------|
| `core/` — Reasoning Core | ✅ есть и реализован (`reasoning.py`, `router.py`) |
| `hud/` — Electron + UI | ✅ есть (`electron/`, `ui/hud.html`, `main.py` backend) |
| `agents/` — спец-агенты (reasoning_core, intent_analysis, task_decomposition, voice_engine, system_ctl, data_scout, web_agent, browser_agent, game_ctl, memory_agent) | ⚠️ структура **другая**: плоские файлы (`claude.py`, `ollama.py`, `browser.py`, ...). Подкаталоги `agents/{reasoning,intent,task,voice,system,memory,browser}/` существуют, но содержат только пустые `__init__.py`. Заявленных специализированных агентов нет |
| `modules/anime-monitor/` | ⚠️ есть `modules/anime-monitor/` **и** `modules/tg-media-analyzer/` (в карте не указан) |
| `mcp/` — MCP server (порт 7735) | ❌ заглушка: все `__init__.py` пустые, сервера нет. CLAUDE.md «ACTIVE PORTS: MCP 7735 ✅ Active» — **не соответствует** |
| `shared/` — BaseAgent, utils | ❌ пусто. CLAUDE.md сам помечает «BaseAgent class in shared/ (not yet implemented — BLOCKER)». Фактически BaseAgent в `agents/base.py`, но не используется |
| `automation/` — n8n workflows | ⚠️ `cron/` и `workflows/` пусты; есть только `scripts/task_watcher.sh` |
| `infra/` — Docker | ❌ пусто |

### 4.3 Что реально работает (по коду)
- **HTTP/SSE backend** (`core/main.py` / `hud/main.py`): auth-токен, rate-limit, `/ask`, `/speak`, `/mac`, `/browse`, `/monitor`, `/agents/status`, SSE `/events`. Реализовано.
- **ReasoningCore + Router**: regex-классификация интентов → агенты (morning/mac/terminal/ollama/weather/news/memory/search/price/monitor/general с фолбэком ollama→groq→xai→gemini→claude). Реализовано.
- **Агенты**: Ollama, Groq, Gemini, xAI, Claude (SDK+CLI), Browser (DuckDuckGo+wttr), Weather, RSS, Morning, Terminal, mac_control. Реализованы.
- **SystemMonitor** (`core/monitor.py`): psutil + powermetrics, голосовые алерты. Реализовано.
- **Память/преференсы/кэш**: JSON-файлы с TTL-кэшем. Реализовано.
- **tg-media-analyzer**: Telegram-бот, скачивание (yt-dlp), кадры/транскрипция (ffmpeg/whisper), Gemini-анализ, пул ключей. Реализовано (но см. баги 1.1/2.1/2.2).

### 4.4 Что заглушка / дублируется
- Заглушки: `mcp/*`, `shared/*`, `infra/*`, `docs/*`, `automation/{cron,workflows}`, подкаталоги `agents/*/` и `core/{bus,intent,memory,reasoning}/` (пустые `__init__`).
- Дубли: `core/` ↔ `hud/system/`; `modules/tg-media-analyzer` ↔ `hud/modules/media_analyzer`; `pool/manager.py`(APIPool) ↔ `modules/.../pool/api_pool.py`(SimplePool); `claude_connector` ↔ `agents/claude.py`.

### 4.5 Несоответствия моделей
- `agents/claude.py:19` дефолт `claude-haiku-4-5-20251001`; `config.yaml:30` тоже.
- `modules/tg-media-analyzer/config.py:46` `CLAUDE_MODEL = "claude-sonnet-4-20250514"` (старый id, не используется в коде модуля — Claude вызывается через watcher CLI).
- `claude_connector/selector.py:43` `claude-sonnet-4-20250514` (мёртвый код).
- `task_watcher.sh:18` `--model claude-fable-5`.

Рекомендация: централизовать id моделей (один конфиг), убрать устаревшие.

---

## 5. ПРИВАТНОСТЬ / GIT-ГИГИЕНА

**Закоммичены в git личные/сгенерированные данные:**
- `hud/data/memory.json` — история взаимодействий.
- `hud/data/preferences.json` — выученные факты о пользователе.
- `hud/data/cache/search_квантовые компьютеры?….json` — кэш поискового запроса.
- `modules/anime-monitor/data/anime.db` — БД.

Причина: `.gitignore` игнорирует `data/...` только в корне (`data/chroma/`, `data/sqlite/`, `data/logs/`, `data/cache/`), но не `hud/data/`.

**Как исправить:**
```
git rm --cached hud/data/memory.json hud/data/preferences.json
git rm -r --cached "hud/data/cache" modules/anime-monitor/data
```
и добавить в `.gitignore`: `hud/data/`, `**/data/`, `*.db`.

---

## Сводный список действий (приоритет)

1. **🔴 Закрыть RCE через Telegram** (1.1): обязательный `TELEGRAM_CHAT_ID` + allowlist `from_user.id`; убрать `--dangerously-skip-permissions`; убрать авто-commit.
2. **🔴 Починить паттерн callback** (2.1): `^(approve|cancel):` в `tg-media-analyzer/main.py:41`.
3. **🟠 Ограничить text-хендлер** задач топиком (2.2).
4. **🟠 Вычистить аллоулист** интерпретаторов в `mac_control` (1.2).
5. **🟠 Удалить дубль-дерево** `hud/system/**` и `hud/modules/media_analyzer` (2.3); выбрать `core/`+`agents/`.
6. **🟠 Убрать личные данные из git** (раздел 5).
7. **🟡 Удалить мёртвый код**: `pool/manager.py`, `claude_connector/`, `BaseAgent` (или внедрить), `WotAgent` (или подключить), `get_best_agent`, неиспользуемый `Router.route()`.
8. **🟡 Подключить или удалить** систему плагинов (`plugin_manager.handle` нигде не вызывается) — добавить вызов в `ReasoningCore.process()` либо удалить.
9. **🟡 Привести пути** к репозиторию (`~/jarvis` → конфигурируемый `ROOT`) — раздел 2.6.
10. **🟡 Создать `docs/ARCHITECTURE.md`** и синхронизировать `CLAUDE.md` (порты MCP/shared/infra помечены активными, но пусты).
</content>
</invoke>

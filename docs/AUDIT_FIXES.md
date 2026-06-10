# JARVIS — Отчёт об исправлениях аудита

**Дата:** 2026-06-10
**Ветка:** `audit-fixes` (5 коммитов поверх `main`)
**Основа:** `docs/AUDIT_REPORT.md`
**Финальная проверка:** `python3 -m py_compile core/*.py agents/*.py` → OK

---

## Пакет 0 — Безопасность бота (commit `1a19621`)
`security: lock down telegram bot — owner whitelist, fix callback pattern, restrict task handler`

- **config.py**: добавлен `OWNER_USER_ID` (env `OWNER_USER_ID`) и `require_security_ids()` — бросает `RuntimeError "Заданы не все обязательные ID безопасности"`, если `TELEGRAM_CHAT_ID == 0` или `OWNER_USER_ID == 0`. Вызывается в `build_app()` → fail fast при старте.
- **bot/task_handler.py** `handle_manual_task`: строгая проверка в начале — `msg.from_user.id == OWNER_USER_ID` и `message_thread_id == TASKS_TOPIC_ID` (без мягкого `config.X and`).
- **bot/task_handler.py** `handle_task_callback`: та же owner-проверка (одобрение запускает Claude Code = RCE-точка).
- **bot/handlers.py** `handle_media` и `handle_url`: проверка `from_user.id == OWNER_USER_ID`.
- **main.py:41**: паттерн callback `^(exec|cancel):` → `^(approve|cancel):` (кнопка «Одобрить» теперь срабатывает).
- **main.py**: регистрация `handle_manual_task` оставлена как `filters.TEXT & ~filters.COMMAND`, но топик-гейт внутри хендлера не даёт обычному тексту стать задачей.
- **automation/scripts/task_watcher.sh**: добавлен блок ⚠️ SECURITY WARNING. `--dangerously-skip-permissions` оставлен намеренно — источник `tasks/pending/` доверенный после whitelist.
- **.env.example**: задокументированы `TELEGRAM_CHAT_ID`, `TASKS_TOPIC_ID`, `OWNER_USER_ID` как обязательные.

> ⚠️ Перед запуском задать в `.env`: `TELEGRAM_CHAT_ID`, `TASKS_TOPIC_ID`, `OWNER_USER_ID`. Иначе бот не стартует (это by design).

## Пакет 1 — Git-гигиена (commit `e92b103`)
`chore: remove personal data from git, update gitignore`

- `git rm --cached`: `hud/data/memory.json`, `hud/data/preferences.json`, `hud/data/cache/` (кэш запроса), `modules/anime-monitor/data/anime.db`.
- **.gitignore** дополнен: `hud/data/`, `**/data/`, `*.db`, `**/data/*.json`, `tmp/`, `**/tmp/`.

## Пакет 2 — Удаление дублей (commit `3e90c25`)
`refactor: remove duplicate hud/system and old media_analyzer`

- Удалён `hud/system/` целиком (дубль `core/` + `agents/`).
- Удалён `hud/modules/media_analyzer/` целиком (старая копия `modules/tg-media-analyzer`).
- Удалён `hud/main.py` — старый backend-entrypoint, импортировавший удалённый `system.*` (дубликат `core/main.py`). Без него удаление дерева оставило бы битый файл.
- **Не тронуты** (по требованию): `hud/voice/`, `hud/electron/`, `hud/src/`, `hud/ui/`.
- Проверка: `python3 -m py_compile core/main.py` → OK; ссылок `from system.` в коде не осталось.

## Пакет 3 — Мёртвый код (commit `0036fca`)
`cleanup: remove dead code — pool, claude_connector, wot, unused methods`

- Удалён top-level `pool/` (`APIPool` — не использовался, создавал sqlite при импорте). Модуль `modules/tg-media-analyzer/pool/` (другой, `SimplePool`) сохранён.
- Удалён `claude_connector/` (дублировал `agents/claude.py`, мёртвый, устаревший model id).
- Удалён `agents/wot.py` + `WotAgent` исключён из `agents/__init__.py` (агент был недостижим).
- **core/router.py**: удалены `get_best_agent()` и legacy `route()` (без вызовов).
- Удалены пустые stub-каталоги: `mcp/*`, `shared/*`, `infra/*`, `docs/{agents,api,architecture}`, `automation/{cron,workflows}`.

## Пакет 4 — Пути и конфиг (commit `a2c4ae7`)
`fix: configurable root path, centralize model ids`

- **core/config_paths.py** (новый): `ROOT = Path(os.getenv("JARVIS_ROOT", Path.home()/"Projects"/"jarvis"))` + производные `DATA_DIR`, `CACHE_DIR`, `LOGS_DIR`, `PLUGINS_DIR`, `MEMORY_FILE`, `PREFS_FILE`, `SECURITY_LOG`.
- Хардкоды `~/jarvis/...` заменены на пути от `ROOT` в: `core/memory.py`, `cache.py`, `security.py`, `preferences.py`, `plugin_registry.py`, `main.py` (`/plugins/install`).
- **core/models.py** (новый): `CLAUDE_MODEL = "claude-fable-5"`, `GEMINI_MODEL = "gemini-2.5-flash"`.
- Использование централизованных id в: `agents/claude.py`, `agents/gemini.py`, `core/main.py`, `config.yaml` (claude → `claude-fable-5`), `modules/tg-media-analyzer/config.py` (убран устаревший `claude-sonnet-4-20250514`).
- Проверка: `JARVIS_ROOT=/tmp/jarvis_test python3 -c "import core.config_paths, core.models, core.memory ..."` → пути и id резолвятся.

---

## Осталось / требует решения

| Тема | Статус | Рекомендация |
|------|--------|--------------|
| `BaseAgent` (`agents/base.py`) | Не используется (нет наследников, async-контракт + retry не задействованы) | **Требует решения: внедрить или удалить.** Либо перевести агентов на `BaseAgent.execute()`/`run()`, либо удалить класс. |
| `plugin_manager.handle()` / `find_handler()` | Не вызываются в пайплайне — плагины регистрируются/тоглятся, но не диспетчеризуются | **Требует решения: внедрить или удалить.** Либо добавить вызов в `ReasoningCore.process()`, либо удалить систему плагинов. |
| `hud/main.py` удалён | Electron (`hud/electron/main.js:61`) спавнит `~/jarvis/main.py` | Переключить запуск на `core/main.py` и согласовать `~/jarvis` ↔ `~/Projects/jarvis` (или задать `JARVIS_ROOT`). |
| `hud/config.yaml` | Дубликат корневого `config.yaml` (всё ещё с `claude-haiku-4-5-...`) | Решить, нужен ли отдельный конфиг для hud; иначе удалить и читать корневой. |
| `core/main.py` путь к `ui/hud.html` | `os.path.join(ROOT, "ui/hud.html")`, где `ROOT = dirname(__file__)` = `core/` → файл по факту в `hud/ui/` | Поправить путь на `hud/ui/hud.html` при доведении `core/main.py` как канона. |
| `docs/ARCHITECTURE.md` | Отсутствует | Создать актуальную архитектуру; синхронизировать `CLAUDE.md` (порты MCP/shared/infra помечены активными, но удалены/пусты). |

---

## Как смержить
```bash
git checkout main && git merge audit-fixes
```
Перед мержем заполнить `.env`: `TELEGRAM_CHAT_ID`, `TASKS_TOPIC_ID`, `OWNER_USER_ID`.
</content>

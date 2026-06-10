# CLAUDE.md — J.A.R.V.I.S. Project Context
# Этот файл читается Claude Code автоматически при запуске в ~/Projects/jarvis/
# Обновлён: 10.06.2026

## PROJECT IDENTITY

**J.A.R.V.I.S.** — personal Agentic AI OS, Iron Man style.
Solo developer: Sergey (Odessa, Ukraine).
Hardware: MacBook Air M2 (Apple Silicon, MPS optimization).

## DIRECTORY MAP

~/Projects/jarvis/
├── core/              # Reasoning Core, central orchestrator
├── hud/               # Electron app + Vite/React HUD (port 3000)
│   ├── ui/hud.html    # Main HUD interface
│   └── backend/       # Python API (port 7734)
├── agents/            # Specialist agents
│   ├── reasoning_core/
│   ├── intent_analysis/
│   ├── task_decomposition/
│   ├── voice_engine/
│   ├── system_ctl/
│   ├── data_scout/
│   ├── web_agent/
│   ├── browser_agent/
│   ├── game_ctl/
│   └── memory_agent/
├── modules/
│   └── anime-monitor/ # Telegram bot (Python 3.11)
├── mcp/               # MCP server (port 7735)
├── automation/        # n8n workflows
├── shared/            # Shared utils, types, BaseAgent class
├── data/              # ChromaDB, SQLite, local storage
├── docs/              # Architecture docs
├── infra/             # Docker, deployment configs
├── .env               # ← GITIGNORED, secrets here
├── .env.example       # Template for new installs
├── .gitignore
├── CLAUDE.md          # ← You are here
└── README.md 
## ACTIVE PORTS

| Service | Port | Status |
|---------|------|--------|
| HUD Frontend | 3000 | ✅ Active |
| Python API Backend | 7734 | ✅ Active |
| MCP Server | 7735 | ✅ Active |
| Ollama | 11434 | ✅ Active |

## CRITICAL: PYTHON RUNTIME

**USE:** `/opt/homebrew/bin/python3.11`
**NEVER USE:** Python 3.13 (Anaconda) — incompatible with project

## CRITICAL: AGENT-BROWSER INSTALL

```bash
# DO NOT: npm install agent-browser (404 error)
# DO:
git clone https://github.com/vercel-labs/agent-browser.git
cd agent-browser && npm install
rm -f /opt/homebrew/bin/agent-browser
npm link
```

## VOICE STATUS

```yaml
# config.yaml
VOICE_ENABLED: false   # Input DISABLED
# TTS output (ElevenLabs) is PRESERVED
```

## SECURITY RULES (Phase 1 — IN PROGRESS)

- [ ] Replace all shell=True with shlex.split() + command whitelist
- [ ] Add rate limiting to all API endpoints
- [ ] CORS: localhost only
- [ ] Secrets: .env only, never in source
- [ ] BaseAgent class in shared/ (not yet implemented — BLOCKER)
- [ ] Resolve: system/agents.py vs system/agents/ directory conflict

## BEHAVIORAL CONTRACT

1. Always respond in Russian
2. Every response ends with Рекомендации block
3. No code generation without architecture agreement first
4. Deliver updates as terminal commands only
5. Request pipeline: Intent Analysis → Task Decomposition → Agent Dispatch

## PRIORITY QUEUE (10.06.2026)

P1: animevost.org full catalog parse (352 pages, fantasy+adventure)
P2: HUD Phase 1 Security Audit
P3: 3D Agent Visualization (glowing orbs around central orb)
P4: Telegram bot for mobile JARVIS control
P5: Morning briefing automation (08:00)
P6: Google Calendar integration

## KNOWN ISSUES

| Issue | Fix |
|-------|-----|
| ReplyKeyboardMarkup arg | Use is_persistent=True, NOT persistent |
| Flat module structure | Ensure __init__.py in agents/, bot/, api/ |
| Telegram callback_data 64b limit | Store in ctx.user_data, pass index only |
| Jikan API 429 | 1.2s delay between requests |
| Ollama timeout | Set 120s for Mistral 7B on M2 |
| Model mismatch | .env model = llama3.2 (matches installed) |
| Electron duplicates | requestSingleInstanceLock + pkill before launch |

## EXTERNAL DEPENDENCIES

| Service | URL/Host | Notes |
|---------|----------|-------|
| Groq API | api.groq.com | 14,400 req/day free |
| Ollama | localhost:11434 | Model: llama3.2 |
| Jikan API | api.jikan.moe/v4 | Free, 3 req/sec |
| ElevenLabs | websockets | TTS output only |
| Supabase | Free tier | DB |
| n8n | Local | Automation |
| ChromaDB | Local | Vector memory |

## DESIGN INSPIRATION

- @huwprosser (TikTok) — 15 years orb interface evolution
- Paradigm: draggable PiP orb as peripheral AI
- Audio-reactive Canvas sphere: particles, arcs, corona

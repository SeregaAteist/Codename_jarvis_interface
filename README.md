# J.A.R.V.I.S.
Personal AI OS — MacBook Air M2

## Structure
- core/       Reasoning Core, Intent, Memory, Event Bus
- hud/        React + Vite HUD (localhost:3000)
- agents/     Specialist agents
- modules/    anime-monitor Telegram bot
- mcp/        MCP servers
- automation/ n8n workflows, cron
- shared/     Types, utils, config
- data/       ChromaDB, SQLite, logs (gitignored)

## Quick start
cd hud && npm install && npm run dev
cd modules/anime-monitor && source venv/bin/activate && python main.py

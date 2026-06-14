PY = /opt/homebrew/bin/python3.11

.PHONY: test lint type-check format check coverage services restart-all

test:
	$(PY) -m pytest tests/ -q

lint:
	$(PY) -m ruff check modules/ shared/ agents/ core/

type-check:
	$(PY) -m mypy shared/ modules/rafail/registry/ \
	  modules/kommo/ modules/ringostat/ agents/ \
	  --strict --ignore-missing-imports

format:
	$(PY) -m black modules/ shared/ agents/ core/

check: lint type-check test

coverage:
	$(PY) -m pytest tests/ \
	  --cov=modules --cov=shared --cov=agents --cov=core \
	  --cov-report=term-missing

services:
	launchctl list | grep jarvis

restart-all:
	launchctl unload ~/Library/LaunchAgents/com.jarvis.*.plist 2>/dev/null; \
	sleep 2; \
	launchctl load ~/Library/LaunchAgents/com.jarvis.*.plist 2>/dev/null

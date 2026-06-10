"""Configurable project paths.

All runtime data lives under ROOT. Override the base directory with the
JARVIS_ROOT environment variable; defaults to ~/Projects/jarvis.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT: Path = Path(os.getenv("JARVIS_ROOT", Path.home() / "Projects" / "jarvis"))

DATA_DIR: Path    = ROOT / "data"
CACHE_DIR: Path   = DATA_DIR / "cache"
LOGS_DIR: Path    = ROOT / "logs"
PLUGINS_DIR: Path = ROOT / "plugins"

MEMORY_FILE: Path  = DATA_DIR / "memory.json"
PREFS_FILE: Path   = DATA_DIR / "preferences.json"
SECURITY_LOG: Path = LOGS_DIR / "security.log"

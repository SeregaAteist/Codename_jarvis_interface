#!/bin/bash
# S-6: ежедневный бэкап SQLite-баз JARVIS в data/backups/ (хранить 7 дней).
# Использует sqlite3 .backup (консистентный снимок). Запускается launchd-агентом
# com.jarvis.sqlite-backup в 03:00 или вручную: bash automation/scripts/backup_sqlite.sh
set -u
ROOT="${JARVIS_ROOT:-$HOME/Projects/jarvis}"
BACKUP_DIR="$ROOT/data/backups"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"

DBS=(
    "$ROOT/data/sqlite/jarvis.db"
    "$ROOT/modules/tg-media-analyzer/data/media_analyzer.db"
    "$ROOT/data/sqlite/rafail.db"
)

for db in "${DBS[@]}"; do
    [ -f "$db" ] || continue
    name="$(basename "$db" .db)"
    dest="$BACKUP_DIR/${name}-${STAMP}.db"
    if sqlite3 "$db" ".backup '$dest'" 2>/dev/null; then
        echo "[$(date)] ✅ $name → $(basename "$dest")"
    else
        echo "[$(date)] ⚠️ не удалось забэкапить $name"
    fi
done

# Прунинг: удалить бэкапы старше 7 дней
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete 2>/dev/null || true
echo "[$(date)] backup done (хранится 7 дней)"

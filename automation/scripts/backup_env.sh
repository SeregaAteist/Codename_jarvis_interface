#!/bin/bash
BACKUP_DIR=~/Projects/jarvis/backups/env
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)

grep -E "^[A-Z_]+=?" ~/Projects/jarvis/.env | \
  sed 's/=.*/=***/' > "$BACKUP_DIR/env_structure_$DATE.txt"

echo "[$DATE] .env структура збережена" >> ~/Projects/jarvis/logs/backup.log

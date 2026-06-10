#!/bin/bash
# ⚠️  SECURITY WARNING ⚠️
# Этот watcher запускает Claude Code с --dangerously-skip-permissions
# (полный доступ к ФС и shell без подтверждений).
# Источник задач — tasks/pending/, наполняется ТОЛЬКО task-ботом ПОСЛЕ проверки
# OWNER_USER_ID (см. modules/tg-media-analyzer/bot/task_handler.py).
# НЕ давайте другим процессам/пользователям писать в tasks/pending/.
# --dangerously-skip-permissions оставлен намеренно: источник доверенный после whitelist.
#
# Task watcher — monitors pending tasks and runs Claude Code
TASKS_DIR="$HOME/Projects/jarvis/tasks"
CLAUDE="$HOME/.local/bin/claude"
LOG="$TASKS_DIR/watcher.log"

# macOS не имеет timeout по умолчанию. Используем timeout/gtimeout (coreutils) если есть,
# иначе работаем без таймаута — не ломая пайплайн (brew install coreutils даёт gtimeout).
TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_PREFIX=""
[ -n "$TIMEOUT_BIN" ] && TIMEOUT_PREFIX="$TIMEOUT_BIN 600"

mkdir -p "$TASKS_DIR/pending" "$TASKS_DIR/done"
echo "[$(date)] Watcher started" >> "$LOG"

while true; do
    for task_file in "$TASKS_DIR/pending"/TASK_*.md; do
        [ -f "$task_file" ] || continue
        task_id=$(basename "$task_file" .md)
        echo "[$(date)] Processing: $task_id" >> "$LOG"

        # Запустить Claude Code
        result_file="$TASKS_DIR/done/${task_id}.result"
        cd "$HOME/Projects/jarvis" && \
        $TIMEOUT_PREFIX "$CLAUDE" --model claude-fable-5 --dangerously-skip-permissions --print \
            "$(cat "$task_file")" > "$result_file" 2>&1

        # Переместить задачу
        mv "$task_file" "$TASKS_DIR/done/${task_id}.md"
        echo "[$(date)] Done: $task_id" >> "$LOG"
    done
    sleep 3
done

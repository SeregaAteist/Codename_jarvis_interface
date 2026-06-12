#!/bin/bash
TASKS_DIR="$HOME/Projects/jarvis/tasks"
CLAUDE="$HOME/.local/bin/claude"
LOG="$TASKS_DIR/watcher.log"
PIDFILE="$TASKS_DIR/watcher.pid"

# Singleton через PID-файл
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date)] Watcher already running (PID $OLD_PID), exiting." >> "$LOG"
        exit 0
    fi
fi
echo $$ > "$PIDFILE"
trap "rm -f $PIDFILE" EXIT

TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
TIMEOUT_PREFIX=""
[ -n "$TIMEOUT_BIN" ] && TIMEOUT_PREFIX="$TIMEOUT_BIN 600"

mkdir -p "$TASKS_DIR/pending" "$TASKS_DIR/done" "$TASKS_DIR/processing"
echo "[$(date)] Watcher started (PID $$)" >> "$LOG"

while true; do
    for task_file in "$TASKS_DIR/pending"/TASK_*.md; do
        [ -f "$task_file" ] || continue
        task_id=$(basename "$task_file" .md)
        mv "$task_file" "$TASKS_DIR/processing/${task_id}.md" 2>/dev/null || continue
        echo "[$(date)] Processing: $task_id" >> "$LOG"
        result_file="$TASKS_DIR/done/${task_id}.result"
        cd "$HOME/Projects/jarvis" && \
        $TIMEOUT_PREFIX "$CLAUDE" --model claude-fable-5 --dangerously-skip-permissions --print \
            --output-format text \
            "$(cat "$TASKS_DIR/processing/${task_id}.md")" > "$result_file.tmp" 2>&1
        mv "$result_file.tmp" "$result_file"
        mv "$TASKS_DIR/processing/${task_id}.md" "$TASKS_DIR/done/${task_id}.md"
        echo "[$(date)] Done: $task_id" >> "$LOG"
    done
    sleep 3
done

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
        $TIMEOUT_PREFIX "$CLAUDE" --model claude-sonnet-4-6 --dangerously-skip-permissions --print \
            --output-format text \
            "$(cat "$TASKS_DIR/processing/${task_id}.md")" > "$result_file.tmp" 2>&1
        mv "$result_file.tmp" "$result_file"
        mv "$TASKS_DIR/processing/${task_id}.md" "$TASKS_DIR/done/${task_id}.md"
        echo "[$(date)] Done: $task_id" >> "$LOG"

        # если задача из TG — отправить результат обратно
        DONE_TASK="$TASKS_DIR/done/${task_id}.md"
        if grep -q "^CHAT_ID:" "$DONE_TASK" 2>/dev/null; then
            TG_CHAT=$(grep "^CHAT_ID:" "$DONE_TASK" | awk '{print $2}')
            TG_TOPIC=$(grep "^TOPIC_ID:" "$DONE_TASK" | awk '{print $2}')
            TG_TOKEN=$(grep "^JARVIS_WORK_BOT_TOKEN=" "$HOME/Projects/jarvis/.env" | cut -d= -f2-)
            [ -z "$TG_TOKEN" ] && TG_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" "$HOME/Projects/jarvis/.env" | cut -d= -f2-)
            /opt/homebrew/bin/python3.11 <<PYEOF 2>>"$LOG"
import json, urllib.request
task_id = "$task_id"
chat_id = $TG_CHAT
topic_id = $TG_TOPIC
token = "$TG_TOKEN"
try:
    with open("$result_file") as f:
        result = f.read(3000)
except Exception:
    result = "(нет результата)"
text = f"✅ Готово: {task_id}\n\n{result}"[:4000]
payload = json.dumps({"chat_id": chat_id, "message_thread_id": topic_id, "text": text}).encode()
req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data=payload, headers={"Content-Type": "application/json"}
)
try:
    urllib.request.urlopen(req, timeout=10)
except Exception as e:
    print(f"[TG send error] {e}")
PYEOF
        fi
    done
    sleep 3
done

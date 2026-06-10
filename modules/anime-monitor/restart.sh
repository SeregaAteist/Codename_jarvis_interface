#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source venv/bin/activate

echo "⏹  Останавливаю старый процесс..."
pkill -f "python main.py" 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Ждём освобождения порта (до 10 сек)
for i in $(seq 1 10); do
    lsof -ti:8000 > /dev/null 2>&1 || break
    echo "   Порт 8000 занят, жду... ($i/10)"
    sleep 1
done

# Убиваем насильно если всё ещё занят
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

echo "▶️  Запускаю..."
nohup python -u main.py >> logs/bot.log 2>&1 &
echo "PID=$! | tail -f logs/bot.log"

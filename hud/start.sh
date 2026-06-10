#!/bin/bash
echo "Останавливаю старые процессы..."
pkill -f "python3.*main.py" 2>/dev/null
pkill -f "ollama serve" 2>/dev/null
sleep 1

echo "Запускаю JARVIS..."
cd ~/jarvis && npx electron .

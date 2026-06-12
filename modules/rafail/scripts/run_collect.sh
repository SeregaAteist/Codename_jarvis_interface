#!/bin/bash
cd ~/Projects/jarvis
# тот же интерпретатор, что у com.jarvis.rafail-bot (зависимости rafail стоят там)
/Users/seregaateist/Projects/jarvis/modules/tg-media-analyzer/venv/bin/python -c "
import sys, asyncio
sys.path.insert(0, '.')
from modules.rafail.collector import collect_all
from modules.rafail.processor import process_pending
async def main():
    collected = await collect_all(hours=24)
    print('Собрано:', collected)
    result = await process_pending(limit=10)
    print('Обработано:', result)
asyncio.run(main())
" >> ~/Projects/jarvis/logs/rafail-cron.log 2>&1

#!/usr/bin/env python3
"""Healthcheck бота tg-media-analyzer.

Проверяет:
1. Конфиг (.env): токен, обязательные ID безопасности, ключи API.
2. Процесс бота (launchd: com.jarvis.tg-media-analyzer).
3. Доступность Bot API (getMe).
4. Реальную отправку тестового сообщения в рабочий топик (TOPIC_ID;
   топик 1 = General — message_thread_id при отправке опускается).

Запуск:
    cd modules/tg-media-analyzer && venv/bin/python scripts/healthcheck.py
Опционально: --no-send (без тестового сообщения), --report "текст"
(отправить текст в топик задач TASKS_TOPIC_ID вместо тестового сообщения).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

GENERAL_TOPIC_ID = 1
API = "https://api.telegram.org/bot{token}/{method}"


def tg_call(method: str, payload: dict | None = None) -> dict:
    url = API.format(token=config.TELEGRAM_TOKEN, method=method)
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def check_config() -> list[str]:
    problems = []
    if not config.TELEGRAM_TOKEN:
        problems.append("TELEGRAM_BOT_TOKEN не задан")
    if config.TELEGRAM_CHAT_ID == 0:
        problems.append("TELEGRAM_CHAT_ID не задан")
    if config.OWNER_USER_ID == 0:
        problems.append("OWNER_USER_ID не задан")
    if not config.GEMINI_KEYS:
        problems.append("Нет ключей Gemini")
    return problems


def check_process() -> bool:
    res = subprocess.run(
        ["pgrep", "-f", "tg-media-analyzer/main.py"],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-send", action="store_true",
                        help="не отправлять тестовое сообщение")
    parser.add_argument("--report", default="",
                        help="отправить текст в топик задач и выйти")
    args = parser.parse_args()

    if args.report:
        thread = config.TASKS_TOPIC_ID
        payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": args.report}
        if thread and thread != GENERAL_TOPIC_ID:
            payload["message_thread_id"] = thread
        r = tg_call("sendMessage", payload)
        print("report sent" if r.get("ok") else f"report failed: {r}")
        return 0 if r.get("ok") else 1

    ok = True

    problems = check_config()
    if problems:
        ok = False
        for p in problems:
            print(f"❌ config: {p}")
    else:
        print(f"✅ config: chat={config.TELEGRAM_CHAT_ID}, "
              f"topic={config.TOPIC_ID}, tasks_topic={config.TASKS_TOPIC_ID}, "
              f"gemini_keys={len(config.GEMINI_KEYS)}, "
              f"claude_keys={len(config.CLAUDE_KEYS)}")

    if check_process():
        print("✅ process: main.py запущен")
    else:
        ok = False
        print("❌ process: main.py НЕ запущен "
              "(launchctl kickstart -k gui/$(id -u)/com.jarvis.tg-media-analyzer)")

    try:
        me = tg_call("getMe")
        if me.get("ok"):
            print(f"✅ api: getMe → @{me['result']['username']}")
        else:
            ok = False
            print(f"❌ api: getMe → {me}")
    except Exception as e:
        ok = False
        print(f"❌ api: {e}")

    if not args.no_send and ok:
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": "🩺 Healthcheck: бот на связи в этом топике.",
        }
        # General (топик 1) — message_thread_id опускается
        if config.TOPIC_ID and config.TOPIC_ID != GENERAL_TOPIC_ID:
            payload["message_thread_id"] = config.TOPIC_ID
        try:
            r = tg_call("sendMessage", payload)
            if r.get("ok"):
                print(f"✅ send: тестовое сообщение в топик {config.TOPIC_ID} "
                      f"доставлено (message_id={r['result']['message_id']})")
            else:
                ok = False
                print(f"❌ send: {r}")
        except Exception as e:
            ok = False
            print(f"❌ send: {e}")

    print("\n=== HEALTHCHECK:", "OK ===" if ok else "FAILED ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""J.A.R.V.I.S. Process Manager — watchdog-демон (stdlib only, без venv-зависимостей).

РАЗДЕЛЕНИЕ КОНТРОЛЯ (важно — без двойного управления одним процессом):
  • launchd-сервисы (telegram-bot, task-watcher) — PM ТОЛЬКО МОНИТОРИТ.
    Перезапуск/KeepAlive делает launchd. PM их никогда не убивает и не стартует.
  • Управляемые сервисы (Python API:7734, HUD Electron:3000, Ollama:11434, n8n:5678)
    — PM мониторит + при необходимости анти-дубль (kill лишних PID) и рестарт.

По умолчанию команда `status` — READ-ONLY (ничего не убивает). Действия (enforce/
restart/watch --auto) — только явными флагами. Анти-дубль самого PM — pid-lock.

Запуск:
  python3 infra/process_manager.py status              # таблица состояний (безопасно)
  python3 infra/process_manager.py watch [--auto]      # демон-наблюдатель
  python3 infra/process_manager.py restart <name>      # рестарт управляемого сервиса
  python3 infra/process_manager.py enforce             # убрать дубли управляемых
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(os.getenv("JARVIS_ROOT", Path.home() / "Projects" / "jarvis"))
LOCK = ROOT / "data" / "process_manager.pid"


@dataclass
class Service:
    name: str
    managed: bool                       # False = под launchd (только мониторинг)
    port: int | None = None             # проверка живости по TCP-порту
    launchd_label: str | None = None    # проверка через launchctl
    pattern: str | None = None          # pgrep -f для PID/анти-дубля
    start_cmd: list[str] | None = None  # команда старта (только managed)


SERVICES: list[Service] = [
    # --- под launchd: ТОЛЬКО мониторинг ---
    Service("telegram-bot", managed=False, launchd_label="com.jarvis.tg-media-analyzer",
            pattern="tg-media-analyzer/main.py"),
    Service("task-watcher", managed=False, launchd_label="com.jarvis.task-watcher",
            pattern="task_watcher.sh"),
    # --- управляемые PM ---
    Service("python-api", managed=True, port=7734, pattern="backend"),
    Service("hud-electron", managed=True, port=3000, pattern="hud/.*[Ee]lectron"),
    Service("ollama", managed=True, port=11434, pattern="ollama serve",
            start_cmd=["ollama", "serve"]),
    Service("n8n", managed=True, port=5678, pattern="n8n"),
]


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def _pids(pattern: str) -> list[int]:
    if not pattern:
        return []
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout
        return [int(x) for x in out.split()]
    except Exception:
        return []


def _launchd_pid(label: str) -> int | None:
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[-1] == label:
                return int(parts[0]) if parts[0].isdigit() else None
    except Exception:
        pass
    return None


def check(svc: Service) -> dict:
    """Состояние сервиса: up, pids, detail."""
    if svc.launchd_label:
        pid = _launchd_pid(svc.launchd_label)
        return {"up": pid is not None, "pids": [pid] if pid else [], "detail": "launchd"}
    up = _port_open(svc.port) if svc.port else bool(_pids(svc.pattern or ""))
    return {"up": up, "pids": _pids(svc.pattern or ""), "detail": f"port {svc.port}" if svc.port else "process"}


def status() -> list[dict]:
    rows = []
    for svc in SERVICES:
        st = check(svc)
        rows.append({
            "name": svc.name,
            "up": st["up"],
            "pids": st["pids"],
            "control": "launchd (monitor)" if not svc.managed else "PM (managed)",
            "detail": st["detail"],
        })
    return rows


def print_status() -> None:
    print(f"{'SERVICE':<16}{'STATUS':<10}{'PID(S)':<22}{'CONTROL':<20}")
    print("-" * 68)
    for r in status():
        st = "🟢 up" if r["up"] else "🔴 down"
        pids = ",".join(map(str, r["pids"])) or "—"
        print(f"{r['name']:<16}{st:<10}{pids:<22}{r['control']:<20}")


def enforce_single_instance(svc: Service, dry_run: bool = True) -> str:
    """Анти-дубль: для УПРАВЛЯЕМЫХ — оставить новейший PID, лишние убить. launchd не трогаем."""
    if not svc.managed:
        return f"{svc.name}: под launchd — анти-дубль делает launchd (KeepAlive), PM не вмешивается"
    pids = sorted(_pids(svc.pattern or ""))
    if len(pids) <= 1:
        return f"{svc.name}: дублей нет ({len(pids)} PID)"
    keep, extra = pids[-1], pids[:-1]
    if dry_run:
        return f"{svc.name}: дубли {extra} (оставить {keep}) — dry-run, не убито"
    for p in extra:
        try:
            os.kill(p, signal.SIGTERM)
        except Exception:
            pass
    return f"{svc.name}: убито {extra}, оставлен {keep}"


def restart(name: str) -> str:
    svc = next((s for s in SERVICES if s.name == name), None)
    if not svc:
        return f"нет сервиса '{name}'"
    if not svc.managed:
        return (f"{svc.name}: под launchd — PM НЕ перезапускает. "
                f"Используй: launchctl kickstart -k gui/$(id -u)/{svc.launchd_label}")
    for p in _pids(svc.pattern or ""):
        try:
            os.kill(p, signal.SIGTERM)
        except Exception:
            pass
    time.sleep(1)
    if not svc.start_cmd:
        return f"{svc.name}: остановлен; команда старта не задана — запусти вручную"
    try:
        subprocess.Popen(svc.start_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return f"{svc.name}: рестарт ({' '.join(svc.start_cmd)})"
    except Exception as e:
        return f"{svc.name}: ошибка старта — {e}"


def _acquire_lock() -> bool:
    """Анти-дубль самого PM: pid-lock. True если захватили, False если PM уже работает."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            old = int(LOCK.read_text().strip())
            os.kill(old, 0)  # жив?
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # мёртвый/чужой — перезаписываем
    LOCK.write_text(str(os.getpid()))
    return True


def watch(interval: int = 15, auto: bool = False) -> None:
    if not _acquire_lock():
        print(f"PM уже запущен (lock: {LOCK}). Выход.")
        sys.exit(1)
    import atexit
    atexit.register(lambda: LOCK.exists() and LOCK.unlink(missing_ok=True))
    print(f"[PM] watchdog запущен (interval={interval}s, auto-restart={auto})")
    while True:
        for svc in SERVICES:
            st = check(svc)
            if svc.managed:
                if len(st["pids"]) > 1:
                    print("[PM]", enforce_single_instance(svc, dry_run=not auto))
                if not st["up"] and auto and svc.start_cmd:
                    print("[PM]", restart(svc.name))
            elif not st["up"]:
                # launchd-сервис лежит — только сигналим, рестарт за launchd
                print(f"[PM] ⚠️ {svc.name} (launchd) down — ждём KeepAlive, PM не вмешивается")
        time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="JARVIS Process Manager")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    w = sub.add_parser("watch")
    w.add_argument("--auto", action="store_true", help="авто-рестарт управляемых (не launchd)")
    w.add_argument("--interval", type=int, default=15)
    r = sub.add_parser("restart")
    r.add_argument("name")
    e = sub.add_parser("enforce")
    e.add_argument("--apply", action="store_true", help="реально убить дубли (иначе dry-run)")
    args = ap.parse_args()

    if args.cmd == "watch":
        watch(interval=args.interval, auto=args.auto)
    elif args.cmd == "restart":
        print(restart(args.name))
    elif args.cmd == "enforce":
        for svc in SERVICES:
            print(enforce_single_instance(svc, dry_run=not args.apply))
    else:
        print_status()


if __name__ == "__main__":
    main()

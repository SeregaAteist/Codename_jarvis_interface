"""ProcessManager — мониторинг и управление сервисами JARVIS."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PLIST_DIR = Path.home() / "Library/LaunchAgents"


@dataclass
class ServiceInfo:
    name: str
    pid: int | None
    exit_code: str
    plist_path: Path | None = None

    @property
    def is_running(self) -> bool:
        return self.pid is not None and self.exit_code == "0"

    @property
    def is_crashed(self) -> bool:
        return self.exit_code not in ("0", "-")


class ProcessManager:
    """Менеджер процессов JARVIS."""

    JARVIS_SERVICES = [
        "com.jarvis.tg-media-analyzer",
        "com.jarvis.rafail-bot",
        "com.jarvis.work-bot",
        "com.jarvis.ringostat",
        "com.jarvis.anime-monitor",
        "com.jarvis.task-watcher",
        "com.jarvis.rafail-cron",
        "com.jarvis.sqlite-backup",
        "com.jarvis.morning-briefing",
    ]

    def status_all(self) -> list[ServiceInfo]:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        services = []
        for line in result.stdout.split("\n"):
            for name in self.JARVIS_SERVICES:
                if name in line:
                    parts = line.split("\t")
                    pid_str = parts[0].strip() if len(parts) > 0 else "-"
                    code_str = parts[1].strip() if len(parts) > 1 else "-"
                    pid = (
                        int(pid_str)
                        if pid_str.lstrip("-").isdigit() and pid_str != "-"
                        else None
                    )
                    plist = PLIST_DIR / f"{name}.plist"
                    services.append(
                        ServiceInfo(
                            name=name,
                            pid=pid,
                            exit_code=code_str,
                            plist_path=plist if plist.exists() else None,
                        )
                    )
        return services

    def restart(self, service_name: str) -> bool:
        plist = PLIST_DIR / f"{service_name}.plist"
        if not plist.exists():
            logger.error("[pm] plist не найден: %s", service_name)
            return False
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        result = subprocess.run(["launchctl", "load", str(plist)], capture_output=True)
        return result.returncode == 0

    def restart_crashed(self) -> list[str]:
        """Перезапустить упавшие сервисы."""
        restarted = []
        for service in self.status_all():
            if service.is_crashed and service.plist_path:
                logger.warning("[pm] перезапуск упавшего: %s", service.name)
                if self.restart(service.name):
                    restarted.append(service.name)
        return restarted

    def get_summary(self) -> str:
        services = self.status_all()
        running = [s for s in services if s.is_running]
        crashed = [s for s in services if s.is_crashed]
        lines = [f"🔧 Сервіси JARVIS: {len(running)}/{len(services)} працюють"]
        if crashed:
            lines.append(
                "⚠️ Впали: "
                + ", ".join(s.name.replace("com.jarvis.", "") for s in crashed)
            )
        return "\n".join(lines)


_pm: ProcessManager | None = None


def get_process_manager() -> ProcessManager:
    global _pm
    if _pm is None:
        _pm = ProcessManager()
    return _pm

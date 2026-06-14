"""System monitor — CPU, RAM, disk, battery, temp, network with voice alerts."""

from __future__ import annotations

import re
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime

import psutil

THRESHOLDS = {
    "cpu": 85,  # % CPU load
    "ram": 88,  # % RAM used
    "disk": 90,  # % disk used
    "temp": 85,  # °C CPU temp
    "battery": 20,  # % — warn
    "battery_low": 10,  # % — critical
}

# How often each alert key can fire (seconds)
_COOLDOWNS = {
    "cpu": 120,
    "ram": 180,
    "disk": 3600,
    "temp": 180,
    "battery_low": 300,
    "battery_critical": 120,
}


def _get_thermal_pressure() -> str:
    """Return thermal pressure level from powermetrics (no password needed after sudoers setup).
    Values: Nominal | Fair | Serious | Critical
    """
    try:
        r = subprocess.run(
            [
                "sudo",
                "-n",
                "powermetrics",
                "-n",
                "1",
                "-i",
                "200",
                "--samplers",
                "thermal",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        m = re.search(r"Current pressure level:\s+(\w+)", r.stdout)
        if m:
            return m.group(1)  # Nominal / Fair / Serious / Critical
    except Exception:
        pass
    return "Unknown"


def _get_cpu_temp() -> float | None:
    """CPU temperature in °C.

    Apple Silicon (M-series) does not expose die temperature via any
    public API — returns None. Intel Macs can use osx-cpu-temp.
    Use get_metrics()['thermal_pressure'] for qualitative state instead.
    """
    # Intel Mac: osx-cpu-temp (brew install osx-cpu-temp)
    try:
        r = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True, timeout=2)
        raw = r.stdout.strip().replace("°C", "").replace("C", "").strip()
        if raw:
            val = float(raw)
            if val > 1.0:  # 0.0 = bogus Apple Silicon reading
                return val
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass

    # psutil sensors (Linux / rare Intel Mac builds)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries and entries[0].current > 1.0:
                    return float(entries[0].current)
    except (AttributeError, Exception):
        pass

    return None


class SystemMonitor:
    def __init__(
        self,
        speaker: Callable[[str], None] | None = None,
        on_alert: Callable[[dict], None] | None = None,
    ):
        self.speaker = speaker
        self.on_alert = on_alert
        self._running = False
        self._alerted: dict[str, float] = {}
        self._thread: threading.Thread | None = None
        self._last_metrics: dict = {}
        self._lock = threading.Lock()

    # ── Metrics collection ────────────────────────────────────────────────────

    def get_metrics(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Battery
        battery = psutil.sensors_battery()
        batt_pct = round(battery.percent, 1) if battery else None
        batt_charge = battery.power_plugged if battery else None

        # Network totals
        net = psutil.net_io_counters()

        # Top-3 processes by CPU
        top_procs: list[dict] = []
        try:
            procs = sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                key=lambda p: p.info.get("cpu_percent") or 0,
                reverse=True,
            )[:5]
            for proc in procs:
                try:
                    cpu_p = proc.info.get("cpu_percent") or 0
                    if cpu_p < 0.1:
                        continue
                    top_procs.append(
                        {
                            "name": proc.info["name"] or "?",
                            "cpu": round(cpu_p, 1),
                            "ram": round(proc.info.get("memory_percent") or 0, 1),
                        }
                    )
                    if len(top_procs) >= 3:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        metrics = {
            "cpu": round(cpu, 1),
            "ram": round(ram.percent, 1),
            "ram_used_gb": round(ram.used / 1024**3, 1),
            "ram_total_gb": round(ram.total / 1024**3, 1),
            "disk": round(disk.percent, 1),
            "disk_free_gb": round(disk.free / 1024**3, 1),
            "disk_total_gb": round(disk.total / 1024**3, 1),
            "temp": _get_cpu_temp(),
            "thermal_pressure": _get_thermal_pressure(),
            "battery_pct": batt_pct,
            "battery_charging": batt_charge,
            "net_sent_mb": round(net.bytes_sent / 1024**2, 1),
            "net_recv_mb": round(net.bytes_recv / 1024**2, 1),
            "top_processes": top_procs,
            "timestamp": datetime.now().isoformat(),
        }
        with self._lock:
            self._last_metrics = metrics
        return metrics

    def last_metrics(self) -> dict:
        with self._lock:
            return dict(self._last_metrics)

    # ── Alert logic ───────────────────────────────────────────────────────────

    def check_alerts(self, metrics: dict) -> list[dict]:
        alerts: list[dict] = []
        now = time.monotonic()

        def _can_fire(key: str) -> bool:
            cooldown = _COOLDOWNS.get(key, 300)
            last = self._alerted.get(key, 0.0)
            if now - last > cooldown:
                self._alerted[key] = now
                return True
            return False

        if metrics["cpu"] > THRESHOLDS["cpu"] and _can_fire("cpu"):
            top = (
                metrics["top_processes"][0]["name"] if metrics["top_processes"] else "?"
            )
            alerts.append(
                {
                    "level": "warning",
                    "key": "cpu",
                    "message": (
                        f"Загрузка процессора {metrics['cpu']}%, сэр. "
                        f"Основной потребитель — {top}. Рекомендую закрыть лишние приложения."
                    ),
                }
            )

        if metrics["ram"] > THRESHOLDS["ram"] and _can_fire("ram"):
            top = (
                metrics["top_processes"][0]["name"] if metrics["top_processes"] else "?"
            )
            alerts.append(
                {
                    "level": "warning",
                    "key": "ram",
                    "message": (
                        f"Память заполнена на {metrics['ram']}% "
                        f"({metrics['ram_used_gb']} из {metrics['ram_total_gb']} ГБ), сэр. "
                        f"Основной потребитель — {top}."
                    ),
                }
            )

        if metrics["disk"] > THRESHOLDS["disk"] and _can_fire("disk"):
            alerts.append(
                {
                    "level": "critical",
                    "key": "disk",
                    "message": (
                        f"Диск заполнен на {metrics['disk']}%. "
                        f"Свободно {metrics['disk_free_gb']} ГБ, сэр. Требуется очистка."
                    ),
                }
            )

        if (
            metrics["temp"] is not None
            and metrics["temp"] > THRESHOLDS["temp"]
            and _can_fire("temp")
        ):
            alerts.append(
                {
                    "level": "warning",
                    "key": "temp",
                    "message": (
                        f"Температура процессора {metrics['temp']}°C, сэр. "
                        "Система перегревается. Проверьте вентиляцию."
                    ),
                }
            )

        pressure = metrics.get("thermal_pressure", "Nominal")
        if pressure == "Critical" and _can_fire("thermal_critical"):
            alerts.append(
                {
                    "level": "critical",
                    "key": "temp",
                    "message": "Критическое тепловое состояние системы, сэр. Возможен троттлинг процессора.",
                }
            )
        elif pressure == "Serious" and _can_fire("thermal_serious"):
            alerts.append(
                {
                    "level": "warning",
                    "key": "temp",
                    "message": "Повышенная тепловая нагрузка на процессор, сэр. Рекомендую снизить нагрузку.",
                }
            )

        batt = metrics.get("battery_pct")
        if batt is not None and not metrics.get("battery_charging"):
            if batt <= THRESHOLDS["battery_low"] and _can_fire("battery_critical"):
                alerts.append(
                    {
                        "level": "critical",
                        "key": "battery",
                        "message": (
                            f"Критический заряд батареи — {batt}%, сэр. "
                            "Подключите питание немедленно."
                        ),
                    }
                )
            elif batt <= THRESHOLDS["battery"] and _can_fire("battery_low"):
                alerts.append(
                    {
                        "level": "warning",
                        "key": "battery",
                        "message": (
                            f"Заряд батареи {batt}%, сэр. "
                            "Рекомендую подключить питание."
                        ),
                    }
                )

        return alerts

    # ── Background loop ───────────────────────────────────────────────────────

    def _loop(self, interval: int):
        # Prime cpu_percent — first call always returns 0.0
        psutil.cpu_percent(interval=None)
        time.sleep(2)

        while self._running:
            try:
                metrics = self.get_metrics()
                alerts = self.check_alerts(metrics)
                for alert in alerts:
                    print(f"[MONITOR] {alert['level'].upper()}: {alert['message']}")
                    if self.speaker:
                        try:
                            self.speaker(alert["message"])
                        except Exception:
                            pass
                    if self.on_alert:
                        try:
                            self.on_alert(alert)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[MONITOR] error: {e}")
            time.sleep(interval)

    def start(self, interval: int = 30) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, args=(interval,), daemon=True, name="jarvis-monitor"
        )
        self._thread.start()
        print(f"[MONITOR] Started — interval {interval}s")

    def stop(self) -> None:
        self._running = False

    # ── Natural language reports ──────────────────────────────────────────────

    def get_report(self) -> str:
        m = self.get_metrics()
        parts = [
            "Системный отчёт, сэр.",
            f"Процессор: {m['cpu']}%.",
            f"Память: {m['ram']}% ({m['ram_used_gb']} из {m['ram_total_gb']} ГБ).",
            f"Диск: {m['disk']}%, свободно {m['disk_free_gb']} ГБ.",
        ]
        if m["temp"] is not None:
            parts.append(f"Температура: {m['temp']}°C.")
        elif m.get("thermal_pressure") and m["thermal_pressure"] != "Unknown":
            parts.append(f"Тепловое давление: {m['thermal_pressure']}.")
        if m["battery_pct"] is not None:
            status = "заряжается" if m["battery_charging"] else "от батареи"
            parts.append(f"Батарея: {m['battery_pct']}% ({status}).")
        if m["top_processes"]:
            top = m["top_processes"][0]
            parts.append(f"Топ процесс: {top['name']} — {top['cpu']}% CPU.")
        return " ".join(parts)

    def get_cpu_report(self) -> str:
        m = self.get_metrics()
        lines = [f"Загрузка процессора: {m['cpu']}%, сэр."]
        if m["top_processes"]:
            names = ", ".join(f"{p['name']} {p['cpu']}%" for p in m["top_processes"])
            lines.append(f"Топ процессы: {names}.")
        return " ".join(lines)

    def get_ram_report(self) -> str:
        m = self.get_metrics()
        return (
            f"Память: {m['ram']}% используется. "
            f"{m['ram_used_gb']} из {m['ram_total_gb']} ГБ, сэр."
        )

    def get_disk_report(self) -> str:
        m = self.get_metrics()
        return (
            f"Диск заполнен на {m['disk']}%. "
            f"Свободно {m['disk_free_gb']} ГБ из {m['disk_total_gb']} ГБ, сэр."
        )

    def get_battery_report(self) -> str:
        m = self.get_metrics()
        if m["battery_pct"] is None:
            return "Батарея не обнаружена — устройство подключено стационарно, сэр."
        status = "заряжается" if m["battery_charging"] else "работает от батареи"
        return f"Заряд батареи: {m['battery_pct']}%, {status}, сэр."

    def get_thermal_report(self) -> str:
        """Report thermal state: exact °C on Intel, pressure level on Apple Silicon."""
        m = self.get_metrics()
        pressure = m.get("thermal_pressure", "Unknown")
        if m["temp"] is not None:
            level = (
                "норма"
                if m["temp"] < 70
                else ("повышенная" if m["temp"] < 85 else "критическая")
            )
            return f"Температура процессора: {m['temp']}°C — {level}, сэр."
        _PRESSURE_RU = {
            "Nominal": "норма, система не греется",
            "Fair": "умеренная нагрузка",
            "Serious": "повышенная нагрузка, возможен троттлинг",
            "Critical": "критическая нагрузка",
            "Unknown": "данные недоступны",
        }
        desc = _PRESSURE_RU.get(pressure, pressure)
        return f"Тепловое давление: {pressure} — {desc}, сэр."

    def get_temp_report(self) -> str:
        """Alias kept for compatibility."""
        return self.get_thermal_report()

    def get_top_processes_report(self) -> str:
        m = self.get_metrics()
        if not m["top_processes"]:
            return "Нет данных о процессах, сэр."
        lines = ["Топ процессы по загрузке CPU, сэр:"]
        for i, p in enumerate(m["top_processes"], 1):
            lines.append(f"{i}. {p['name']} — CPU {p['cpu']}%, RAM {p['ram']}%.")
        return " ".join(lines)


# ── Singleton ─────────────────────────────────────────────────────────────────

monitor = SystemMonitor()

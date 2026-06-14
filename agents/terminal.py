"""Execute macOS commands from natural language — allowlist only, no shell injection."""

import re
import subprocess

# ── Safe predefined commands ──────────────────────────────────────────────────
# Each entry: (pattern, args_list). All calls use list args, no injection.

_SAFE_MAP: list[tuple[re.Pattern, list]] = [
    (re.compile(r"открой?\s+safari", re.I), ["open", "-a", "Safari"]),
    (re.compile(r"открой?\s+chrome", re.I), ["open", "-a", "Google Chrome"]),
    (re.compile(r"открой?\s+firefox", re.I), ["open", "-a", "Firefox"]),
    (re.compile(r"открой?\s+терминал", re.I), ["open", "-a", "Terminal"]),
    (re.compile(r"открой?\s+finder", re.I), ["open", "-a", "Finder"]),
    (
        re.compile(r"открой?\s+(vscode|vs code)", re.I),
        ["open", "-a", "Visual Studio Code"],
    ),
    (re.compile(r"открой?\s+telegram", re.I), ["open", "-a", "Telegram"]),
    (re.compile(r"открой?\s+spotify", re.I), ["open", "-a", "Spotify"]),
    (re.compile(r"открой?\s+музык", re.I), ["open", "-a", "Music"]),
    (re.compile(r"открой?\s+фото", re.I), ["open", "-a", "Photos"]),
    (re.compile(r"открой?\s+калькулятор", re.I), ["open", "-a", "Calculator"]),
    (
        re.compile(r"скриншот", re.I),
        ["screencapture", "-x", "/tmp/jarvis_screenshot.png"],
    ),
    (re.compile(r"заблокируй|блокировка", re.I), ["pmset", "displaysleepnow"]),
    (re.compile(r"спящ|режим сна", re.I), ["pmset", "sleepnow"]),
]


class TerminalAgent:
    name = "terminal"
    icon = "⌘"

    def ask(self, prompt: str) -> str:
        for pattern, args in _SAFE_MAP:
            if pattern.search(prompt):
                return self._run(args)
        return (
            "Не понял команду. Доступные: открой Safari/Chrome/Telegram/Spotify/Finder, "
            "сделай скриншот, заблокируй экран, режим сна."
        )

    def _run(self, args: list) -> str:
        try:
            result = subprocess.run(
                args,  # list — no shell injection possible
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            out = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                return f"Выполнено: {' '.join(args)}" + (f"\n{out}" if out else "")
            return f"Ошибка (код {result.returncode}): {out}"
        except subprocess.TimeoutExpired:
            return "Команда превысила таймаут 10 секунд."
        except Exception as e:
            return f"Не удалось выполнить: {e}"

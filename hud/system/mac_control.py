"""macOS control via AppleScript and subprocess."""
import os
import re
import shlex
import subprocess

# Allowlist: only alphanumeric, spaces, dots, dashes — prevents AppleScript injection
_SAFE_NAME = re.compile(r'^[a-zA-Zа-яёА-ЯЁ0-9 .\-]{1,64}$')

# Command whitelist for execute_terminal_command — first token must be in this set
_CMD_ALLOWLIST: frozenset[str] = frozenset({
    "open", "say", "afplay", "osascript", "screencapture",
    "ls", "pwd", "echo", "date", "uptime", "whoami", "hostname",
    "brew", "pip3", "pip", "python3", "python", "ollama",
    "pmset", "brightness", "caffeinate",
    "which", "type", "env", "printenv",
})

# Hard blocklist — applied even with confirm=False
_BLOCK_PAT = re.compile(
    r'\b(rm\s+-[rf]|mkfs|dd\b|sudo|chmod|chown|format|shred|'
    r':(){:|fork\s+bomb|>\s*/dev/[sh]|curl.*\|\s*[bs]ash|wget.*\|\s*[bs]ash)\b',
    re.I,
)


def _safe_name(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise ValueError(f"Недопустимые символы в имени: {name!r}")
    return name


def run_applescript(script: str) -> str:
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def open_app(app_name: str) -> str:
    try:
        name = _safe_name(app_name)
    except ValueError as e:
        return str(e)
    run_applescript(f'tell application "{name}" to activate')
    return f"Открываю {name}."


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    run_applescript(f'set volume output volume {level}')
    return f"Громкость установлена на {level}%."


def get_volume() -> str:
    vol = run_applescript('output volume of (get volume settings)')
    return f"Текущая громкость: {vol}%."


def set_brightness(level: int) -> str:
    level = max(0, min(100, int(level)))
    subprocess.run(['brightness', str(level / 100)], capture_output=True)
    return f"Яркость установлена на {level}%."


def lock_screen() -> str:
    subprocess.run(['pmset', 'displaysleepnow'], capture_output=True)
    return "Экран заблокирован."


def show_notification(title: str, message: str) -> str:
    script = (
        f'display notification {_as_str(message)} '
        f'with title {_as_str(title)}'
    )
    run_applescript(script)
    return "Уведомление отправлено."


def _as_str(s: str) -> str:
    """Wrap a Python string as a safe AppleScript string literal."""
    escaped = s.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def execute_terminal_command(cmd: str, confirm: bool = True) -> str:
    """
    Runs a shell command only after explicit confirmation AND blocklist check.
    confirm=True → returns CONFIRM_REQUIRED token (no execution).
    confirm=False → executes with shell=False via shlex.split for safety.
    """
    if confirm:
        return f"CONFIRM_REQUIRED:{cmd}"

    if _BLOCK_PAT.search(cmd):
        try:
            from system.security_log import log_command
            log_command(cmd, allowed=False)
        except Exception:
            pass
        return "⛔ Команда заблокирована по соображениям безопасности."

    try:
        args = shlex.split(cmd)
    except ValueError as e:
        return f"Ошибка парсинга команды: {e}"

    if not args:
        return "Пустая команда."

    # Allowlist check — first token must be a known-safe binary
    base_cmd = os.path.basename(args[0]).lower()
    if base_cmd not in _CMD_ALLOWLIST:
        try:
            from system.security_log import log_command
            log_command(cmd, allowed=False)
        except Exception:
            pass
        return f"⛔ Команда «{base_cmd}» не в списке разрешённых, сэр."

    try:
        from system.security_log import log_command
        log_command(cmd, allowed=True)
    except Exception:
        pass

    try:
        result = subprocess.run(
            args,
            shell=False,          # safe: args already split by shlex
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (result.stdout or result.stderr or "Команда выполнена.").strip()
        return out[:500]
    except subprocess.TimeoutExpired:
        return "Команда превысила таймаут 30 секунд."
    except FileNotFoundError:
        return f"Команда не найдена: {args[0]}"
    except Exception as e:
        return f"Ошибка: {e}"

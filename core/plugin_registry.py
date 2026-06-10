"""Plugin architecture for Jarvis — register, discover, and dispatch plugins."""
from __future__ import annotations
import importlib.util
import os
import threading
from typing import Callable

from core.config_paths import PLUGINS_DIR as _PLUGINS_DIR_PATH
_PLUGINS_DIR = str(_PLUGINS_DIR_PATH)
os.makedirs(_PLUGINS_DIR, exist_ok=True)


class Plugin:
    def __init__(
        self,
        name:        str,
        description: str,
        triggers:    list[str],
        handler:     Callable[[str], str],
        version:     str = "1.0",
        author:      str = "system",
    ):
        self.name        = name
        self.description = description
        self.triggers    = [t.lower() for t in triggers]
        self.handler     = handler
        self.version     = version
        self.author      = author
        self.enabled     = True

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "description": self.description,
            "triggers":    self.triggers,
            "enabled":     self.enabled,
            "version":     self.version,
            "author":      self.author,
        }


class PluginManager:
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, plugin: Plugin) -> None:
        with self._lock:
            self._plugins[plugin.name] = plugin
        print(f"[PLUGIN] Registered: {plugin.name} v{plugin.version}")

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._plugins.pop(name, None) is not None

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def find_handler(self, text: str) -> tuple[Callable | None, str | None]:
        """Return (handler_fn, plugin_name) for first matching trigger, or (None, None)."""
        tl = text.lower()
        with self._lock:
            plugins = list(self._plugins.values())
        for plugin in plugins:
            if not plugin.enabled:
                continue
            if any(t in tl for t in plugin.triggers):
                return plugin.handler, plugin.name
        return None, None

    def handle(self, text: str) -> tuple[str | None, str | None]:
        """Run the matched plugin handler. Returns (reply, plugin_name) or (None, None)."""
        fn, name = self.find_handler(text)
        if fn is None:
            return None, None
        try:
            return fn(text), name
        except Exception as e:
            return f"Плагин {name} ошибка: {e}", name

    # ── Management ────────────────────────────────────────────────────────────

    def enable(self, name: str) -> bool:
        with self._lock:
            if name in self._plugins:
                self._plugins[name].enabled = True
                return True
        return False

    def disable(self, name: str) -> bool:
        with self._lock:
            if name in self._plugins:
                self._plugins[name].enabled = False
                return True
        return False

    def list_plugins(self) -> list[dict]:
        with self._lock:
            return [p.to_dict() for p in self._plugins.values()]

    def load_from_file(self, path: str) -> Plugin | None:
        """Dynamically load a plugin from a .py file in the plugins dir (see config_paths.PLUGINS_DIR)."""
        try:
            # Security: only allow files inside the plugins directory.
            # Use os.sep suffix to prevent prefix-collision attacks
            # (e.g. /plugins2/evil.py matching /plugins prefix).
            real_path = os.path.realpath(path)
            real_dir  = os.path.realpath(_PLUGINS_DIR)
            if not real_path.startswith(real_dir + os.sep):
                raise ValueError("Path traversal attempt blocked.")
            if not real_path.endswith(".py"):
                raise ValueError("Only .py files allowed.")

            spec   = importlib.util.spec_from_file_location("_jarvis_plugin", real_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            meta    = getattr(module, "PLUGIN_META", {})
            handler = getattr(module, "handler", None)
            setup   = getattr(module, "setup", None)

            if not callable(handler):
                raise ValueError("Plugin missing handler() function.")

            if callable(setup) and not setup():
                raise ValueError("Plugin setup() returned False.")

            plugin = Plugin(
                name        = meta.get("name",        os.path.basename(path)[:-3]),
                description = meta.get("description", ""),
                triggers    = meta.get("triggers",    []),
                handler     = handler,
                version     = meta.get("version",     "1.0"),
                author      = meta.get("author",      "external"),
            )
            self.register(plugin)
            return plugin
        except Exception as e:
            print(f"[PLUGIN] Failed to load {path}: {e}")
            return None

    def load_directory(self) -> int:
        """Scan the plugins dir and load all .py files (except template.py)."""
        count = 0
        for fname in os.listdir(_PLUGINS_DIR):
            if fname.endswith(".py") and fname != "template.py" and not fname.startswith("_"):
                plugin = self.load_from_file(os.path.join(_PLUGINS_DIR, fname))
                if plugin:
                    count += 1
        return count


# ── Singleton ─────────────────────────────────────────────────────────────────

plugin_manager = PluginManager()


def _register_builtins():
    from agents.browser import smart_search, get_price
    from agents.mac_control import open_app, set_volume

    plugin_manager.register(Plugin(
        name        = "browser_search",
        description = "Поиск в интернете через DuckDuckGo",
        triggers    = ["найди", "поищи", "что такое", "кто такой", "когда был", "нагугли", "погугли"],
        handler     = lambda text: smart_search(
            __import__("re").sub(r"\b(найди|поищи|что такое|кто такой|нагугли|погугли)\s*", "", text, flags=__import__("re").I).strip()
        ),
    ))

    plugin_manager.register(Plugin(
        name        = "price_check",
        description = "Проверка цен на товары",
        triggers    = ["цена", "сколько стоит", "стоимость", "почём"],
        handler     = lambda text: get_price(
            __import__("re").sub(r"\b(цена|сколько стоит|стоимость|почём)\s*", "", text, flags=__import__("re").I).strip()
        ),
    ))

    plugin_manager.register(Plugin(
        name        = "mac_control",
        description = "Управление macOS — открытие приложений",
        triggers    = ["открой", "запусти"],
        handler     = lambda text: open_app(
            __import__("re").sub(r"\b(открой|запусти)\s*", "", text, flags=__import__("re").I).strip().title()
        ),
    ))


_register_builtins()

#!/usr/bin/env python3
"""Jarvis — personal AI assistant.
HTTP + SSE on port 7734 · voice listener · Reasoning Core.
"""

import json
import os
import queue
import re
import secrets as _secrets
import subprocess
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = os.path.dirname(__file__)
sys.path.insert(0, ROOT)

# Load .env if present (keys stay out of config.yaml)
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from agents import (
    ClaudeAgent, GeminiAgent, GroqAgent, XAIAgent,
    WeatherAgent, RSSAgent,
    MorningAgent, TerminalAgent, OllamaAgent,
)
from agents.browser import BrowserAgent
from core.cache import metrics_cache
from core.security import log_auth, log_rate_limit, log_threat, log_input_violation
from core.plugin_registry import plugin_manager
from core.monitor import monitor as _monitor
from core.reasoning import ReasoningCore
from core.router import Router
from connectors.voice import listener
from connectors.voice import speak as _speak_raw, stop as _stop_raw

# ── Config ────────────────────────────────────────────────────────────────────

with open(os.path.join(ROOT, "config.yaml")) as f:
    CONFIG = yaml.safe_load(f)

PORT  = CONFIG["server"]["port"]
VOICE = CONFIG["voice"]["voice"]
RATE  = CONFIG["voice"]["rate"]

# ── Auth token — read from Electron env, generate if running standalone ───────

_TOKEN: str = os.environ.get("JARVIS_TOKEN", "")
if not _TOKEN:
    _TOKEN = _secrets.token_urlsafe(32)
    print(f"[auth] standalone mode — token generated (not logged for security)")

# ── Rate limiting ─────────────────────────────────────────────────────────────

_rl_lock    = threading.Lock()
_rl_windows: dict[str, list[float]] = defaultdict(list)
_RL_WINDOW  = 60.0
_RL_LIMITS  = {"/ask": 20, "/metrics": 120, "/events": 5, "/speak": 10, "/browse": 15, "/monitor/status": 60, "default": 30}


def _rate_ok(ip: str, path: str) -> bool:
    key   = f"{ip}:{path}"
    limit = _RL_LIMITS.get(path, _RL_LIMITS["default"])
    now   = time.monotonic()
    with _rl_lock:
        wins = _rl_windows[key]
        wins[:] = [t for t in wins if now - t < _RL_WINDOW]
        if len(wins) >= limit:
            return False
        wins.append(now)
        return True

# ── Input limits ──────────────────────────────────────────────────────────────

_MAX_TEXT = 2_000   # chars for /ask

# ── Agent usage tracking ──────────────────────────────────────────────────────

_AGENT_LIMITS: dict[str, int | None] = {
    "ollama": None,   # unlimited (local)
    "groq":   14400,  # llama-3.1-8b-instant free tier
    "gemini": 1500,   # gemini-2.5-flash-lite free tier
    "xai":    None,   # credit-based
    "claude": None,   # credit-based
    "system": None,
    "browser": None,
    "mac":    None,
}
_AGENT_ICONS: dict[str, str] = {
    "ollama":  "⬡ OLLAMA",
    "groq":    "⚡ GROQ",
    "gemini":  "◈ GEMINI",
    "xai":     "✕ GROK/xAI",
    "claude":  "◆ CLAUDE",
    "system":  "⊙ SYSTEM",
    "browser": "⬡ BROWSER",
    "mac":     "⊞ MAC",
}

_usage_lock = threading.Lock()
_usage_calls: dict[str, int] = {}
_usage_date  = ""

def _track_call(agent: str):
    global _usage_date
    today = time.strftime("%Y-%m-%d")
    with _usage_lock:
        if today != _usage_date:
            _usage_calls.clear()
            _usage_date = today
        _usage_calls[agent] = _usage_calls.get(agent, 0) + 1
_MAX_BODY = 8_192   # bytes for any POST body

_CTL_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")


def _clean(text: str) -> str:
    """Strip dangerous control chars, enforce length limit."""
    return _CTL_RE.sub("", text)[:_MAX_TEXT]

# ── SSE ───────────────────────────────────────────────────────────────────────

_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def broadcast(data: dict):
    msg = json.dumps(data, ensure_ascii=False)
    with _sse_lock:
        clients = list(_sse_clients)
    dead = []
    for q in clients:
        try:
            q.put_nowait(msg)
        except queue.Full:
            dead.append(q)
    if dead:
        with _sse_lock:
            for q in dead:
                try:
                    _sse_clients.remove(q)
                except ValueError:
                    pass


def set_status(state: str, agent: str = ""):
    broadcast({"type": "status", "state": state, "agent": agent})

# ── TTS ───────────────────────────────────────────────────────────────────────


def speak(text: str):
    set_status("speaking")
    _speak_raw(text, VOICE, RATE)


def stop_speaking():
    _stop_raw()
    set_status("idle")

# ── Build Reasoning Core ──────────────────────────────────────────────────────

def _build_core() -> ReasoningCore:
    lat  = CONFIG["weather"]["lat"]
    lon  = CONFIG["weather"]["lon"]
    city = CONFIG["user"].get("city", "Одесса")

    router = Router(
        morning  = MorningAgent(lat, lon, city, CONFIG.get("news", {}).get("feeds", [])),
        terminal = TerminalAgent(),
        wot      = None,
        ollama   = OllamaAgent(model=CONFIG.get("ollama", {}).get("model", "mistral")),
        weather  = WeatherAgent(lat, lon, city),
        rss      = RSSAgent(feeds=CONFIG.get("news", {}).get("feeds", [])),
        claude   = ClaudeAgent(
            model      = CONFIG.get("claude",  {}).get("model",      "claude-haiku-4-5-20251001"),
            max_tokens = CONFIG.get("claude",  {}).get("max_tokens", 512),
        ),
        gemini   = GeminiAgent(
            model      = CONFIG.get("gemini",  {}).get("model",      "gemini-2.0-flash"),
            max_tokens = CONFIG.get("gemini",  {}).get("max_tokens", 512),
        ),
        groq     = GroqAgent(
            model      = CONFIG.get("groq",    {}).get("model",      "llama-3.1-8b-instant"),
            max_tokens = CONFIG.get("groq",    {}).get("max_tokens", 512),
        ),
        xai      = XAIAgent(
            model      = CONFIG.get("xai",     {}).get("model",      "grok-3-mini"),
            max_tokens = CONFIG.get("xai",     {}).get("max_tokens", 512),
        ),
        browser  = BrowserAgent(),
    )

    def _status_cb(state: str, agent: str = ""):
        set_status(state, agent)
        if agent:
            broadcast({"type": "agent", "agent": agent})

    return ReasoningCore(router=router, on_status=_status_cb)


_core = _build_core()

# ── Metrics ───────────────────────────────────────────────────────────────────


def get_metrics() -> dict:
    cached = metrics_cache.get("metrics")
    if cached:
        return cached

    result = _fetch_metrics()
    metrics_cache.set("metrics", result)
    return result


def _fetch_metrics() -> dict:
    try:
        import psutil
        return {
            "cpu": round(psutil.cpu_percent(interval=0.1), 1),
            "ram": round(psutil.virtual_memory().percent, 1),
        }
    except ImportError:
        pass
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        nums = {}
        for k, p in [
            ("free",     r"Pages free:\s+(\d+)"),
            ("active",   r"Pages active:\s+(\d+)"),
            ("inactive", r"Pages inactive:\s+(\d+)"),
            ("wired",    r"Pages wired down:\s+(\d+)"),
        ]:
            m = re.search(p, vm)
            if m:
                nums[k] = int(m.group(1))
        total = sum(nums.values()) or 1
        used  = nums.get("active", 0) + nums.get("inactive", 0) + nums.get("wired", 0)
        ram   = round(used / total * 100, 1)
        lines = subprocess.run(
            ["ps", "-A", "-o", "%cpu"], capture_output=True, text=True
        ).stdout.splitlines()[1:]
        cpu = min(round(sum(float(x) for x in lines if x.strip()), 1), 100.0)
        return {"cpu": cpu, "ram": ram}
    except Exception:
        return {"cpu": 0, "ram": 0}

# ── HTTP Handler ──────────────────────────────────────────────────────────────


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads     = True
    allow_reuse_address = True


_ALLOWED_ORIGINS = {
    "http://localhost:7734",
    "http://127.0.0.1:7734",
    "null",     # Electron file:// origin
    "file://",
}


class JarvisHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Log path only — no body content (may contain voice transcriptions)
        print(f"[{self.address_string()}] {fmt % args}")

    # ── Security helpers ──────────────────────────────────────────────────────

    def _auth_ok(self) -> bool:
        """Validate X-Jarvis-Token header or ?token= query param (SSE fallback)."""
        tok = self.headers.get("X-Jarvis-Token", "")
        if tok:
            ok = _secrets.compare_digest(tok, _TOKEN)
            if not ok:
                log_auth(False, self.client_address[0], urlparse(self.path).path)
            return ok
        qs    = parse_qs(urlparse(self.path).query)
        param = qs.get("token", [""])[0]
        ok    = bool(param) and _secrets.compare_digest(param, _TOKEN)
        if not ok and param:
            log_auth(False, self.client_address[0], urlparse(self.path).path)
        return ok

    def _rate_ok(self) -> bool:
        path = urlparse(self.path).path
        ok   = _rate_ok(self.client_address[0], path)
        if not ok:
            log_rate_limit(self.client_address[0], path)
        return ok

    def _cors_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        return origin if origin in _ALLOWED_ORIGINS else "http://localhost:7734"

    # ── Response helpers ──────────────────────────────────────────────────────

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return {}
        if n > _MAX_BODY:
            self.rfile.read(n)  # drain to keep connection clean
            log_input_violation(f"body too large: {n} bytes", self.client_address[0])
            return {}
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _deny(self, status: int = 401, msg: str = "unauthorized"):
        self._json({"error": msg}, status)

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        qs   = parse_qs(urlparse(self.path).query)

        # /ping is always public — health check without auth
        if path == "/ping":
            self._json({"status": "ok", "jarvis": "online"})
            return

        if not self._auth_ok():
            self._deny(); return
        if not self._rate_ok():
            self._deny(429, "rate limit exceeded"); return

        if path in ("/", "/hud"):
            with open(os.path.join(ROOT, "ui/hud.html"), encoding="utf-8") as f:
                self._html(f.read())
        elif path == "/metrics":
            self._json(get_metrics())
        elif path == "/mac":
            self._handle_mac_get(qs)
        elif path == "/config":
            obj = CONFIG.get("objective", {})
            self._json({
                "objective": {
                    "label":    obj.get("label", ""),
                    "target":   obj.get("target", 0),
                    "current":  obj.get("current", 0),
                    "currency": obj.get("currency", ""),
                }
            })
        elif path == "/events":
            self._sse()
        elif path == "/morning":
            self._morning()
        elif path == "/speak":
            t = qs.get("text", [""])[0]
            if t:
                speak(_clean(t))
                self._json({"status": "speaking"})
            else:
                self._json({"error": "no text"}, 400)
        elif path == "/stop":
            stop_speaking()
            self._json({"status": "stopped"})
        elif path == "/voice/status":
            self._json({"paused": listener.is_paused(), "disabled": listener.is_disabled()})
        elif path == "/ollama/status":
            from agents.ollama import is_available, list_models
            self._json({"available": is_available(), "models": list_models()})
        elif path == "/memory/stats":
            from core.memory import get_stats
            self._json(get_stats())
        elif path == "/plugins":
            self._json({"plugins": plugin_manager.list_plugins()})
        elif path == "/agents/status":
            from agents.ollama import is_available as _ol_ok
            availability = {
                "ollama":  _ol_ok(),
                "groq":    bool(os.environ.get("GROQ_API_KEY","").strip()),
                "gemini":  bool(os.environ.get("GEMINI_API_KEY","").strip()),
                "xai":     bool(os.environ.get("XAI_API_KEY","").strip()),
                "claude":  CONFIG.get("claude",{}).get("enabled", False),
            }
            today = time.strftime("%Y-%m-%d")
            with _usage_lock:
                calls = dict(_usage_calls) if today == _usage_date else {}
            agents_out = []
            for name, icon in _AGENT_ICONS.items():
                if name in ("system","browser","mac"):
                    continue
                limit = _AGENT_LIMITS.get(name)
                used  = calls.get(name, 0)
                pct   = round(used / limit * 100, 1) if limit else None
                agents_out.append({
                    "name":       name,
                    "icon":       icon,
                    "available":  availability.get(name, False),
                    "calls_today": used,
                    "limit":      limit,
                    "pct":        pct,
                })
            self._json({"agents": agents_out, "date": today})

        elif path == "/monitor/status":
            try:
                # Use background-thread cache if fresh (< 35s); avoids
                # running sudo powermetrics on every 5s HUD poll
                m = _monitor.last_metrics()
                if not m:
                    m = _monitor.get_metrics()
                alerts = _monitor.check_alerts(m)
                self._json({"metrics": m, "alerts": alerts})
            except Exception as e:
                self._json({"error": str(e)}, 500)
        else:
            self._json({"error": "not found"}, 404)

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self):  # noqa: N802
        if not self._auth_ok():
            self._deny(); return
        if not self._rate_ok():
            self._deny(429, "rate limit exceeded"); return

        path = urlparse(self.path).path
        body = self._body()

        if path == "/ask":
            raw  = body.get("text", "")
            text = _clean(raw).strip()
            if not text:
                self._json({"error": "empty text"}, 400)
                return
            resp = _core.process(text)
            _track_call(resp.agent)
            broadcast({"type": "agent", "agent": resp.agent})
            broadcast({"type": "telemetry", "text": f"USR {text[:40]} → AGT {resp.agent}"})
            speak(resp.text)
            # Log to persistent memory
            try:
                from core.memory import log_interaction
                log_interaction(text, resp.text, resp.agent)
            except Exception:
                pass
            self._json({"reply": resp.text, "agent": resp.agent, "intent": resp.intent})

        elif path == "/speak":
            t = _clean(body.get("text", "")).strip()
            if t:
                speak(t)
                self._json({"status": "speaking"})
            else:
                self._json({"error": "no text"}, 400)

        elif path == "/mac":
            self._handle_mac_post(body)

        elif path == "/voice/toggle":
            if listener.is_disabled():
                self._json({"paused": True, "disabled": True, "status": "disabled"})
            else:
                paused = listener.toggle()
                state  = "paused" if paused else "listening"
                set_status(state)
                self._json({"paused": paused, "disabled": False, "status": state})

        elif path == "/browse":
            self._handle_browse(body)

        elif path == "/plugins/toggle":
            name    = body.get("name", "")
            enabled = body.get("enabled")
            if not name:
                self._json({"error": "name required"}, 400); return
            if enabled is True:
                ok = plugin_manager.enable(name)
            elif enabled is False:
                ok = plugin_manager.disable(name)
            else:
                self._json({"error": "enabled must be bool"}, 400); return
            self._json({"ok": ok, "name": name, "enabled": enabled})

        elif path == "/plugins/install":
            filename = body.get("file", "")
            if not filename:
                self._json({"error": "file required"}, 400); return
            import os as _os
            full_path = _os.path.join(_os.path.expanduser("~/jarvis/plugins"), filename)
            plugin = plugin_manager.load_from_file(full_path)
            if plugin:
                self._json({"ok": True, "name": plugin.name})
            else:
                self._json({"error": "failed to load plugin"}, 422)

        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Jarvis-Token")
        self.end_headers()

    # ── SSE ───────────────────────────────────────────────────────────────────

    def _sse(self):
        q: queue.Queue = queue.Queue(maxsize=30)
        with _sse_lock:
            _sse_clients.append(q)
        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.end_headers()
        try:
            while True:
                try:
                    data = q.get(timeout=15)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _sse_lock:
                try:
                    _sse_clients.remove(q)
                except ValueError:
                    pass

    # ── Mac control ───────────────────────────────────────────────────────────

    def _handle_mac_get(self, qs):
        from agents.mac_control import get_volume
        action = qs.get("action", [""])[0]
        if action == "volume":
            self._json({"result": get_volume()})
        else:
            self._json({"error": "unknown action"}, 400)

    def _handle_mac_post(self, body):
        from agents import mac_control as mc
        action = body.get("action", "")
        params = body.get("params", {})
        try:
            if action == "open_app":
                result = mc.open_app(params.get("name", ""))
            elif action == "set_volume":
                result = mc.set_volume(int(params.get("level", 50)))
            elif action == "lock_screen":
                result = mc.lock_screen()
            elif action == "notification":
                result = mc.show_notification(
                    params.get("title", "JARVIS"),
                    _clean(params.get("message", ""))
                )
            elif action == "terminal":
                confirm = params.get("confirm", True)
                result  = mc.execute_terminal_command(
                    _clean(params.get("cmd", "")), confirm
                )
            else:
                self._json({"error": f"unknown action: {action}"}, 400)
                return
            self._json({"result": result})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── Browse ────────────────────────────────────────────────────────────────

    def _handle_browse(self, body: dict):
        from agents.browser import (
            smart_search, get_price, fetch_page, open_url_in_browser,
        )
        action = body.get("action", "search")
        query  = _clean(body.get("query", "")).strip()
        if not query:
            self._json({"error": "empty query"}, 400)
            return

        broadcast({"type": "status",    "state": "searching", "agent": "browser"})
        broadcast({"type": "agent",     "agent": "browser"})
        broadcast({"type": "telemetry", "text":  f"BROWSER · {action.upper()} · {query[:40]}"})

        try:
            if action == "search":
                result = smart_search(query)
            elif action == "price":
                result = get_price(query)
            elif action == "fetch":
                result = fetch_page(query)
            elif action == "open":
                result = open_url_in_browser(query)
            else:
                self._json({"error": f"unknown action: {action}"}, 400)
                return
        except Exception as e:
            result = f"Ошибка браузер-агента: {e}"

        broadcast({"type": "status",    "state": "idle",     "agent": "browser"})
        broadcast({"type": "telemetry", "text":  f"BROWSER · COMPLETE · {len(result)} chars"})
        self._json({"result": result, "action": action, "query": query})

    # ── Morning ───────────────────────────────────────────────────────────────

    def _morning(self):
        resp = _core.process("доброе утро")
        speak(resp.text)
        self._json({"reply": resp.text, "agent": resp.agent})

# ── Voice callback ────────────────────────────────────────────────────────────


def _on_voice(text: str):
    broadcast({"type": "wake",  "text":  text})
    resp = _core.process(text)
    broadcast({"type": "reply", "text":  resp.text, "agent": resp.agent})
    broadcast({"type": "agent", "agent": resp.agent})
    broadcast({"type": "telemetry", "text": f"MIC {text[:40]} → AGT {resp.agent}"})
    try:
        from core.memory import log_interaction
        log_interaction(text, resp.text, resp.agent)
    except Exception:
        pass
    speak(resp.text)

# ── Entry point ───────────────────────────────────────────────────────────────


def main():
    name = CONFIG["user"]["name"]
    print("┌─────────────────────────────────────────┐")
    print("│  J.A.R.V.I.S.  —  Reasoning Core v2    │")
    print(f"│  User : {name:<32}│")
    print(f"│  URL  : http://localhost:{PORT:<15}│")
    print("└─────────────────────────────────────────┘")

    # Always register callback and start — VOICE_ENABLED=False in listener.py makes
    # start() a safe no-op that emits "disabled" to SSE clients and returns immediately.
    listener.on_status(lambda s: set_status(s))
    if not CONFIG["voice"].get("enabled", True):
        print("[voice] disabled in config.yaml")
    listener.start(_on_voice)

    # Greeting on startup
    try:
        from core.proactive import get_time_aware_greeting
        greeting = get_time_aware_greeting()
        threading.Thread(target=speak, args=(greeting,), daemon=True).start()
    except Exception as e:
        print(f"[greeting] {e}")

    # Proactive background thread — checks every 30 min
    def _proactive_loop():
        import time as _t
        while True:
            _t.sleep(1800)
            try:
                from core.proactive import get_proactive_suggestion
                from agents.morning import MorningAgent as _MA
                suggestion = get_proactive_suggestion()
                if suggestion == "morning_brief":
                    resp = _core.process("доброе утро")
                    broadcast({"type": "reply", "text": resp.text, "agent": resp.agent})
                    speak(resp.text)
                elif suggestion == "evening_summary":
                    resp = _core.process("вечерний отчёт")
                    broadcast({"type": "reply", "text": resp.text, "agent": resp.agent})
                    speak(resp.text)
            except Exception as e:
                print(f"[proactive] {e}")
    threading.Thread(target=_proactive_loop, daemon=True).start()

    # ── Ensure Ollama is running ──────────────────────────────────────────
    from agents.ollama import ensure_running as _ollama_ensure
    threading.Thread(target=_ollama_ensure, daemon=True).start()

    # ── System monitor ────────────────────────────────────────────────────────
    def _on_monitor_alert(alert: dict):
        broadcast({"type": "monitor_alert", **alert})
        broadcast({"type": "telemetry",
                   "text": f"SYS {alert['level'].upper()} · {alert['key'].upper()} · {alert['message'][:60]}"})

    _monitor.speaker  = speak
    _monitor.on_alert = _on_monitor_alert
    _monitor.start(interval=CONFIG.get("monitor", {}).get("interval", 30))
    # Warm up metrics cache immediately so HUD shows data on first load
    threading.Thread(target=_monitor.get_metrics, daemon=True).start()

    server = ThreadedHTTPServer((CONFIG["server"]["host"], PORT), JarvisHandler)
    print(f"[HTTP] Listening on :{PORT}  (threaded)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJarvis выключен.")
        _monitor.stop()
        server.server_close()


if __name__ == "__main__":
    main()

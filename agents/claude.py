"""Claude agent — Anthropic SDK with CLI fallback."""
from __future__ import annotations
import os
import subprocess


_SYSTEM_PROMPT = (
    "Ты — JARVIS, персональный ИИ-ассистент Сергея. "
    "Отвечай кратко, по делу, на русском языке. "
    "Обращайся к пользователю «сэр». "
    "Не добавляй лишних вводных фраз. Максимум 3–4 предложения."
)


class ClaudeAgent:
    name = "claude"
    icon = "◆"

    def __init__(self, model: str = "claude-haiku-4-5-20251001", max_tokens: int = 512):
        self.model      = model
        self.max_tokens = max_tokens
        self._client    = None  # lazy init

    def _get_client(self):
        """Lazy-init Anthropic client; returns None if key missing."""
        if self._client is not None:
            return self._client
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return None
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=key)
            return self._client
        except ImportError:
            return None

    def is_available(self) -> bool:
        """True if SDK key is set OR claude CLI exists."""
        if os.environ.get("ANTHROPIC_API_KEY", "").strip():
            return True
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def ask(self, prompt: str) -> str:
        client = self._get_client()
        if client:
            return self._ask_sdk(client, prompt)
        return self._ask_cli(prompt)

    # ── SDK path ──────────────────────────────────────────────────────────────

    def _ask_sdk(self, client, prompt: str) -> str:
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            return f"Ошибка Claude API: {e}"

    # ── CLI fallback ──────────────────────────────────────────────────────────

    def _ask_cli(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                ["claude", "--print"],
                input=prompt, capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or "неизвестная ошибка"
                return f"Ошибка Claude CLI: {err}"
            return result.stdout.strip()
        except FileNotFoundError:
            return "Claude недоступен: установите CLI или добавьте ANTHROPIC_API_KEY в .env"
        except subprocess.TimeoutExpired:
            return "Claude не ответил за 30 секунд, сэр."
        except Exception as e:
            return f"Ошибка Claude CLI: {e}"

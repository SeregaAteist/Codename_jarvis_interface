"""xAI agent — Grok models via OpenAI-compatible API.

Free credits: $25/month on new accounts (x.ai/api)
Models: grok-3-mini (fast/cheap), grok-3 (smart), grok-2 (stable)
"""

from __future__ import annotations

import os

_SYSTEM_PROMPT = (
    "Ты — JARVIS, персональный ИИ-ассистент Сергея. "
    "Отвечай кратко, по делу, на русском языке. "
    "Обращайся к пользователю «сэр». "
    "Максимум 3–4 предложения."
)

_BASE_URL = "https://api.x.ai/v1"
_DEFAULT_MODEL = "grok-3-mini"


class XAIAgent:
    name = "xai"
    icon = "✕ GROK"

    def __init__(self, model: str = _DEFAULT_MODEL, max_tokens: int = 512):
        self.model = model
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        key = os.environ.get("XAI_API_KEY", "").strip()
        if not key:
            return None
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=key, base_url=_BASE_URL)
            return self._client
        except Exception:
            return None

    def is_available(self) -> bool:
        return bool(os.environ.get("XAI_API_KEY", "").strip())

    def ask(self, prompt: str) -> str:
        client = self._get_client()
        if not client:
            return "XAI_API_KEY не задан в .env, сэр."
        try:
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"Ошибка xAI API: {e}"

"""Groq agent — ultra-fast inference (free tier: ~14 400 req/day llama3).

Models (free):
  llama-3.1-8b-instant  — fastest,  14 400 req/day
  llama-3.3-70b-versatile — smarter, 1 000 req/day
  mixtral-8x7b-32768    — balanced, 14 400 req/day
"""

from __future__ import annotations

import os

_SYSTEM_PROMPT = (
    "Ты — JARVIS, персональный ИИ-ассистент Сергея. "
    "Отвечай кратко, по делу, на русском языке. "
    "Обращайся к пользователю «сэр». "
    "Максимум 3–4 предложения."
)

_DEFAULT_MODEL = "llama-3.1-8b-instant"


class GroqAgent:
    name = "groq"
    icon = "⚡ GROQ"

    def __init__(self, model: str = _DEFAULT_MODEL, max_tokens: int = 512):
        self.model = model
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            return None
        try:
            from groq import Groq

            self._client = Groq(api_key=key)
            return self._client
        except Exception:
            return None

    def is_available(self) -> bool:
        return bool(os.environ.get("GROQ_API_KEY", "").strip())

    def ask(self, prompt: str) -> str:
        client = self._get_client()
        if not client:
            return "GROQ_API_KEY не задан в .env, сэр."
        try:
            chat = client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            return chat.choices[0].message.content.strip()
        except Exception as e:
            return f"Ошибка Groq API: {e}"

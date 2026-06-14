"""Gemini agent — google-genai SDK with model fallback chain."""

from __future__ import annotations

import os

from core.models import GEMINI_MODEL

_SYSTEM_PROMPT = (
    "Ты — JARVIS, персональный ИИ-ассистент Сергея. "
    "Отвечай кратко, по делу, на русском языке. "
    "Обращайся к пользователю «сэр». "
    "Максимум 3–4 предложения."
)

# Tried in order; first to succeed wins
_FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]

_DEFAULT_MODEL = GEMINI_MODEL


class GeminiAgent:
    name = "gemini"
    icon = "◈ GEMINI"

    def __init__(self, model: str = _DEFAULT_MODEL, max_tokens: int = 512):
        self.model = model
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            return None
        try:
            from google import genai

            self._client = genai.Client(api_key=key)
            return self._client
        except Exception:
            return None

    def is_available(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())

    def ask(self, prompt: str) -> str:
        client = self._get_client()
        if not client:
            return "GEMINI_API_KEY не задан в .env, сэр."

        from google.genai import types

        cfg = types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            max_output_tokens=self.max_tokens,
        )

        # Build fallback list: configured model first, then the rest
        models = [self.model] + [m for m in _FALLBACK_MODELS if m != self.model]
        last_err = ""
        for model in models:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=cfg,
                )
                return resp.text.strip()
            except Exception as e:
                last_err = str(e)
                # Only retry on transient errors (503) or quota (429)
                code = getattr(e, "status_code", None) or (
                    503 if "503" in last_err else (429 if "429" in last_err else 0)
                )
                if code not in (429, 503):
                    break

        return f"Ошибка Gemini API: {last_err[:120]}"

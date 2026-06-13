"""DocParser — извлечение знаний из документов через Gemini."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DocParser:
    """Читает PDF/Word/Excel и извлекает структурированные знания."""

    async def parse_url(self, url: str) -> str:
        """Скачать документ по URL и извлечь текст через Gemini."""
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(url)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")

        suffix = ".pdf" if "pdf" in content_type else ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(r.content)
            tmp_path = f.name

        try:
            return await self._extract_with_gemini(Path(tmp_path))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def parse_file(self, path: Path) -> str:
        """Извлечь текст из локального файла через Gemini."""
        return await self._extract_with_gemini(path)

    async def _extract_with_gemini(self, path: Path) -> str:
        """Gemini нативно читает PDF и извлекает структурированный текст."""
        import google.generativeai as genai

        from shared.llm.router import get_router

        router = get_router()
        key: str = router._gemini_pool.get_key()  # type: ignore[attr-defined]

        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        uploaded = genai.upload_file(str(path))
        prompt = """Извлеки из документа структурированную информацию:
1. Технические характеристики (если есть)
2. Схемы подключения и порты
3. Сервисные интервалы и регламент обслуживания
4. Типичные ошибки и их коды
5. Настройки и конфигурация

Формат: структурированный текст с разделами. Язык оригинала."""

        response = model.generate_content([prompt, uploaded])
        result: str = response.text
        return result

    async def extract_equipment_card(
        self, url: str, brand: str, model: str
    ) -> dict[str, Any]:
        """Извлечь данные для карточки оборудования из мануала."""
        text = await self.parse_url(url)

        from shared.llm.router import get_router

        router = get_router()

        prompt = f"""На основе этого мануала создай карточку оборудования в YAML формате.

Мануал:
{text[:10000]}

Нужно извлечь:
- specs: технические характеристики (мощность, напряжение, токи, порты)
- service_intervals: сервисные интервалы (месяцы и действия)
- compatible_with: совместимое оборудование

Верни только YAML без пояснений."""

        yaml_text = await router.generate("quality", prompt)
        import yaml

        try:
            result: dict[str, Any] = yaml.safe_load(yaml_text)
            return result
        except Exception:
            return {"raw": yaml_text}

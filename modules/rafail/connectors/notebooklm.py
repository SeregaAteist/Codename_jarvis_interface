"""NotebookLM connector (RF-4).

У NotebookLM нет публичного API. Паттерн: Drive-папки подключены к
ноутбукам как источники — заливаем файл в нужную папку, NotebookLM
подхватывает при синхронизации источников.

.env:
    NOTEBOOKLM_SES_FOLDER_ID=
    NOTEBOOKLM_SALES_FOLDER_ID=
    NOTEBOOKLM_ENERGY_FOLDER_ID=
"""

from __future__ import annotations

import logging
import time

from modules.rafail.connectors.drive import DriveConnector
from shared.config.secrets import opt

logger = logging.getLogger(__name__)

_DOMAIN_ENV = {
    "ses": "NOTEBOOKLM_SES_FOLDER_ID",
    "sales": "NOTEBOOKLM_SALES_FOLDER_ID",
    "energy": "NOTEBOOKLM_ENERGY_FOLDER_ID",
}


class NotebookLMConnector:
    def __init__(self, drive: DriveConnector | None = None):
        self.drive = drive or DriveConnector()
        self.folders = {d: opt(env) for d, env in _DOMAIN_ENV.items()}

    def folder_for(self, domain: str) -> str:
        """ID Drive-папки NotebookLM для домена ('' если не настроена)."""
        return self.folders.get(domain, "")

    def is_configured(self, domain: str) -> bool:
        return bool(self.folder_for(domain))

    async def push(self, domain: str, title: str, content: str) -> dict:
        """Залить материал в NotebookLM-папку домена.

        Имя файла: YYYY-MM-DD_<title>.md — хронологическая сортировка
        источников в ноутбуке.
        """
        folder_id = self.folder_for(domain)
        if not folder_id:
            raise RuntimeError(
                f"NotebookLM: папка для домена '{domain}' не задана — "
                f"добавьте {_DOMAIN_ENV.get(domain, 'NOTEBOOKLM_*_FOLDER_ID')} в .env"
            )
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[
            :80
        ]
        filename = f"{time.strftime('%Y-%m-%d')}_{safe_title}.md"
        res = await self.drive.upload_file(content, filename, folder_id)
        logger.info("[NotebookLM] %s → %s (%s)", filename, domain, res.get("id"))
        return res

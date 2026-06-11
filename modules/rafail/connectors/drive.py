"""DriveConnector — Google Drive API v3 (RF-3).

Автономный доступ (без Claude MCP): service account JSON, путь в .env:
    GOOGLE_SA_JSON=/path/to/service-account.json

Папки/доки должны быть расшарены на email сервисного аккаунта (Viewer/Editor).
Google-клиент синхронный — все вызовы обёрнуты в asyncio.to_thread.
"""
from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path

from shared.config.secrets import opt

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive"]

# Google Docs → экспорт в текст; остальное скачиваем как есть
_EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class DriveConnector:
    FOLDER_IDS = {
        "moodle_root":    "1AsasJyrCVSsISI6q0kRI-oROj_imYdt-",
        "course_ses":     "1xSSn_XWVJPCsgRXKkyZ8QPdaJUHPoADF",
        "section_admin":  "1-mR-fTWH5UBqpBMzVv8rkLaz6g_Jdy3Y",
        "section_start":  "1k65M1KPNZvmdiZ95WaeWYTRze2eck9VM",
        "section_market": "1syqofeMd_AxsHzfU7fGKF34BPB0m5GqU",
        "section_ses":    "1jI9NPpXlQWWL8mTY1GufKCzOnNg7HDn_",
        "section_equip":  "1JBu91CuVnNvB1vwOOgsdvDRUqVTAikHZ",
        "section_client": "1rZCNDdfBE9hUkZMPhOp9ruxRESvLcBtX",
        "section_funnel": "13P7N-D5WmQVi5NC5G_xslH5nodQKw0gH",
        "section_finance":"1Z8lLouJXK8hOsvZy4Whd9rkKZOkl7ZE_",
        "section_crm":    "1wNguoBroX1E0-cV9KtXwt0cZ52t3FB2X",
        "section_epc":    "10ZBtIgHnlZio_NKm--sVCpbfh6SPIhRM",
        "section_after":  "1DBsuIksfLkLKetsoE5hQudU1rHnAcNk4",
        "kb_v2":          "1uowsvJTxFLFw3N6CTWOOif0baDMcwIGBpjDe-8uybHo",
        "template":       "14DLRd4HIRRK41UQdQEDhIrd9l7ZIxztAScTnFAdDhs0",
    }

    def __init__(self, sa_json: str = ""):
        self._sa_json = sa_json or opt("GOOGLE_SA_JSON")
        self._svc = None

    # ── транспорт ─────────────────────────────────────────────────────────────

    def _service(self):
        """Ленивая инициализация Drive API клиента (требует GOOGLE_SA_JSON)."""
        if self._svc is not None:
            return self._svc
        if not self._sa_json or not Path(self._sa_json).exists():
            raise RuntimeError(
                "DriveConnector: задайте GOOGLE_SA_JSON в .env (путь к service account JSON) "
                "и расшарьте папки на email сервисного аккаунта"
            )
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            self._sa_json, scopes=_SCOPES
        )
        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._svc

    # ── операции ──────────────────────────────────────────────────────────────

    async def read_file(self, file_id: str) -> str:
        """Содержимое файла: Google Docs экспортируются в текст."""
        return await asyncio.to_thread(self._read_file_sync, file_id)

    def _read_file_sync(self, file_id: str) -> str:
        from googleapiclient.http import MediaIoBaseDownload

        svc = self._service()
        meta = svc.files().get(fileId=file_id, fields="mimeType,name").execute()
        mime = meta["mimeType"]

        if mime in _EXPORT_MIME:
            req = svc.files().export_media(fileId=file_id, mimeType=_EXPORT_MIME[mime])
        else:
            req = svc.files().get_media(fileId=file_id)

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")

    async def list_folder(self, folder_id: str) -> list[dict]:
        """Файлы папки: [{id, name, mimeType, modifiedTime}]."""
        return await asyncio.to_thread(self._list_folder_sync, folder_id)

    def _list_folder_sync(self, folder_id: str) -> list[dict]:
        svc = self._service()
        files: list[dict] = []
        token = None
        while True:
            res = svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
                pageSize=100,
                pageToken=token,
            ).execute()
            files.extend(res.get("files", []))
            token = res.get("nextPageToken")
            if not token:
                return files

    async def upload_file(self, content: str, filename: str, folder_id: str) -> dict:
        """Загрузка текстового файла в папку. Возвращает {id, name}."""
        return await asyncio.to_thread(self._upload_sync, content, filename, folder_id)

    def _upload_sync(self, content: str, filename: str, folder_id: str) -> dict:
        from googleapiclient.http import MediaIoBaseUpload

        svc = self._service()
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")), mimetype="text/plain", resumable=False
        )
        return svc.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id,name",
        ).execute()

    async def search(self, query: str) -> list[dict]:
        """Полнотекстовый поиск по Drive."""
        return await asyncio.to_thread(self._search_sync, query)

    def _search_sync(self, query: str) -> list[dict]:
        svc = self._service()
        safe = query.replace("'", "\\'")
        res = svc.files().list(
            q=f"fullText contains '{safe}' and trashed=false",
            fields="files(id,name,mimeType,modifiedTime)",
            pageSize=50,
        ).execute()
        return res.get("files", [])

    # ── шорткаты ──────────────────────────────────────────────────────────────

    async def read_kb_v2(self) -> str:
        return await self.read_file(self.FOLDER_IDS["kb_v2"])

    async def read_template(self) -> str:
        return await self.read_file(self.FOLDER_IDS["template"])

    def is_configured(self) -> bool:
        return bool(self._sa_json) and Path(self._sa_json).exists()

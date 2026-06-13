"""ProfileManager — управление профилями компаний."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent.parent / "profiles"


class CompanyProfile:
    """Профиль компании."""

    def __init__(self, profile_id: str, data: dict[str, Any]) -> None:
        self.id = profile_id
        self.name: str = data.get("name", "")
        self.language: str = data.get("language", "uk")
        self.directions: list[dict[str, Any]] = data.get("directions", [])
        self.active_role: str = data.get("active_role", "trainee")
        self.active_dept: str = data.get("active_dept", "sales")
        self.knowledge_base: dict[str, Any] = data.get("knowledge_base", {})
        self.equipment_dir: Path = (
            PROFILES_DIR / profile_id / data.get("equipment_registry", "equipment/")
        )
        self._raw = data

    @classmethod
    def load(cls, profile_id: str) -> CompanyProfile:
        path = PROFILES_DIR / profile_id / "company.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Профиль не найден: {profile_id}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(profile_id, data)

    def save(self) -> None:
        path = PROFILES_DIR / self.id / "company.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(self._raw, allow_unicode=True), encoding="utf-8")


class ProfileManager:
    """Менеджер профилей компаний."""

    def __init__(self) -> None:
        self._active: CompanyProfile | None = None

    def list_profiles(self) -> list[str]:
        return [
            p.name
            for p in PROFILES_DIR.iterdir()
            if p.is_dir() and not p.name.startswith("_")
        ]

    def load(self, profile_id: str) -> CompanyProfile:
        self._active = CompanyProfile.load(profile_id)
        logger.info("[profile] загружен: %s", profile_id)
        return self._active

    @property
    def active(self) -> CompanyProfile:
        if self._active is None:
            self._active = CompanyProfile.load("lk_energy")
        return self._active

    def create(
        self, profile_id: str, name: str, direction: str, kb_type: str = "moodle"
    ) -> CompanyProfile:
        """Создать новый профиль компании."""
        data = {
            "name": name,
            "language": "uk",
            "directions": [{"name": direction, "priority": 1}],
            "knowledge_base": {"primary": kb_type, "url": "", "token_env": ""},
            "active_role": "trainee",
            "active_dept": "sales",
            "equipment_registry": "equipment/",
        }
        profile = CompanyProfile(profile_id, data)
        profile.save()
        logger.info("[profile] создан: %s", profile_id)
        return profile


_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager

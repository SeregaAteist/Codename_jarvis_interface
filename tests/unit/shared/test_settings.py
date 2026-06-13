"""Тесты для shared/config/settings.py."""

from __future__ import annotations


def test_settings_loads() -> None:
    from shared.config.settings import get_settings

    s = get_settings()
    assert s.owner_user_id == 374728252
    assert s.kommo_domain == "lkenergy.kommo.com"
    assert s.rafail_topic_id == 205
    assert s.work_topic_id == 202


def test_settings_singleton() -> None:
    from shared.config.settings import get_settings

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_field_types() -> None:
    from shared.config.settings import get_settings

    s = get_settings()
    assert isinstance(s.owner_user_id, int)
    assert isinstance(s.rafail_chat_id, int)
    assert isinstance(s.gemini_keys, str)
    assert isinstance(s.kommo_domain, str)


def test_get_gemini_keys_parses_csv() -> None:
    from shared.config.settings import JarvisSettings

    s = JarvisSettings(gemini_keys="key1,key2, key3")
    assert s.get_gemini_keys() == ["key1", "key2", "key3"]


def test_get_gemini_keys_empty() -> None:
    from shared.config.settings import JarvisSettings

    s = JarvisSettings(gemini_keys="")
    assert s.get_gemini_keys() == []

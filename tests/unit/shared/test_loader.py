"""Тесты для shared/config/loader.py."""

from __future__ import annotations

from unittest.mock import patch

import yaml


def _reload_loader():
    import shared.config.loader as m

    m.load.cache_clear()
    return m


def test_load_returns_dict(tmp_path):
    jarvis_yaml = tmp_path / "jarvis.yaml"
    jarvis_yaml.write_text(yaml.dump({"ports": {"api": 7734}, "services": {}}))
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()

    loader = _reload_loader()
    with (
        patch.object(loader, "CONFIG_PATH", jarvis_yaml),
        patch.object(loader, "MODULES_DIR", modules_dir),
    ):
        loader.load.cache_clear()
        result = loader.load()

    assert result["ports"]["api"] == 7734
    assert "services" in result


def test_load_merges_module_yamls(tmp_path):
    jarvis_yaml = tmp_path / "jarvis.yaml"
    jarvis_yaml.write_text(yaml.dump({"services": {"kommo": {"token": "override"}}}))
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    (modules_dir / "kommo.yaml").write_text(
        yaml.dump({"domain": "lkenergy.kommo.com", "token": "original"})
    )

    loader = _reload_loader()
    with (
        patch.object(loader, "CONFIG_PATH", jarvis_yaml),
        patch.object(loader, "MODULES_DIR", modules_dir),
    ):
        loader.load.cache_clear()
        result = loader.load()

    # jarvis.yaml перезаписывает модульный конфиг
    assert result["services"]["kommo"]["token"] == "override"
    assert result["services"]["kommo"]["domain"] == "lkenergy.kommo.com"


def test_load_empty_yaml(tmp_path):
    jarvis_yaml = tmp_path / "jarvis.yaml"
    jarvis_yaml.write_text("")
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()

    loader = _reload_loader()
    with (
        patch.object(loader, "CONFIG_PATH", jarvis_yaml),
        patch.object(loader, "MODULES_DIR", modules_dir),
    ):
        loader.load.cache_clear()
        result = loader.load()

    assert isinstance(result, dict)
    assert "services" in result


def test_get_nested_key(tmp_path):
    jarvis_yaml = tmp_path / "jarvis.yaml"
    jarvis_yaml.write_text(yaml.dump({"ports": {"api": 7734, "mcp": 7735}}))
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()

    loader = _reload_loader()
    with (
        patch.object(loader, "CONFIG_PATH", jarvis_yaml),
        patch.object(loader, "MODULES_DIR", modules_dir),
    ):
        loader.load.cache_clear()
        assert loader.get("ports.api") == 7734
        assert loader.get("ports.mcp") == 7735
        assert loader.get("ports.missing", 0) == 0


def test_get_missing_key_returns_default(tmp_path):
    jarvis_yaml = tmp_path / "jarvis.yaml"
    jarvis_yaml.write_text(yaml.dump({"a": {"b": "val"}}))
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()

    loader = _reload_loader()
    with (
        patch.object(loader, "CONFIG_PATH", jarvis_yaml),
        patch.object(loader, "MODULES_DIR", modules_dir),
    ):
        loader.load.cache_clear()
        assert loader.get("x.y.z", "default") == "default"
        assert loader.get("a.b") == "val"
        assert loader.get("a.b.c", "fallback") == "fallback"

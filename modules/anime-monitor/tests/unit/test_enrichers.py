"""БЛОК 3: реестр обогатителей — BaseEnricher, ENRICHERS_ENABLED, Kitsu-заглушка."""
from agents.anilist_agent import AniListEnricher
from agents.base_enricher import BaseEnricher
from agents.jikan_agent import JikanEnricher
from agents.kitsu_agent import KitsuEnricher


def test_all_inherit_base():
    for cls in (AniListEnricher, JikanEnricher, KitsuEnricher):
        assert issubclass(cls, BaseEnricher)
        assert cls.name != "base"


def test_priority_order():
    enrichers = sorted(
        [JikanEnricher(), KitsuEnricher(), AniListEnricher()],
        key=lambda e: e.priority,
    )
    assert [e.name for e in enrichers] == ["anilist", "jikan", "kitsu"]


def test_env_toggle(monkeypatch):
    """Отключение агента через ENRICHERS_ENABLED — без правок кода."""
    from config import cfg
    import main as main_mod

    monkeypatch.setattr(cfg, "ENRICHERS_ENABLED", ["jikan"])
    active = main_mod.active_enrichers()
    assert [e.name for e in active] == ["jikan"]

    monkeypatch.setattr(cfg, "ENRICHERS_ENABLED", ["anilist", "jikan", "kitsu"])
    assert [e.name for e in main_mod.active_enrichers()] == ["anilist", "jikan", "kitsu"]


async def test_kitsu_stub_does_not_break():
    items = [{"title": "X"}]
    out = await KitsuEnricher().enrich(items)
    assert out == items   # заглушка возвращает как есть

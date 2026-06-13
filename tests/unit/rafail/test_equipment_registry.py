import tempfile
from pathlib import Path

from modules.rafail.registry.equipment_registry import (
    EquipmentCard,
    EquipmentRegistry,
    ServiceInterval,
)


def test_save_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        reg = EquipmentRegistry(Path(tmp))
        card = EquipmentCard(
            model="SUN-10K-SG04LP3-EU",
            brand="Deye",
            category="inverter_hybrid",
            service_intervals=[ServiceInterval(months=12, action="Чистка")],
        )
        path = reg.save(card)
        assert path.exists()

        loaded = reg.get("deye", "sun-10k-sg04lp3-eu")
        assert loaded is not None
        assert loaded.model == "SUN-10K-SG04LP3-EU"
        assert loaded.service_intervals[0].months == 12


def test_search():
    with tempfile.TemporaryDirectory() as tmp:
        reg = EquipmentRegistry(Path(tmp))
        card = EquipmentCard(
            model="SUN-10K-SG04LP3-EU", brand="Deye", category="inverter_hybrid"
        )
        reg.save(card)
        results = reg.search("deye")
        assert len(results) == 1

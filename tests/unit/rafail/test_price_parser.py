import pytest

from modules.rafail.researchers.price_parser import PriceItem, PriceParser


@pytest.fixture
def parser():
    return PriceParser()


def test_price_item_detect_brand():
    item = PriceItem(name="Deye SUN-10K-SG04LP3-EU інвертор")
    item.detect_brand()
    assert item.brand == "Deye"


def test_price_item_detect_category_inverter():
    item = PriceItem(name="Інвертор Deye 10кВт")
    item.detect_category()
    assert item.category == "inverter"


def test_price_item_detect_category_battery():
    item = PriceItem(name="Pylontech US5000 акумулятор")
    item.detect_category()
    assert item.category == "battery"


def test_price_item_detect_category_panel():
    item = PriceItem(name="JA Solar 550W панель сонячна")
    item.detect_category()
    assert item.category == "panel"


def test_price_item_unknown_category():
    item = PriceItem(name="Щось незрозуміле")
    item.detect_category()
    assert item.category == "other"


def test_to_equipment_cards_skips_unknown(parser):
    items = [
        PriceItem(name="test", brand="", category="other", price=100),
        PriceItem(name="Deye SUN-10K", brand="Deye", category="inverter", price=45000),
    ]
    cards = parser.to_equipment_cards(items)
    assert len(cards) == 1
    assert cards[0].brand == "Deye"

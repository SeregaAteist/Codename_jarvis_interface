from unittest.mock import AsyncMock, patch

import pytest

from modules.rafail.researchers.price_parser import KPParser, PriceItem, PriceParser


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


def test_price_item_no_brand():
    item = PriceItem(name="Невідомий пристрій XYZ")
    item.detect_brand()
    assert item.brand == ""


def test_price_item_detect_category_cable():
    item = PriceItem(name="Кабель мідний 4мм 100м")
    item.detect_category()
    assert item.category == "cable"


def test_price_item_detect_category_switch():
    item = PriceItem(name="Автоматичний вимикач ABB 63A")
    item.detect_category()
    assert item.category == "switch"


# ── KPParser тесты ────────────────────────────────────────────────────────────


@pytest.fixture
def kp_parser():
    return KPParser()


@pytest.mark.asyncio
async def test_kp_parser_parse_kp_valid_json(kp_parser):
    valid_json = """{
        "power_kw": 10,
        "inverter": {"brand": "Deye", "model": "SUN-10K", "qty": 1},
        "panels": {"brand": "JA Solar", "model": "JAM72S20", "power_w": 550, "qty": 18},
        "batteries": [{"brand": "Pylontech", "model": "US5000", "capacity_kwh": 9.6, "qty": 2}],
        "total_price": 450000,
        "currency": "UAH",
        "client_type": "residential",
        "location": "Одеса",
        "notes": ""
    }"""
    with patch("shared.llm.router.get_router") as mock_router:
        mock_router.return_value.generate = AsyncMock(return_value=valid_json)
        result = await kp_parser.parse_kp("Комерційна пропозиція: Deye 10кВт")
    assert result["power_kw"] == 10
    assert result["inverter"]["brand"] == "Deye"
    assert result["total_price"] == 450000


@pytest.mark.asyncio
async def test_kp_parser_parse_kp_with_code_block(kp_parser):
    wrapped = '```json\n{"power_kw": 5, "currency": "UAH", "total_price": 200000}\n```'
    with patch("shared.llm.router.get_router") as mock_router:
        mock_router.return_value.generate = AsyncMock(return_value=wrapped)
        result = await kp_parser.parse_kp("КП тест")
    assert result["power_kw"] == 5


@pytest.mark.asyncio
async def test_kp_parser_parse_kp_invalid_json(kp_parser):
    with patch("shared.llm.router.get_router") as mock_router:
        mock_router.return_value.generate = AsyncMock(return_value="не JSON відповідь")
        result = await kp_parser.parse_kp("КП тест")
    assert result == {}


@pytest.mark.asyncio
async def test_kp_parser_parse_kp_truncates_content(kp_parser):
    long_content = "x" * 10000
    captured = []

    async def capture_generate(mode, prompt):
        captured.append(prompt)
        return '{"power_kw": 0, "currency": "UAH"}'

    with patch("shared.llm.router.get_router") as mock_router:
        mock_router.return_value.generate = capture_generate
        await kp_parser.parse_kp(long_content)

    assert "x" * 5000 in captured[0]
    assert "x" * 5001 not in captured[0]


@pytest.mark.asyncio
async def test_kp_parser_create_case_study(kp_parser):
    kp_data = {"power_kw": 10, "inverter": {"brand": "Deye"}, "total_price": 400000}
    expected = "## Кейс: Приватний будинок 10кВт"
    with patch("shared.llm.router.get_router") as mock_router:
        mock_router.return_value.generate = AsyncMock(return_value=expected)
        result = await kp_parser.create_case_study(kp_data, result="Клієнт задоволений")
    assert result == expected


@pytest.mark.asyncio
async def test_kp_parser_create_case_study_no_result(kp_parser):
    with patch("shared.llm.router.get_router") as mock_router:
        mock_router.return_value.generate = AsyncMock(return_value="## Кейс: Тест")
        result = await kp_parser.create_case_study({"power_kw": 5})
    assert "Кейс" in result

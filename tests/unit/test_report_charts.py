import re
from copy import deepcopy
from decimal import Decimal
from html.parser import HTMLParser
from xml.etree import ElementTree

import pytest

from retail_pipeline.report_charts import product_mix, sales_trend, store_ranking


class _Elements(HTMLParser):
    def __init__(self, markup: str) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.feed(markup)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


def _attributes(markup: str, attribute: str, tag: str | None = None) -> list[dict[str, str | None]]:
    return [
        attrs
        for name, attrs in _Elements(markup).elements
        if attribute in attrs and (tag is None or name == tag)
    ]


def _svg(markup: str) -> ElementTree.Element:
    match = re.search(r"<svg\b.*?</svg>", markup, re.DOTALL)
    assert match is not None
    return ElementTree.fromstring(match.group())


def test_single_day_is_a_centered_column_with_exact_revenue_and_accessible_description() -> None:
    chart = sales_trend([{"business_date": "2026-01-01", "net_revenue_brl": "104.00"}])
    svg = _svg(chart)
    bars = svg.findall("rect")
    assert len(bars) == 1
    assert Decimal(bars[0].get("x", "0")) + Decimal(bars[0].get("width", "0")) / 2 == 300
    assert bars[0].get("data-value-raw") == "104.00"
    assert bars[0].findtext("title") == "01/01/2026: R$ 104,00"
    assert svg.get("role") == "img"
    assert svg.get("height") == "240"
    assert "01/01/2026: R$ 104,00" in (svg.findtext("desc") or "")
    assert svg.findall("polyline") == []
    assert "01/01/2026</span>" in chart


def test_days_are_sorted_and_missing_dates_keep_their_position_without_a_zero() -> None:
    chart = sales_trend(
        [
            {"business_date": "2026-01-03", "net_revenue_brl": "30.00"},
            {"business_date": "2026-01-01", "net_revenue_brl": "10.00"},
            {"business_date": "2026-01-02", "net_revenue_brl": None},
        ]
    )
    bars = _svg(chart).findall("rect")
    assert [bar.get("data-chart-date") for bar in bars] == ["2026-01-01", "2026-01-03"]
    assert Decimal(bars[1].get("x", "0")) - Decimal(bars[0].get("x", "0")) > 300
    assert "Datas sem observação não representam receita zero" in chart
    assert 'data-chart-date="2026-01-02"' not in chart


def test_zero_is_a_real_marker_and_negative_revenue_extends_below_the_zero_axis() -> None:
    svg = _svg(
        sales_trend(
            [
                {"business_date": "2026-01-01", "net_revenue_brl": "0.00"},
                {"business_date": "2026-01-02", "net_revenue_brl": "-12.34"},
                {"business_date": "2026-01-03", "net_revenue_brl": "20.00"},
            ]
        )
    )
    zero = next(
        line for line in svg.findall("line") if line.get("class") == "sales-trend-zero-line"
    )
    marker = next(line for line in svg.findall("line") if line.get("data-sign") == "zero")
    negative = next(bar for bar in svg.findall("rect") if bar.get("data-sign") == "negative")
    assert marker.get("data-value-raw") == "0.00"
    assert marker.get("y1") == zero.get("y1")
    assert negative.get("y") == zero.get("y1")
    assert Decimal(negative.get("height", "0")) > 0
    assert negative.findtext("title") == "02/01/2026: R$ -12,34"


def test_duplicate_dates_do_not_silently_add_a_new_daily_total() -> None:
    chart = sales_trend(
        [
            {"business_date": "2026-01-01", "net_revenue_brl": "10.00"},
            {"business_date": "2026-01-01", "net_revenue_brl": "20.00"},
            {"business_date": "2026-01-02", "net_revenue_brl": "5.00"},
        ]
    )
    assert [bar["data-chart-date"] for bar in _attributes(chart, "data-chart-date")] == [
        "2026-01-02"
    ]
    assert "Datas sem observação" in chart


@pytest.mark.parametrize("value", [None, "NaN", "Infinity", "not-money", True])
def test_unavailable_numbers_never_become_zero(value: object) -> None:
    assert "<svg" not in sales_trend([{"business_date": "2026-01-01", "net_revenue_brl": value}])
    assert "<ol" not in store_ranking([{"store_id": "S01", "net_revenue_brl": value}])
    mix = product_mix([{"product_id": "P01", "units": value}])
    assert "data-units-raw" not in mix
    assert "data-share-denominator-raw" not in mix


def test_store_ranking_aggregates_decimal_and_shares_the_entire_input_before_top_six() -> None:
    rows = [{"store_id": f"S{index}", "net_revenue_brl": str(index)} for index in range(1, 8)] + [
        {"store_id": "S7", "net_revenue_brl": "0.10"}
    ]
    chart = store_ranking(rows, truncated=True)
    ranked = _attributes(chart, "data-chart-store", "li")
    assert [item["data-chart-store"] for item in ranked] == ["S7", "S6", "S5", "S4", "S3", "S2"]
    assert ranked[0]["data-value-raw"] == "7.10"
    assert (
        _attributes(chart, "data-share-denominator-raw")[0]["data-share-denominator-raw"] == "28.10"
    )
    assert "Recorte parcial de linhas exibidas" in chart
    assert "6 de 7 lojas. Participação na receita deste recorte." in chart
    assert "R$ 7,10" in chart


def test_six_of_twelve_stores_keep_the_other_six_in_the_percentage_denominator() -> None:
    chart = store_ranking(
        [{"store_id": f"S{index:02d}", "net_revenue_brl": "10.00"} for index in range(12)]
    )
    assert len(_attributes(chart, "data-chart-store", "li")) == 6
    assert (
        _attributes(chart, "data-share-denominator-raw")[0]["data-share-denominator-raw"]
        == "120.00"
    )
    assert {
        item["data-share-percent-raw"] for item in _attributes(chart, "data-share-percent-raw")
    } == {"8.33"}
    assert "6 de 12 lojas. Participação na receita deste recorte." in chart


def test_a_negative_store_outside_top_six_disables_part_of_total_percentages() -> None:
    chart = store_ranking(
        [
            *[{"store_id": f"S{index}", "net_revenue_brl": "10.00"} for index in range(6)],
            {"store_id": "S6", "net_revenue_brl": "-1.00"},
        ]
    )
    assert "data-share-denominator-raw" not in chart
    assert "data-share-percent-raw" not in chart


def test_store_aggregation_preserves_amounts_above_float_precision() -> None:
    chart = store_ranking(
        [
            {"store_id": "S1", "net_revenue_brl": Decimal("90071992547409.91")},
            {"store_id": "S1", "net_revenue_brl": Decimal("0.01")},
        ]
    )
    assert _attributes(chart, "data-chart-store", "li")[0]["data-value-raw"] == "90071992547409.92"
    assert "R$ 90.071.992.547.409,92" in chart


def test_store_with_a_missing_daily_value_is_undefined_instead_of_a_partial_ranking() -> None:
    chart = store_ranking(
        [
            {"store_id": "S1", "net_revenue_brl": "10.00"},
            {"store_id": "S1", "net_revenue_brl": None},
            {"store_id": "S2", "net_revenue_brl": "0.00"},
        ]
    )
    assert [item["data-chart-store"] for item in _attributes(chart, "data-chart-store")] == ["S2"]
    assert "receita completa não entram no ranking" in chart
    assert "R$ 0,00" in chart
    assert "data-share-denominator-raw" not in chart


def test_negative_store_values_are_signed_bars_without_part_of_total_percentages() -> None:
    chart = store_ranking(
        [
            {"store_id": "S1", "net_revenue_brl": "10.00"},
            {"store_id": "S2", "net_revenue_brl": "-20.00"},
        ]
    )
    negative = next(
        item for item in _attributes(chart, "data-chart-store") if item["data-sign"] == "negative"
    )
    assert negative["data-value-raw"] == "-20.00"
    assert "R$ -20,00" in chart
    assert "data-share-percent-raw" not in chart
    assert "width:66.666667%" in chart


def test_product_mix_denominator_and_legend_describe_only_supplied_products() -> None:
    chart = product_mix([{"product_id": "P1", "units": 3}, {"product_id": "P2", "units": 1}], True)
    assert _attributes(chart, "data-share-denominator-raw")[0]["data-share-denominator-raw"] == "4"
    shares = [
        item["data-share-percent-raw"] for item in _attributes(chart, "data-share-percent-raw")
    ]
    assert shares == ["75.00", "25.00"]
    assert "width:75.000000%" in chart
    assert "Unidades no recorte de produtos exibidos" in chart


def test_product_mix_groups_only_the_remaining_displayed_products_without_losing_units() -> None:
    chart = product_mix(
        [{"product_id": f"P{index}", "units": index} for index in range(1, 9)], True
    )
    assert len(_attributes(chart, "data-chart-product", "li")) == 5
    group = _attributes(chart, "data-chart-product-group", "li")[0]
    assert group["data-product-count"] == "3"
    assert group["data-units-raw"] == "6"
    assert _attributes(chart, "data-share-denominator-raw")[0]["data-share-denominator-raw"] == "36"
    assert "Demais produtos exibidos" in chart
    assert "16,67%" in chart


def test_product_zero_and_missing_units_are_distinct_and_neither_creates_a_segment() -> None:
    chart = product_mix([{"product_id": "P1", "units": 0}, {"product_id": "P2", "units": None}])
    products = _attributes(chart, "data-chart-product", "li")
    assert products[0]["data-units-raw"] == "0"
    assert "data-units-raw" not in products[1]
    assert "product-mix-track" not in chart
    assert "Zero unidades registradas" in chart


def test_negative_product_units_keep_the_value_but_do_not_define_a_mix() -> None:
    chart = product_mix([{"product_id": "P1", "units": 3}, {"product_id": "P2", "units": -1}])
    assert "Participação não calculada" in chart
    assert "product-mix-track" not in chart
    assert "data-share-percent-raw" not in chart
    assert any(item["data-units-raw"] == "-1" for item in _attributes(chart, "data-units-raw"))


def test_hostile_identifiers_remain_literal_text_and_attributes() -> None:
    label = '<img src=x onerror="alert(1)"> & loja'
    for chart in (
        store_ranking([{"store_id": label, "net_revenue_brl": "12.50"}]),
        product_mix([{"product_id": label, "units": 3}]),
    ):
        elements = _Elements(chart).elements
        assert not any(tag in {"img", "script"} for tag, _ in elements)
        assert not any("onerror" in attrs for _, attrs in elements)
        identifier = "data-chart-store" if "store-ranking" in chart else "data-chart-product"
        assert _attributes(chart, identifier, "li")[0][identifier] == label


def test_input_rows_are_not_mutated_by_any_chart() -> None:
    rows = [
        {
            "store_id": "S1",
            "product_id": "P1",
            "business_date": "2026-01-01",
            "net_revenue_brl": "1.005",
            "units": 2,
        }
    ]
    before = deepcopy(rows)
    for helper in (sales_trend, store_ranking, product_mix):
        helper(rows)
    assert rows == before
    assert "R$ 1,01" in store_ranking(rows)


@pytest.mark.parametrize("helper", [sales_trend, store_ranking, product_mix])
def test_empty_input_is_an_explicit_empty_state(helper: object) -> None:
    assert callable(helper)
    assert 'class="chart-empty"' in helper([])

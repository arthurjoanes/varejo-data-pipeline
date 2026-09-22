"""Oráculos manuais para fronteiras que atravessam CSV, Spark, Delta e HTML."""

import json
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.generation import fixture_rows, write_batch
from retail_pipeline.pipeline import process_batch
from retail_pipeline.publication import load_snapshot, read_table
from retail_pipeline.reporting import generate_report

pytestmark = pytest.mark.integration


def _report_metrics(html: str) -> dict[str, str]:
    """Read named values without coupling the domain oracle to visual markup."""

    class MetricsParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.values: dict[str, str] = {}
            self.metric: str | None = None
            self.depth = 0
            self.parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if self.metric is not None:
                self.depth += 1
            elif metric := dict(attrs).get("data-metric"):
                assert metric not in self.values, f"Repeated summary metric: {metric}"
                self.metric, self.depth, self.parts = metric, 1, []

        def handle_data(self, data: str) -> None:
            if self.metric is not None:
                self.parts.append(data)

        def handle_endtag(self, tag: str) -> None:
            if self.metric is not None:
                self.depth -= 1
                if self.depth == 0:
                    self.values[self.metric] = " ".join("".join(self.parts).split())
                    self.metric = None

    parser = MetricsParser()
    parser.feed(html)
    return parser.values


def test_date_and_money_boundaries_survive_delta_storage(
    spark: SparkSession, tmp_path: Path, monkeypatch
) -> None:
    base = fixture_rows()[0]
    rows = [
        {
            **base,
            "sale_id": "maximum",
            "quantity": "1000000",
            "unit_price_brl": "999999999.99",
            "line_discount_brl": "0",
            "sold_at": "9999-12-31T12:00:00Z",
        },
        {
            **base,
            "sale_id": "oldest",
            "quantity": "1",
            "unit_price_brl": "0.01",
            "line_discount_brl": "0",
            "sold_at": "0001-01-02T12:00:00Z",
            "source_updated_at": "0001-01-02T12:00:00Z",
        },
        {
            **base,
            "sale_id": "historic",
            "quantity": "1",
            "unit_price_brl": "1.01",
            "line_discount_brl": "0",
            "sold_at": "1800-01-01T12:00:00Z",
        },
    ]
    source = write_batch(tmp_path / "input", rows, zero_movement=("S02", "S03"))
    root = tmp_path / "state"
    result = process_batch(spark, root, source)
    assert result.state == "PUBLISHED", result.issues
    snapshot = load_snapshot(root)
    actual = read_table(spark, snapshot, "gold_store_day").orderBy("business_date").collect()
    assert [(r["business_date"], r["net_revenue_brl"], r["sales_count"]) for r in actual] == [
        (date(1, 1, 2), Decimal("0.01"), 1),
        (date(1800, 1, 1), Decimal("1.01"), 1),
        (date(9999, 12, 31), Decimal("999999999990000.00"), 1),
    ]
    report = generate_report(spark, root, tmp_path / "report.html").read_text(encoding="utf-8")
    assert "R$ 999.999.999.990.001,02" in report
    assert "31/12/9999" in report
    # A contenção da próxima entrega não pode mudar os valores já publicados.
    monkeypatch.setenv("RETAIL_MAX_FILE_BYTES", "16")
    blocked = process_batch(spark, root, source)
    assert blocked.state == "BLOCKED", blocked.issues
    assert blocked.exit_code == 2
    assert any(issue["code"] == "INPUT_FILE_BYTES_LIMIT" for issue in blocked.issues)
    assert load_snapshot(root) == snapshot
    reference_evidence = root / "runs" / blocked.run_id / "evidence/operator-references.json"
    assert json.loads(reference_evidence.read_text()) == json.loads(
        (root / "operator-references.json").read_text()
    )


def test_zero_movement_all_cancellations_and_free_sales_have_distinct_ticket_meaning(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    empty = write_batch(
        tmp_path / "empty", [], batch_id="empty", zero_movement=("S01", "S02", "S03")
    )
    assert process_batch(spark, root, empty).state == "PUBLISHED"
    empty_html = generate_report(spark, root, tmp_path / "empty.html").read_text(encoding="utf-8")
    empty_metrics = _report_metrics(empty_html)
    assert empty_metrics["net_revenue"] == "R$ 0,00"
    assert empty_metrics["sales_count"] == "0"
    assert empty_metrics["average_ticket_brl"] == "—"
    assert "Sem vendas no período" in empty_html
    cancelled = [{**row, "operation": "CANCEL"} for row in fixture_rows()]
    source = write_batch(tmp_path / "cancel", cancelled, batch_id="cancelled")
    assert process_batch(spark, root, source).state == "PUBLISHED"
    snapshot = load_snapshot(root)
    assert read_table(spark, snapshot, "silver").count() == 4
    assert read_table(spark, snapshot, "gold_store_day").count() == 0
    cancelled_html = generate_report(spark, root, tmp_path / "cancel.html").read_text(
        encoding="utf-8"
    )
    assert "Sem vendas no período" in cancelled_html
    cancelled_metrics = _report_metrics(cancelled_html)
    assert cancelled_metrics["net_revenue"] == "R$ 0,00"
    assert cancelled_metrics["sales_count"] == "0"
    assert cancelled_metrics["average_ticket_brl"] == "—"
    free_rows = [
        {**row, "revision": "2", "unit_price_brl": "0", "line_discount_brl": "0"}
        for row in fixture_rows()
    ]
    free = write_batch(tmp_path / "free", free_rows, batch_id="free")
    assert process_batch(spark, root, free).state == "PUBLISHED"
    gold = read_table(spark, load_snapshot(root), "gold_store_day").orderBy("store_id").collect()
    assert [(r["sales_count"], r["average_ticket_brl"]) for r in gold] == [
        (2, Decimal("0.00")),
        (1, Decimal("0.00")),
    ]
    free_html = generate_report(spark, root, tmp_path / "free.html").read_text(encoding="utf-8")
    free_metrics = _report_metrics(free_html)
    assert free_metrics["net_revenue"] == "R$ 0,00"
    assert free_metrics["sales_count"] == "3"
    assert free_metrics["average_ticket_brl"] == "R$ 0,00"
    assert "Sem vendas no período" not in free_html


def test_same_sale_in_different_sources_is_distinct_and_offsets_are_equivalent(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    row = {
        **fixture_rows()[0],
        "quantity": "1",
        "unit_price_brl": "1",
        "line_discount_brl": "0",
        "sold_at": "2026-01-02T02:59:59.999999Z",
    }
    for source_name in ("pos-a", "pos-b"):
        source = write_batch(
            tmp_path / source_name,
            [{**row, "source_system": source_name}],
            batch_id=source_name,
            source_system=source_name,
            zero_movement=("S02", "S03"),
        )
        assert process_batch(spark, root, source).state == "PUBLISHED"
    actual = read_table(spark, load_snapshot(root), "gold_store_day").collect()
    assert len(actual) == 1
    assert (
        actual[0]["business_date"],
        actual[0]["sales_count"],
        actual[0]["average_ticket_brl"],
    ) == (date(2026, 1, 1), 2, Decimal("1.00"))
    equivalent = {**row, "source_system": "pos-a", "sold_at": "2026-01-01T23:59:59.999999-03:00"}
    source = write_batch(
        tmp_path / "equivalent",
        [equivalent],
        batch_id="equivalent",
        source_system="pos-a",
        zero_movement=("S02", "S03"),
    )
    replay = process_batch(spark, root, source)
    assert replay.state == "PUBLISHED" and replay.stats["duplicates"] == 1
    assert read_table(spark, load_snapshot(root), "silver").count() == 2

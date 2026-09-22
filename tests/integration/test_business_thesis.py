"""Oráculo de negócio literal: não usa a transformação para calcular o esperado."""

import os
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.generation import fixture_rows, write_batch
from retail_pipeline.pipeline import process_batch
from retail_pipeline.publication import Publication, atomic_json, load_snapshot, read_table
from retail_pipeline.reporting import generate_report

pytestmark = pytest.mark.integration


def rows(spark: SparkSession, snapshot: Publication) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in read_table(spark, snapshot, "gold_store_day")
        .select("business_date", "store_id", "net_revenue_brl", "sales_count", "average_ticket_brl")
        .orderBy("business_date", "store_id")
        .collect()
    ]


def test_independent_coverage_whole_sale_correction_and_recovery(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    base = write_batch(tmp_path / "base", fixture_rows(), batch_id="base")
    steps = []
    evidence_dir = os.getenv("RETAIL_THESIS_EVIDENCE_DIR")

    def capture_step(name: str) -> None:
        # Exporta a publicação e a tentativa presentes nesse instante, sem reconstruir
        # estados antigos para screenshots. Só roda quando a prova pede evidências.
        if evidence_dir:
            generate_report(spark, root, Path(evidence_dir) / name, synthetic_data=True)

    result = process_batch(spark, root, base)
    steps.append(asdict(result))
    assert result.state == "PUBLISHED", result.issues
    frozen = load_snapshot(root)
    assert frozen is not None
    initial = [
        (date(2026, 1, 1), "S01", Decimal("44.00"), 2, Decimal("22.00")),
        (date(2026, 1, 1), "S02", Decimal("20.00"), 1, Decimal("20.00")),
    ]
    assert rows(spark, frozen) == initial
    capture_step("published-initial.html")
    omitted = write_batch(
        tmp_path / "omitted",
        fixture_rows()[:3],
        batch_id="sender-reduced-calendar",
        expected_stores=("S01", "S03"),
    )
    result = process_batch(spark, root, omitted)
    steps.append(asdict(result))
    assert result.state == "BLOCKED"
    assert result.coverage["expected"] == ["S01", "S02", "S03"]
    assert result.coverage["missing"] == ["S02"]
    assert load_snapshot(root) == frozen
    capture_step("coverage-blocked.html")

    partial_rows = fixture_rows()
    partial_rows[0].update(revision="99", sold_at="2026-01-02T12:00:00-03:00")
    # Baseline ingênuo executado em Python: agrupar a imagem recebida por dia
    # preserva R$64,00, mas conta A1 em dois dias (quatro vendas no fechamento).
    naive_sales = len(
        {
            (
                row["source_system"],
                row["store_id"],
                row["sale_id"],
                datetime.fromisoformat(row["sold_at"])
                .astimezone(ZoneInfo("America/Sao_Paulo"))
                .date(),
            )
            for row in partial_rows
        }
    )
    naive_revenue = sum(
        (int(row["quantity"]) * Decimal(row["unit_price_brl"]) - Decimal(row["line_discount_brl"]))
        for row in partial_rows
    )
    assert naive_revenue == Decimal("64.00") and naive_sales == 4
    partial = write_batch(tmp_path / "partial", partial_rows, batch_id="partial-date-99")
    for validate_only in (True, False):
        result = process_batch(spark, root, partial, validate_only=validate_only)
        steps.append(asdict(result))
        assert result.state == "BLOCKED", result.issues
        assert "SALE_DATE_CONFLICT" in {issue["code"] for issue in result.issues}
        assert result.stats["rejected"] == 2
        assert load_snapshot(root) == frozen
    capture_step("partial-date-blocked.html")
    complete_rows = fixture_rows()
    for row in complete_rows[:2]:
        row.update(revision="2", sold_at="2026-01-02T12:00:00-03:00")
    complete = write_batch(tmp_path / "complete", complete_rows, batch_id="complete-date-2")
    result = process_batch(spark, root, complete)
    steps.append(asdict(result))
    assert result.state == "PUBLISHED", result.issues
    corrected = load_snapshot(root)
    assert corrected is not None
    expected = [
        (date(2026, 1, 1), "S01", Decimal("20.00"), 1, Decimal("20.00")),
        (date(2026, 1, 1), "S02", Decimal("20.00"), 1, Decimal("20.00")),
        (date(2026, 1, 2), "S01", Decimal("24.00"), 1, Decimal("24.00")),
    ]
    assert rows(spark, corrected) == expected
    assert read_table(spark, corrected, "history").filter("revision = 99").count() == 0

    capture_step("whole-sale-corrected.html")
    changed_rows = [dict(row) for row in complete_rows]
    changed_rows[0].update(revision="3", quantity="3")
    changed = write_batch(tmp_path / "recovery", changed_rows, batch_id="recoverable-3")
    result = process_batch(spark, root, changed, fail_at="after_gold", allow_failures=True)
    steps.append(asdict(result))
    assert result.state == "TECHNICAL_FAILURE"
    assert load_snapshot(root) == corrected
    assert rows(spark, corrected) == expected
    # A falha deixou de fato duas tabelas latest incompatíveis; o manifesto
    # conserva ambas as versões oficiais anteriores, e não apenas o mesmo ID.
    candidate_totals = {
        table: sum(
            row["net_revenue_brl"]
            for row in spark.read.format("delta").load(corrected["tables"][table]["path"]).collect()
        )
        for table in ("gold_store_day", "gold_product_day")
    }
    official_totals = {
        table: sum(row["net_revenue_brl"] for row in read_table(spark, corrected, table).collect())
        for table in ("gold_store_day", "gold_product_day")
    }
    assert candidate_totals == {
        "gold_store_day": Decimal("74.00"),
        "gold_product_day": Decimal("64.00"),
    }
    assert official_totals == {
        "gold_store_day": Decimal("64.00"),
        "gold_product_day": Decimal("64.00"),
    }
    assert read_table(spark, corrected, "history").filter("revision = 3").count() == 0
    capture_step("failure-before-publication.html")
    result = process_batch(spark, root, changed)
    steps.append(asdict(result))
    assert result.state == "PUBLISHED", result.issues
    recovered = load_snapshot(root)
    assert recovered is not None
    final_expected = [
        *expected[:2],
        (date(2026, 1, 2), "S01", Decimal("34.00"), 1, Decimal("34.00")),
    ]
    observed = rows(spark, recovered)
    assert observed == final_expected
    replay = process_batch(spark, root, changed)
    steps.append(asdict(replay))
    assert replay.state == "NO_CHANGE"
    assert load_snapshot(root) == recovered
    assert rows(spark, frozen) == initial
    if evidence_dir:
        capture_step("report.html")
        atomic_json(
            Path(evidence_dir) / "business-thesis.json",
            {
                "status": "passed",
                "data_origin": "Synthetic manual fixture executed with real Spark and Delta",
                "report_capture": "Each HTML reads the actual state immediately after its named step",
                "reports": [
                    "published-initial.html",
                    "coverage-blocked.html",
                    "partial-date-blocked.html",
                    "whole-sale-corrected.html",
                    "failure-before-publication.html",
                    "report.html",
                ],
                "baseline_partial_date": {
                    "method": "Agrupamento direto da imagem recebida por origem/loja/venda/dia, Python independente",
                    "net_revenue_brl": naive_revenue,
                    "sales_count": naive_sales,
                    "manual_correct_sales_count": 3,
                    "pipeline_decision": "BLOCKED: SALE_DATE_CONFLICT",
                },
                "spark": spark.version,
                "data_dir": str(root),
                "expected_initial": initial,
                "after_failure_latest_totals": candidate_totals,
                "after_failure_official_totals": official_totals,
                "observed_initial_frozen": rows(spark, frozen),
                "expected_final": final_expected,
                "observed_final": observed,
                "steps": steps,
                "initial_publication": frozen,
                "final_publication": recovered,
                "limitations": "Fixture pequena, ambiente local, nenhuma inferência de throughput de produção.",
            },
        )

from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.generation import fixture_rows, write_batch
from retail_pipeline.pipeline import process_batch
from retail_pipeline.profiling import ProfileParameters, build_profile, load_profile
from retail_pipeline.publication import Publication, load_snapshot, read_table, table_reference

pytestmark = pytest.mark.integration


def require_snapshot(root: Path) -> Publication:
    snapshot = load_snapshot(root)
    assert snapshot is not None
    return snapshot


def require_profile(snapshot: Publication) -> dict[str, Any]:
    result = load_profile(snapshot)
    assert result["status"] == "AVAILABLE", result
    assert result["profile"] is not None
    return result["profile"]


def oracle(events: list[dict[str, str]]) -> dict[str, Any]:
    # Oráculo independente: escolhe imagens por chave/revisão em Python/Decimal,
    # sem Gold, helper de transformação ou código do perfil.
    latest: dict[tuple[str, ...], dict[str, str]] = {}
    for event in events:
        key = tuple(event[name] for name in ("source_system", "store_id", "sale_id", "line_id"))
        if key not in latest or int(event["revision"]) > int(latest[key]["revision"]):
            latest[key] = event
    active = [row for row in latest.values() if row["operation"] == "UPSERT"]
    gross = sum(
        (int(row["quantity"]) * Decimal(row["unit_price_brl"]) for row in active), Decimal("0.00")
    )
    discount = sum((Decimal(row["line_discount_brl"]) for row in active), Decimal("0.00"))
    return {
        "active_lines": len(active),
        "sales": len(
            {
                tuple(row[name] for name in ("source_system", "store_id", "sale_id"))
                for row in active
            }
        ),
        "units": sum(int(row["quantity"]) for row in active),
        "net_revenue_brl": format(gross - discount, ".2f"),
        "gross_revenue_brl": format(gross, ".2f"),
        "discount_brl": format(discount, ".2f"),
    }


def test_revision_cancel_profile_matches_decimal_oracle_and_replay_is_immutable(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    original_rows = fixture_rows()
    original = write_batch(tmp_path / "base", original_rows, batch_id="profile-base")
    accepted = process_batch(spark, root, original)
    assert accepted.state == "PUBLISHED", accepted.issues
    previous = require_snapshot(root)
    previous_profile = require_profile(previous)
    assert previous_profile["active_state"]["totals"] == oracle(original_rows)
    assert previous_profile["comparison"]["status"] == "NO_BASELINE"
    previous_bytes = Path(previous["profile"]["path"]).read_bytes()

    corrected_rows = fixture_rows()
    corrected_rows[0].update(revision="2", quantity="100", unit_price_brl="11.00")
    corrected_rows[-1].update(revision="2", operation="CANCEL")
    # A duplicata recebida deve entrar em métricas do lote, nunca em receita ativa.
    received = [*corrected_rows, dict(corrected_rows[0])]
    corrected = write_batch(tmp_path / "corrected", received, batch_id="profile-corrected")
    failed = process_batch(spark, root, corrected, fail_at="profile_write", allow_failures=True)
    assert failed.state == "TECHNICAL_FAILURE"
    assert require_snapshot(root) == previous
    assert Path(previous["profile"]["path"]).read_bytes() == previous_bytes

    result = process_batch(spark, root, corrected)
    assert result.state == "PUBLISHED", result.issues
    current = require_snapshot(root)
    profile = require_profile(current)
    assert profile["active_state"]["totals"] == oracle([*original_rows, *received])
    assert profile["active_state"]["cancelled_keys"] == 1
    assert profile["batch"]["stats"]["received"] == 5
    assert profile["batch"]["stats"]["duplicates"] == 3
    assert profile["batch"]["received_operations"] == {
        "valid_cancel_events": 1,
        "valid_revision_gt1_events": 3,
    }
    assert profile["state_changes"]["revised_keys"] == 2
    assert profile["state_changes"]["cancelled_keys"] == 1
    assert profile["state_changes"]["effective_changes"] == 2
    assert profile["comparison"]["baseline_publication_id"] == previous["publication_id"]
    assert profile["comparison"]["warnings"] >= 1
    assert all(rule["severity"] in {"INFO", "WARNING"} for rule in profile["comparison"]["rules"])
    current_bytes = Path(current["profile"]["path"]).read_bytes()
    assert process_batch(spark, root, corrected).state == "NO_CHANGE"
    assert require_snapshot(root) == current
    assert Path(current["profile"]["path"]).read_bytes() == current_bytes
    assert len(list((root / "profiles").glob("*.json"))) == 2

    unpublished_rows = fixture_rows()
    unpublished_rows[0].update(revision="99", quantity="999", unit_price_brl="99.00")
    unpublished = write_batch(
        tmp_path / "unpublished", unpublished_rows, batch_id="profile-unpublished"
    )
    failed_gold = process_batch(spark, root, unpublished, fail_at="after_gold", allow_failures=True)
    assert failed_gold.state == "TECHNICAL_FAILURE"
    assert require_snapshot(root) == current
    assert Path(current["profile"]["path"]).read_bytes() == current_bytes
    rebuilt = build_profile(
        spark,
        current,
        previous,
        batch_stats=result.stats,
        coverage=result.coverage,
        reference_hashes=profile["reference_hashes"],
    )
    # A versão física mais nova é da tentativa bloqueada; o perfil relê as duas
    # versões indicadas pelos manifestos oficiais e reproduz seus bytes lógicos.
    assert rebuilt == profile


def test_comparison_recalculates_full_intersection_despite_truncated_groups_and_dates(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    base = write_batch(tmp_path / "base", fixture_rows(), batch_id="intersection-base")
    assert process_batch(spark, root, base).state == "PUBLISHED"
    previous = require_snapshot(root)
    moved_rows = fixture_rows()
    for row in moved_rows[:2]:
        row.update(revision="2", sold_at="2026-01-02T12:00:00-03:00")
    moved = write_batch(tmp_path / "moved", moved_rows, batch_id="intersection-moved")
    result = process_batch(spark, root, moved)
    assert result.state == "PUBLISHED", result.issues
    current = require_snapshot(root)
    profile = require_profile(current)
    diagnostic = build_profile(
        spark,
        current,
        previous,
        batch_stats=result.stats,
        coverage=result.coverage,
        reference_hashes=profile["reference_hashes"],
        parameters=ProfileParameters(group_limit=1, date_display_limit=1, min_active_lines=1),
    )
    assert diagnostic["date_range"]["date_count"] == 2
    assert diagnostic["date_range"]["dates_truncated"] is True
    assert diagnostic["active_state"]["groups"]["stores"]["truncated"] is True
    assert diagnostic["active_state"]["groups"]["products"]["truncated"] is True
    comparison = diagnostic["comparison"]
    assert comparison["status"] == "COMPARABLE"
    assert comparison["context"]["dates_changed"] is True
    assert comparison["scope"]["dates"]["dates"] == ["2026-01-01"]
    assert comparison["scope"]["date_intersection_complete"] is True
    assert comparison["original_totals"]["current"]["net_revenue_brl"] == "64.00"
    assert comparison["equivalent_totals"]["previous"]["net_revenue_brl"] == "64.00"
    assert comparison["equivalent_totals"]["current"]["net_revenue_brl"] == "40.00"
    assert comparison["equivalent_totals"]["current"]["units"] == 4
    assert comparison["scope"]["silver_versions"]["previous"] == previous["tables"]["silver"]

    # Uma Silver candidata em outro caminho permite provar período disjunto.
    disjoint_path = tmp_path / "candidate-disjoint"
    read_table(spark, current, "silver").filter("business_date = DATE '2026-01-02'").write.format(
        "delta"
    ).save(str(disjoint_path))
    candidate = copy.deepcopy(current)
    candidate["publication_id"] = "candidate-disjoint"
    candidate["tables"]["silver"] = table_reference(spark, disjoint_path)
    incomparable = build_profile(
        spark,
        candidate,
        previous,
        batch_stats=result.stats,
        coverage=result.coverage,
        reference_hashes=profile["reference_hashes"],
    )
    assert incomparable["comparison"]["status"] == "NOT_COMPARABLE"
    assert incomparable["comparison"]["scope"]["dates"]["date_count"] == 0
    assert incomparable["comparison"]["equivalent_totals"] is None
    assert incomparable["comparison"]["rules"] == []
    assert require_snapshot(root) == current


def test_zero_publication_and_legacy_baseline_are_explicit(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    zero = write_batch(
        tmp_path / "zero", [], batch_id="zero-first", zero_movement=("S01", "S02", "S03")
    )
    first_result = process_batch(spark, root, zero)
    assert first_result.state == "PUBLISHED", first_result.issues
    first = require_snapshot(root)
    profile = require_profile(first)
    assert profile["active_state"]["totals"] == oracle([])
    assert profile["date_range"]["start"] is None
    assert profile["comparison"]["status"] == "NO_BASELINE"
    assert profile["coverage"]["scope_complete"] is True
    second_zero = write_batch(
        tmp_path / "zero-second", [], batch_id="zero-second", zero_movement=("S01", "S02", "S03")
    )
    second_result = process_batch(spark, root, second_zero)
    assert second_result.state == "PUBLISHED", second_result.issues
    second = require_snapshot(root)
    assert require_profile(second)["comparison"]["status"] == "EMPTY"
    legacy = copy.deepcopy(first)
    del legacy["profile"]
    recovered_profile = build_profile(
        spark,
        second,
        legacy,
        batch_stats=second_result.stats,
        coverage=second_result.coverage,
        reference_hashes=profile["reference_hashes"],
    )
    assert recovered_profile["comparison"]["status"] == "BASELINE_PROFILE_UNAVAILABLE"
    assert recovered_profile["comparison"]["original_totals"]["previous"] is None
    assert recovered_profile["coverage"]["scope_complete"] is False
    assert load_profile(None)["status"] == "NO_PUBLICATION"


def test_legacy_unknown_coverage_is_not_inferred_from_active_stores(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    source = write_batch(tmp_path / "base", fixture_rows(), batch_id="coverage-base")
    result = process_batch(spark, root, source)
    assert result.state == "PUBLISHED", result.issues
    previous = require_snapshot(root)
    stored = require_profile(previous)
    legacy = copy.deepcopy(previous)
    del legacy["profile"]
    candidate = copy.deepcopy(previous)
    candidate["publication_id"] = "coverage-legacy-candidate"
    latest_coverage = {
        "expected": ["S03"],
        "received": ["S03"],
        "missing": [],
        "zero_movement": ["S03"],
    }
    profile = build_profile(
        spark,
        candidate,
        legacy,
        batch_stats={},
        coverage=latest_coverage,
        reference_hashes=stored["reference_hashes"],
    )
    assert profile["active_state"]["groups"]["stores"]["group_count"] == 2
    assert profile["coverage"]["received"] == ["S03"]
    assert profile["coverage"]["scope_complete"] is False
    assert profile["batch"]["coverage"] == latest_coverage
    # Uma baseline com perfil preserva a cobertura confirmada cumulativa.
    candidate["publication_id"] = "coverage-known-candidate"
    known = build_profile(
        spark,
        candidate,
        previous,
        batch_stats={},
        coverage=latest_coverage,
        reference_hashes=stored["reference_hashes"],
    )
    assert known["coverage"]["received"] == ["S01", "S02", "S03"]
    assert known["coverage"]["scope_complete"] is True
    assert known["batch"]["coverage"] == latest_coverage

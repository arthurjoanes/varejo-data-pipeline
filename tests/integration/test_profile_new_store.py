"""A newly covered store changes global totals without changing the shared recut."""

from decimal import Decimal
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.generation import (
    default_catalog,
    default_schedule,
    fixture_rows,
    write_batch,
)
from retail_pipeline.pipeline import process_batch
from retail_pipeline.profiling import load_profile
from retail_pipeline.publication import load_snapshot
from retail_pipeline.references import configure_references


@pytest.mark.integration
def test_new_store_changes_context_and_totals_but_not_the_equivalent_scope(
    spark: SparkSession, tmp_path: Path
) -> None:
    # All four stores and both windows are approved before the first publication.
    # A separate state avoids changing the standard autouse three-store fixture.
    root = tmp_path / "new-store-state"
    base_stores = ["S01", "S02", "S03"]
    expanded_stores = [*base_stores, "S04"]
    catalog = default_catalog(store_count=4)
    schedule = default_schedule(base_stores, window_id="base-window")
    schedule["windows"] = [
        *schedule["windows"],
        *default_schedule(expanded_stores, window_id="expanded-window")["windows"],
    ]
    configure_references(root, catalog, schedule)
    approved_bytes = (root / "operator-references.json").read_bytes()

    original_rows = fixture_rows()
    base = write_batch(
        tmp_path / "new-store-base",
        original_rows,
        batch_id="new-store-base",
        window_id="base-window",
        expected_stores=base_stores,
        zero_movement=("S03",),
        catalog=catalog,
    )
    baseline_result = process_batch(spark, root, base)
    assert baseline_result.state == "PUBLISHED", baseline_result.issues
    baseline = load_snapshot(root)
    assert baseline is not None
    baseline_read = load_profile(baseline)
    assert baseline_read["status"] == "AVAILABLE" and baseline_read["profile"] is not None
    baseline_profile = baseline_read["profile"]
    baseline_totals = baseline_profile["active_state"]["totals"]
    assert baseline_totals["net_revenue_brl"] == "64.00"
    assert baseline_profile["coverage"]["received"] == base_stores
    baseline_bytes = Path(baseline["profile"]["path"]).read_bytes()

    added = {
        **original_rows[0],
        "store_id": "S04",
        "sale_id": "new-store-sale",
        "quantity": "1000",
        "unit_price_brl": "1000.00",
        "line_discount_brl": "0.00",
    }
    expanded = write_batch(
        tmp_path / "new-store-expanded",
        [*original_rows, added],
        batch_id="new-store-expanded",
        window_id="expanded-window",
        expected_stores=expanded_stores,
        zero_movement=("S03",),
        catalog=catalog,
    )
    result = process_batch(spark, root, expanded)
    assert result.state == "PUBLISHED", result.issues
    current = load_snapshot(root)
    assert current is not None and current["publication_id"] != baseline["publication_id"]
    current_read = load_profile(current)
    assert current_read["status"] == "AVAILABLE" and current_read["profile"] is not None
    profile = current_read["profile"]
    comparison = profile["comparison"]

    assert profile["coverage"]["scope_complete"] is True
    assert profile["coverage"]["received"] == expanded_stores
    assert comparison["baseline_publication_id"] == baseline["publication_id"]
    assert comparison["status"] == "COMPARABLE"
    assert comparison["context"]["stores_added"] == ["S04"]
    assert comparison["context"]["stores_removed"] == []
    assert comparison["context"]["dates_changed"] is False
    assert comparison["context"]["catalog_changed"] is False
    assert comparison["context"]["catalog_reference_origin"] == "approved_operator_catalog"
    assert comparison["scope"]["stores"] == base_stores
    assert comparison["scope"]["dates"]["dates"] == ["2026-01-01"]
    assert comparison["scope"]["date_intersection_complete"] is True
    assert comparison["scope"]["silver_versions"] == {
        "previous": baseline["tables"]["silver"],
        "current": current["tables"]["silver"],
    }

    added_revenue = Decimal(added["quantity"]) * Decimal(added["unit_price_brl"])
    current_totals = profile["active_state"]["totals"]
    assert Decimal(current_totals["net_revenue_brl"]) == (
        Decimal(baseline_totals["net_revenue_brl"]) + added_revenue
    )
    assert current_totals["active_lines"] == baseline_totals["active_lines"] + 1
    assert current_totals["units"] == baseline_totals["units"] + int(added["quantity"])
    assert comparison["original_totals"]["current"] == current_totals
    assert comparison["original_totals"]["previous"] == baseline_totals
    assert comparison["equivalent_totals"]["previous"] == baseline_totals
    assert comparison["equivalent_totals"]["current"] == baseline_totals
    assert comparison["warnings"] == 0
    assert all(rule["status"] == "STABLE" for rule in comparison["rules"])
    s04 = next(
        group
        for group in profile["active_state"]["groups"]["stores"]["values"]
        if group["store_id"] == "S04"
    )
    assert Decimal(s04["net_revenue_brl"]) == added_revenue
    assert (root / "operator-references.json").read_bytes() == approved_bytes
    assert Path(baseline["profile"]["path"]).read_bytes() == baseline_bytes

"""Profiles join the commit; lineage exports remain recoverable after it."""

import json
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.generation import fixture_rows, write_batch
from retail_pipeline.lineage import canonical_run_id, export_lineage, validate_event
from retail_pipeline.pipeline import process_batch
from retail_pipeline.profiling import load_profile
from retail_pipeline.publication import load_snapshot


@pytest.mark.integration
def test_profile_write_failure_and_postcommit_export_recover_idempotently(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    original_input = write_batch(tmp_path / "base", fixture_rows(), batch_id="base")
    first = process_batch(spark, root, original_input)
    assert first.state == "PUBLISHED", first.issues
    original = load_snapshot(root)
    assert original is not None
    assert load_profile(original)["status"] == "AVAILABLE"
    profile_path = Path(original["profile"]["path"])
    profile_bytes = profile_path.read_bytes()
    revised = fixture_rows()
    revised[0].update(revision="2", unit_price_brl="30.00")
    source = write_batch(tmp_path / "revision", revised, batch_id="revision")
    failed = process_batch(spark, root, source, fail_at="profile_write", allow_failures=True)
    assert failed.state == "TECHNICAL_FAILURE"
    assert load_snapshot(root) == original
    assert profile_path.read_bytes() == profile_bytes
    assert len(list((root / "profiles").glob("*.json"))) == 1

    committed = process_batch(spark, root, source, fail_at="lineage_export", allow_failures=True)
    assert committed.state == "PUBLISHED", committed.issues
    assert committed.exit_code == 0
    assert any(issue["code"] == "LINEAGE_EXPORT_FAILURE" for issue in committed.issues)
    snapshot = load_snapshot(root)
    assert snapshot is not None and snapshot["run_id"] == committed.run_id
    profile = load_profile(snapshot)
    assert profile["status"] == "AVAILABLE" and profile["profile"] is not None
    assert profile["profile"]["active_state"]["totals"]["net_revenue_brl"] == "104.00"
    assert profile["profile"]["comparison"]["baseline_publication_id"] == original["publication_id"]
    assert profile["profile"]["comparison"]["warnings"] > 0
    terminal = root / "lineage/events" / canonical_run_id(committed.run_id) / "terminal.json"
    assert not terminal.exists()
    preserved = {
        path: path.read_bytes()
        for path in [
            root / "publication.json",
            Path(snapshot["profile"]["path"]),
            *list((root / "runs").glob("*/evidence/raw/*")),
        ]
        if path.is_file()
    }
    exported = export_lineage(root)
    assert exported["errors"] == []
    event = json.loads(terminal.read_text())
    validate_event(event)
    assert event["eventType"] == "COMPLETE"
    assert event["run"]["facets"]["varejo_outcome"]["newPublication"] is True
    terminal_bytes = terminal.read_bytes()
    assert export_lineage(root)["errors"] == []
    assert terminal.read_bytes() == terminal_bytes
    assert all(path.read_bytes() == value for path, value in preserved.items())
    repeat = process_batch(spark, root, source)
    assert repeat.state == "NO_CHANGE"
    assert load_snapshot(root) == snapshot
    assert len(list((root / "profiles").glob("*.json"))) == 2
    repeated_event = json.loads(
        (root / "lineage/events" / canonical_run_id(repeat.run_id) / "terminal.json").read_text()
    )
    assert repeated_event["outputs"] == []
    assert repeated_event["run"]["facets"]["varejo_outcome"]["newPublication"] is False

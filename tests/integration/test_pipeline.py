from __future__ import annotations

import csv
import hashlib
import json
import select
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.contracts import BUSINESS_FIELDS
from retail_pipeline.generation import fixture_rows, generate_scenario, write_batch
from retail_pipeline.pipeline import RunResult, process_batch
from retail_pipeline.publication import (
    Publication,
    WriterBusy,
    load_snapshot,
    read_table,
    writer_lock,
)

pytestmark = pytest.mark.integration


def require_publication(root: Path) -> Publication:
    snapshot = load_snapshot(root)
    assert snapshot is not None
    return snapshot


def store_values(spark: SparkSession, snapshot: Publication) -> list[tuple[object, ...]]:
    rows = (
        read_table(spark, snapshot, "gold_store_day")
        .select(
            "business_date",
            "store_id",
            "net_revenue_brl",
            "units",
            "item_lines",
            "sales_count",
            "average_ticket_brl",
        )
        .orderBy("business_date", "store_id")
        .collect()
    )
    return [tuple(row) for row in rows]


def revenue(spark: SparkSession, snapshot: Publication) -> Decimal:
    # Só coleta o gold da fixture pequena; os totais esperados foram calculados à mão.
    return sum(
        (row["net_revenue_brl"] for row in read_table(spark, snapshot, "gold_store_day").collect()),
        Decimal("0"),
    )


def assert_published(result: RunResult) -> None:
    assert result.state == "PUBLISHED", result.issues
    assert result.exit_code == 0


def add_second_export(input_dir: Path, row: dict[str, str]) -> None:
    path = input_dir / "S01-second.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BUSINESS_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    manifest_path = input_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append(
        {
            "path": path.name,
            "store_id": "S01",
            "row_count": 1,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_valid_replay_revisions_date_cancel_and_reactivation(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    original = write_batch(tmp_path / "valid", fixture_rows(), batch_id="base")
    accepted = process_batch(spark, root, original)
    assert_published(accepted)
    first = require_publication(root)
    assert accepted.coverage == {
        "expected": ["S01", "S02", "S03"],
        "received": ["S01", "S02", "S03"],
        "missing": [],
        "zero_movement": ["S03"],
    }
    expected = [
        (date(2026, 1, 1), "S01", Decimal("44.00"), 6, 3, 2, Decimal("22.00")),
        (date(2026, 1, 1), "S02", Decimal("20.00"), 1, 1, 1, Decimal("20.00")),
    ]
    assert store_values(spark, first) == expected
    product = read_table(spark, first, "gold_product_day").orderBy("product_id").collect()
    assert [(row["product_id"], row["net_revenue_brl"], row["units"]) for row in product] == [
        ("P01", Decimal("39.00"), 3),
        ("P02", Decimal("5.00"), 1),
        ("P03", Decimal("20.00"), 3),
    ]

    replay = process_batch(spark, root, original)
    assert replay.state == "NO_CHANGE"
    assert replay.stats["duplicates"] == 4
    assert require_publication(root) == first
    reordered = write_batch(tmp_path / "reordered", reversed(fixture_rows()), batch_id="reordered")
    assert_published(process_batch(spark, root, reordered))
    assert store_values(spark, require_publication(root)) == expected
    doubled = write_batch(tmp_path / "duplicates", fixture_rows() * 2, batch_id="duplicates")
    repeated = process_batch(spark, root, doubled)
    assert_published(repeated)
    assert repeated.stats["duplicates"] == 8
    assert read_table(spark, require_publication(root), "history").count() == 4

    corrected_rows = fixture_rows()
    corrected_rows[0].update(revision="2", quantity="3", unit_price_brl="11.00")
    corrected = write_batch(
        tmp_path / "corrected", corrected_rows, batch_id="corrected", correction_of="base"
    )
    assert_published(process_batch(spark, root, corrected))
    assert revenue(spark, require_publication(root)) == Decimal("77.00")
    old = write_batch(tmp_path / "old", fixture_rows(), batch_id="old")
    stale = process_batch(spark, root, old)
    assert_published(stale)
    assert stale.stats["stale"] == 1
    assert revenue(spark, require_publication(root)) == Decimal("77.00")

    moved_rows = [dict(row) for row in corrected_rows]
    moved_rows[0].update(revision="3", sold_at="2026-01-02T12:00:00-03:00")
    moved_rows[1].update(revision="2", sold_at="2026-01-02T12:00:00-03:00")
    moved = write_batch(tmp_path / "moved", moved_rows, batch_id="moved")
    assert_published(process_batch(spark, root, moved))
    assert store_values(spark, require_publication(root)) == [
        (date(2026, 1, 1), "S01", Decimal("20.00"), 3, 1, 1, Decimal("20.00")),
        (date(2026, 1, 1), "S02", Decimal("20.00"), 1, 1, 1, Decimal("20.00")),
        (date(2026, 1, 2), "S01", Decimal("37.00"), 4, 2, 1, Decimal("37.00")),
    ]

    cancelled_rows = [dict(row) for row in moved_rows]
    cancelled_rows[-1].update(revision="2", operation="CANCEL")
    cancelled = write_batch(tmp_path / "cancelled", cancelled_rows, batch_id="cancelled")
    assert_published(process_batch(spark, root, cancelled))
    snapshot = require_publication(root)
    assert revenue(spark, snapshot) == Decimal("57.00")
    assert read_table(spark, snapshot, "silver").filter("operation = 'CANCEL'").count() == 1
    assert read_table(spark, snapshot, "history").filter("sale_id = 'B1'").count() == 2
    cancelled_rows[-1].update(revision="3", operation="UPSERT")
    reactivated = write_batch(tmp_path / "reactivated", cancelled_rows, batch_id="reactivated")
    assert_published(process_batch(spark, root, reactivated))
    assert revenue(spark, require_publication(root)) == Decimal("77.00")
    # O leitor usa o snapshot capturado mesmo após outras publicações.
    assert store_values(spark, first) == expected


def test_delivery_quality_immutable_batch_and_rejected_history(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    source = write_batch(tmp_path / "valid", fixture_rows(), batch_id="base")
    assert_published(process_batch(spark, root, source))
    official = require_publication(root)

    missing = write_batch(tmp_path / "missing", fixture_rows(), batch_id="missing")
    original_bytes = (missing / "S02.csv").read_bytes()
    (missing / "S02.csv").unlink()
    blocked = process_batch(spark, root, missing)
    assert blocked.state == "BLOCKED"
    assert blocked.exit_code == 2
    assert blocked.stats["revision_checks_executed"] == 0
    assert blocked.coverage["missing"] == ["S02"]
    assert require_publication(root) == official
    # A reposição do arquivo permite repetir o mesmo manifesto.
    (missing / "S02.csv").write_bytes(original_bytes)
    assert_published(process_batch(spark, root, missing))
    official = require_publication(root)

    cross_duplicate = write_batch(
        tmp_path / "cross-duplicate", fixture_rows(), batch_id="cross-duplicate"
    )
    add_second_export(cross_duplicate, fixture_rows()[0])
    result = process_batch(spark, root, cross_duplicate)
    assert_published(result)
    assert result.stats["received"] == 5
    assert result.stats["duplicates"] == 5
    assert revenue(spark, require_publication(root)) == Decimal("64.00")
    official = require_publication(root)
    cross_conflict = write_batch(
        tmp_path / "cross-conflict", fixture_rows(), batch_id="cross-conflict"
    )
    add_second_export(cross_conflict, {**fixture_rows()[0], "unit_price_brl": "99.00"})
    result = process_batch(spark, root, cross_conflict)
    assert result.state == "BLOCKED"
    assert result.stats["conflicts"] == 2
    assert result.stats["revision_checks_executed"] == 1
    assert require_publication(root) == official

    for scenario, code in (
        ("hash", "HASH_MISMATCH"),
        ("schema", "SCHEMA_MISMATCH"),
        ("reference", "UNKNOWN_PRODUCT"),
    ):
        rows = fixture_rows()
        if scenario == "reference":
            rows[0]["product_id"] = "P999"
        bad = write_batch(tmp_path / scenario, rows, batch_id=scenario)
        if scenario in ("hash", "schema"):
            path = bad / "S01.csv"
            content = path.read_text(encoding="utf-8")
            path.write_text(
                content + "\n" if scenario == "hash" else content.replace("quantity", "qty", 1),
                encoding="utf-8",
            )
        rejected = process_batch(spark, root, bad)
        assert rejected.state == "BLOCKED", rejected.issues
        assert rejected.stats["revision_checks_executed"] == 0
        assert code in {issue["code"] for issue in rejected.issues}
        assert require_publication(root) == official
        assert (root / "runs" / rejected.run_id / "evidence" / "raw" / "S01.csv").exists()

    multi = generate_scenario(tmp_path / "multi", scenario="multi_invalid", batch_id="multi")
    invalid = process_batch(spark, root, multi)
    assert invalid.state == "BLOCKED"
    assert invalid.stats["received"] == 5
    assert invalid.stats["rejected"] == 1
    assert invalid.stats["valid"] == 4
    assert invalid.stats["violations"] >= 4
    quarantine = spark.read.format("delta").load(str(root / "runs" / invalid.run_id / "quarantine"))
    assert quarantine.count() == 1
    assert len(quarantine.first()["errors"]) == invalid.stats["violations"]

    divergence = fixture_rows()
    divergence[0]["unit_price_brl"] = "99.00"
    conflict = write_batch(tmp_path / "conflict", divergence, batch_id="conflict")
    result = process_batch(spark, root, conflict)
    assert result.state == "BLOCKED"
    assert result.stats["conflicts"] == 1
    assert result.stats["revision_checks_executed"] == 1
    assert "REVISION_CONFLICT" in {issue["code"] for issue in result.issues}
    within = generate_scenario(tmp_path / "within", scenario="conflict", batch_id="within")
    assert process_batch(spark, root, within).stats["conflicts"] == 2

    changed = write_batch(tmp_path / "changed-id", divergence, batch_id="base")
    result = process_batch(spark, root, changed)
    assert result.state == "BLOCKED"
    assert "BATCH_ID_CONFLICT" in {issue["code"] for issue in result.issues}

    # Revisão de lote rejeitado não entra no histórico aceito.
    poisoned_rows = fixture_rows()
    poisoned_rows[0].update(revision="99", unit_price_brl="99.00")
    poisoned_rows[-1]["product_id"] = "P999"
    poisoned = write_batch(tmp_path / "poisoned", poisoned_rows, batch_id="poisoned")
    assert process_batch(spark, root, poisoned).state == "BLOCKED"
    recovery_rows = fixture_rows()
    recovery_rows[0].update(revision="2", quantity="3", unit_price_brl="11.00")
    recovery = write_batch(tmp_path / "recovery", recovery_rows, batch_id="clean")
    assert_published(process_batch(spark, root, recovery))
    recovered = require_publication(root)
    assert revenue(spark, recovered) == Decimal("77.00")
    assert "poisoned" not in recovered["accepted_batches"]
    assert read_table(spark, recovered, "history").filter("revision = 99").count() == 0


def test_business_timezone_boundary(spark: SparkSession, tmp_path: Path) -> None:
    source = generate_scenario(tmp_path / "input", scenario="timezone", batch_id="timezone")
    root = tmp_path / "state"
    assert_published(process_batch(spark, root, source))
    assert store_values(spark, require_publication(root)) == [
        (date(2026, 1, 1), "S01", Decimal("39.00"), 5, 2, 2, Decimal("19.50")),
        (date(2026, 1, 1), "S02", Decimal("20.00"), 1, 1, 1, Decimal("20.00")),
        (date(2026, 1, 2), "S01", Decimal("5.00"), 1, 1, 1, Decimal("5.00")),
    ]


def test_failure_points_preserve_previous_publication_and_retry(
    spark: SparkSession, tmp_path: Path
) -> None:
    root = tmp_path / "state"
    source = write_batch(tmp_path / "valid", fixture_rows(), batch_id="base")
    assert_published(process_batch(spark, root, source))
    original = require_publication(root)
    failed_rows = fixture_rows()
    failed_rows[0].update(revision="99", unit_price_brl="99.00")
    high_revision = write_batch(tmp_path / "failed-high", failed_rows, batch_id="failed-high")
    failed = process_batch(spark, root, high_revision, fail_at="after_gold", allow_failures=True)
    assert failed.state == "TECHNICAL_FAILURE"
    assert require_publication(root) == original
    alternative_rows = fixture_rows()
    alternative_rows[0].update(revision="2", unit_price_brl="11.00")
    alternative = write_batch(tmp_path / "alternative", alternative_rows, batch_id="alternative")
    assert_published(process_batch(spark, root, alternative))
    snapshot = require_publication(root)
    assert revenue(spark, snapshot) == Decimal("66.00")
    assert "failed-high" not in snapshot["accepted_batches"]
    assert read_table(spark, snapshot, "history").filter("revision = 99").count() == 0
    assert revenue(spark, original) == Decimal("64.00")

    amount = Decimal("66.00")
    for revision, point in enumerate(("after_ingestion", "after_gold", "before_publish"), start=3):
        previous = require_publication(root)
        previous_rows = store_values(spark, previous)
        rows = fixture_rows()
        rows[0].update(revision=str(revision), unit_price_brl=f"{revision + 9}.00")
        candidate = write_batch(tmp_path / point, rows, batch_id=point)
        failed = process_batch(spark, root, candidate, fail_at=point, allow_failures=True)
        assert failed.state == "TECHNICAL_FAILURE", failed.issues
        assert failed.exit_code == 3
        assert require_publication(root) == previous
        assert store_values(spark, previous) == previous_rows
        assert revenue(spark, previous) == amount
        attempt = json.loads((root / "runs" / failed.run_id / "attempt.json").read_text())
        assert attempt["state"] == "TECHNICAL_FAILURE"
        retry = process_batch(spark, root, candidate)
        assert_published(retry)
        amount += Decimal("2.00")
        assert revenue(spark, require_publication(root)) == amount
        assert store_values(spark, previous) == previous_rows
        assert process_batch(spark, root, candidate).state == "NO_CHANGE"


def test_flock_excludes_other_process_and_releases_after_exit(tmp_path: Path) -> None:
    root = tmp_path / "state"
    contender = """
import sys
from pathlib import Path
from retail_pipeline.publication import WriterBusy, writer_lock
try:
    with writer_lock(Path(sys.argv[1])):
        pass
except WriterBusy:
    sys.exit(23)
"""
    with writer_lock(root):
        result = subprocess.run(
            [sys.executable, "-c", contender, str(root)], timeout=15, check=False
        )
        assert result.returncode == 23
    holder = """
import sys
from pathlib import Path
from retail_pipeline.publication import writer_lock
with writer_lock(Path(sys.argv[1])):
    print('locked', flush=True)
    sys.stdin.read()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", holder, str(root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        ready, _, _ = select.select([child.stdout], [], [], 15)
        assert ready, "O escritor filho não sinalizou a aquisição do lock."
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(WriterBusy):
            process_batch(cast(SparkSession, None), root, tmp_path / "unread-delivery")
        assert not (root / "runs").exists()
        assert load_snapshot(root) is None
    finally:
        child.terminate()
        child.wait(timeout=15)
        if child.stdin:
            child.stdin.close()
        if child.stdout:
            child.stdout.close()
    with writer_lock(root):
        assert (root / "writer.lock").is_file()

from decimal import Decimal
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from retail_pipeline import pipeline
from retail_pipeline.generation import fixture_rows, write_batch
from retail_pipeline.publication import Publication, load_snapshot, publish, read_table
from retail_pipeline.reporting import ReportPayload, _read_attempts, build_report_html


@pytest.mark.integration
@pytest.mark.parametrize("failure_point", ["publish", "attempt", "log"])
def test_error_after_pointer_commit_preserves_published_state(
    spark: SparkSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    source = write_batch(tmp_path / "input", fixture_rows(), batch_id="committed")
    root = tmp_path / "state"

    def publish_then_fail(root: Path, snapshot: Publication) -> None:
        publish(root, snapshot)
        raise OSError("Falha simulada depois da troca do ponteiro oficial.")

    real_atomic_json = pipeline.atomic_json
    real_log_event = pipeline.log_event

    def fail_final_attempt(path: Path, value: object) -> None:
        if (
            path.name == "attempt.json"
            and isinstance(value, dict)
            and value.get("state") == "PUBLISHED"
        ):
            raise OSError("Falha simulada na auditoria da tentativa já publicada.")
        real_atomic_json(path, value)

    def fail_final_log(root: Path, result: pipeline.RunResult, stage: str, duration: float) -> None:
        if stage == "complete":
            raise OSError("Falha simulada no log final depois da publicação.")
        real_log_event(root, result, stage, duration)

    if failure_point == "publish":
        monkeypatch.setattr(pipeline, "publish", publish_then_fail)
    elif failure_point == "attempt":
        monkeypatch.setattr(pipeline, "atomic_json", fail_final_attempt)
    else:
        monkeypatch.setattr(pipeline, "log_event", fail_final_log)
    result = pipeline.process_batch(spark, root, source)
    assert result.state == "PUBLISHED", result.issues
    assert result.exit_code == 0
    assert any(
        issue["code"] == "AUDIT_WRITE_FAILURE" and issue["severity"] == "WARNING"
        for issue in result.issues
    )
    snapshot = load_snapshot(root)
    assert snapshot is not None
    assert snapshot["publication_id"] == result.publication_id
    assert snapshot["run_id"] == result.run_id
    assert read_table(spark, snapshot, "silver").count() == 4
    rows = read_table(spark, snapshot, "gold_store_day").orderBy("store_id").collect()
    assert [row["units"] for row in rows] == [6, 1]
    assert [row["net_revenue_brl"] for row in rows] == [Decimal("44.00"), Decimal("20.00")]
    latest, failed = _read_attempts(root, snapshot)
    assert latest is not None and latest["state"] == "PUBLISHED"
    assert failed is None
    if failure_point == "attempt":
        html = build_report_html(ReportPayload(snapshot=snapshot, latest_attempt=latest))
        assert "Publicado, mas o registro final da tentativa falhou." in html
        assert "<dt>Recebidos</dt><dd>—</dd>" in html


@pytest.mark.integration
@pytest.mark.parametrize("reference", ["catalog.json", "schedule.json"])
def test_replay_cannot_silently_change_validation_references(
    spark: SparkSession, tmp_path: Path, reference: str
) -> None:
    import json

    source = write_batch(tmp_path / "input", fixture_rows(), batch_id="reference-fixed")
    root = tmp_path / "state"
    assert pipeline.process_batch(spark, root, source, validate_only=True).state == "VALIDATED"
    path = source / reference
    document = json.loads(path.read_text())
    if reference == "catalog.json":
        document["stores"][0]["name"] = "Nome revisto pelo operador"
    else:
        document["windows"][0]["ends_at"] = "2026-04-01T00:00:00-03:00"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = pipeline.process_batch(spark, root, source)
    assert result.state == "BLOCKED"
    assert "BATCH_REFERENCE_CONFLICT" in {issue["code"] for issue in result.issues}
    assert load_snapshot(root) is None

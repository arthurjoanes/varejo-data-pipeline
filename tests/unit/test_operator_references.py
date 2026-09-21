import json
import sys
from pathlib import Path
from typing import cast

import pytest
from pyspark.sql import SparkSession

from retail_pipeline import cli, spark
from retail_pipeline.generation import default_catalog, default_schedule, fixture_rows, write_batch
from retail_pipeline.ingestion import prepare_batch
from retail_pipeline.pipeline import process_batch
from retail_pipeline.references import configure_references, load_references


def test_sender_cannot_reduce_independently_approved_coverage(tmp_path: Path) -> None:
    references = configure_references(tmp_path / "state", default_catalog(), default_schedule())
    source = write_batch(
        tmp_path / "sender",
        fixture_rows()[:3],
        batch_id="new-id-does-not-authorize-omission",
        expected_stores=("S01", "S03"),
    )
    declared = prepare_batch(source, tmp_path / "declared", "untrusted-format-check")
    assert declared.issues == []  # Reproduz a lacuna: documentos do remetente são coerentes.
    approved = prepare_batch(
        source, tmp_path / "approved", "operator-check", operator_references=references
    )
    assert approved.coverage["expected"] == ["S01", "S02", "S03"]
    assert approved.coverage["missing"] == ["S02"]
    assert {i["code"] for i in approved.issues} == {"MISSING_STORE"}
    evidence = json.loads((tmp_path / "approved/operator-references.json").read_text())
    assert evidence == references.document


def test_operator_configuration_is_idempotent_and_immutable(tmp_path: Path) -> None:
    root = tmp_path / "state"
    original = configure_references(root, default_catalog(), default_schedule())
    assert configure_references(root, default_catalog(), default_schedule()) == original
    with pytest.raises(ValueError, match="já fixadas"):
        configure_references(root, default_catalog(), default_schedule(("S01", "S03")))
    assert load_references(root) == original


def test_missing_operator_config_blocks_before_spark_access(tmp_path: Path) -> None:
    result = process_batch(cast(SparkSession, None), tmp_path / "state", tmp_path / "absent")
    assert result.state == "BLOCKED"
    assert [issue["code"] for issue in result.issues] == ["OPERATOR_REFERENCES_MISSING"]
    assert not (tmp_path / "state/publication.json").exists()


def test_legacy_publication_cannot_inherit_new_trust_without_reprocessing(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    pointer = root / "publication.json"
    pointer.write_text('{"publication_id":"legacy"}')
    with pytest.raises(ValueError, match="legada"):
        configure_references(root, default_catalog(), default_schedule())
    assert pointer.read_text() == '{"publication_id":"legacy"}'
    assert not (root / "operator-references.json").exists()


def test_configure_cli_requires_no_spark(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = tmp_path / "catalog.json"
    schedule = tmp_path / "schedule.json"
    catalog.write_text(json.dumps(default_catalog()))
    schedule.write_text(json.dumps(default_schedule()))
    monkeypatch.setattr(spark, "create_spark", lambda: pytest.fail("Configuração iniciou Spark."))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "varejo",
            "--data-dir",
            str(tmp_path / "state"),
            "configure",
            "--catalog",
            str(catalog),
            "--schedule",
            str(schedule),
        ],
    )
    assert cli.main() == 0
    assert load_references(tmp_path / "state") is not None

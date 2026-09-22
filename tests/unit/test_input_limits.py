from __future__ import annotations

import json
from pathlib import Path

import pytest

from retail_pipeline.generation import default_catalog, default_schedule, generate_scenario
from retail_pipeline.ingestion import _read_json, _snapshot, prepare_batch
from retail_pipeline.input_limits import InputLimits
from retail_pipeline.references import ReferenceConfig


@pytest.mark.parametrize(
    "limits,files,code,expected_bytes",
    [
        (InputLimits(file_bytes=5), {"a.csv": b"123456"}, "INPUT_FILE_BYTES_LIMIT", 5),
        (InputLimits(json_bytes=5), {"a.json": b"123456"}, "INPUT_JSON_BYTES_LIMIT", 5),
        (
            InputLimits(total_bytes=7),
            {"a.csv": b"1234", "b.csv": b"5678"},
            "INPUT_TOTAL_BYTES_LIMIT",
            7,
        ),
        (InputLimits(files=1), {"a.csv": b"1", "b.csv": b"2"}, "INPUT_FILE_COUNT_LIMIT", 1),
    ],
)
def test_snapshot_stops_at_budget_and_labels_partial_evidence(
    tmp_path: Path, limits: InputLimits, files: dict[str, bytes], code: str, expected_bytes: int
) -> None:
    source, raw = tmp_path / "source", tmp_path / "evidence/raw"
    source.mkdir()
    for name, content in files.items():
        (source / name).write_bytes(content)
    issues: list[dict[str, object]] = []
    assert not _snapshot(source, raw, issues, limits)
    assert [issue["code"] for issue in issues] == [code]
    evidence = json.loads((raw.parent / "snapshot.json").read_text())
    assert evidence["complete"] is False
    assert evidence["copied_bytes"] == expected_bytes
    assert evidence["reason"] == code
    assert sum(p.stat().st_size for p in raw.rglob("*") if p.is_file()) == expected_bytes
    assert all((source / name).read_bytes() == content for name, content in files.items())


def test_exact_budget_is_accepted(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.json").write_bytes(b"{}")
    issues: list[dict[str, object]] = []
    raw = tmp_path / "evidence/raw"
    assert _snapshot(source, raw, issues, InputLimits(2, 2, 2, 1))
    assert not issues
    assert json.loads((raw.parent / "snapshot.json").read_text())["complete"] is True


def test_incomplete_snapshot_is_never_parsed_as_a_complete_delivery(tmp_path: Path) -> None:
    source = generate_scenario(tmp_path / "source")
    references = ReferenceConfig(default_catalog(), default_schedule())
    batch = prepare_batch(
        source,
        tmp_path / "evidence",
        "budget",
        limits=InputLimits(files=1),
        operator_references=references,
    )
    assert batch.manifest == {}
    assert batch.stats["received"] == 0
    assert batch.rows_path.read_bytes() == b""
    assert batch.issues[0]["code"] == "INPUT_FILE_COUNT_LIMIT"
    assert (tmp_path / "evidence/quality.json").is_file()
    assert (
        json.loads((tmp_path / "evidence/operator-references.json").read_text())
        == references.document
    )


def test_json_limit_is_checked_before_decode_and_parsing(tmp_path: Path, monkeypatch) -> None:
    document = tmp_path / "references.json"
    document.write_bytes(b"x" * 9)

    def forbidden(*args, **kwargs):
        pytest.fail("oversized JSON reached the parser")

    monkeypatch.setattr(json, "loads", forbidden)
    issues: list[dict[str, object]] = []
    assert _read_json(document, issues, "CATALOG", limits=InputLimits(json_bytes=8)) == {}
    assert issues[0]["code"] == "INPUT_JSON_BYTES_LIMIT"


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_invalid_environment_budget_fails_explicitly(monkeypatch, value: str) -> None:
    monkeypatch.setenv("RETAIL_MAX_FILES", value)
    with pytest.raises(ValueError, match="RETAIL_MAX_FILES deve ser inteiro positivo"):
        InputLimits.from_environment()

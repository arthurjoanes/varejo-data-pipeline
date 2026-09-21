from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import pytest

from retail_pipeline.contracts import BUSINESS_FIELDS, logical_hash, validate_row
from retail_pipeline.generation import fixture_rows, generate_scenario, write_batch
from retail_pipeline.ingestion import prepare_batch


def validate(row: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    return validate_row(
        row,
        source_system="synthetic-pos",
        store_id="S01",
        stores={"S01", "S02", "S03"},
        products={"P01", "P02", "P03"},
    )


def codes(batch: object) -> set[str]:
    return {issue["code"] for issue in batch.issues}


def test_canonical_payload_equates_offsets_integer_and_money() -> None:
    row = fixture_rows()[0]
    alternative = {
        **row,
        "quantity": "02",
        "unit_price_brl": "10",
        "sold_at": "2026-01-01T15:00:00Z",
    }
    canonical, errors = validate(row)
    other, other_errors = validate(alternative)
    assert not errors and not other_errors
    assert logical_hash(canonical) == logical_hash(other)
    assert canonical["unit_price_brl"] == "10.00"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("quantity", "0", "INVALID_QUANTITY"),
        ("quantity", "1.5", "INVALID_QUANTITY"),
        ("quantity", "1000001", "INVALID_QUANTITY"),
        ("revision", "2147483648", "INVALID_REVISION"),
        ("unit_price_brl", "999999999.999", "INVALID_UNIT_PRICE_BRL"),
        ("unit_price_brl", "NaN", "INVALID_UNIT_PRICE_BRL"),
        ("unit_price_brl", "Infinity", "INVALID_UNIT_PRICE_BRL"),
        ("line_discount_brl", "20.01", "DISCOUNT_EXCEEDS_GROSS"),
        ("sold_at", "2026-01-01T12:00:00", "INVALID_SOLD_AT"),
        ("sold_at", "2026-02-30T12:00:00Z", "INVALID_SOLD_AT"),
        ("sold_at", "2026-01-01T12:00:00+01:60", "INVALID_SOLD_AT"),
        ("source_updated_at", "2026-01-01T12:00:00-02:99", "INVALID_SOURCE_UPDATED_AT"),
        ("operation", "cancel", "INVALID_OPERATION"),
        ("product_id", "P404", "UNKNOWN_PRODUCT"),
        ("sale_id", "../outside", "INVALID_SALE_ID"),
    ],
)
def test_invalid_values_remain_diagnosable(field: str, value: str, code: str) -> None:
    canonical, errors = validate({**fixture_rows()[0], field: value})
    assert code in errors
    assert canonical[field] == value


def test_cancel_is_complete_image() -> None:
    row = {**fixture_rows()[0], "operation": "CANCEL", "quantity": "0"}
    assert "INVALID_QUANTITY" in validate(row)[1]


def test_input_alias_cannot_make_snapshot_copy_its_own_evidence(tmp_path: Path) -> None:
    source = generate_scenario(tmp_path / "input")
    (source / "alias").mkdir()
    with pytest.raises(ValueError, match="fora do diretório de entrada"):
        prepare_batch(source / "alias" / "..", source / "evidence", "nested")
    assert not (source / "evidence").exists()


def test_financial_boundary_and_complete_cancel() -> None:
    row = {
        **fixture_rows()[0],
        "operation": "CANCEL",
        "quantity": "1000000",
        "unit_price_brl": "999999999.99",
        "line_discount_brl": "999999999990000.00",
    }
    assert validate(row)[1] == []
    assert (
        "DISCOUNT_EXCEEDS_GROSS" in validate({**row, "line_discount_brl": "999999999990000.01"})[1]
    )


def test_fixture_has_full_independent_coverage(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert prepared.issues == []
    assert prepared.stats == {"received": 4, "valid": 4, "rejected": 0, "violations": 0}
    assert prepared.coverage == {
        "expected": ["S01", "S02", "S03"],
        "received": ["S01", "S02", "S03"],
        "missing": [],
        "zero_movement": ["S03"],
    }
    assert (tmp_path / "evidence/raw/S01.csv").read_bytes() == (folder / "S01.csv").read_bytes()
    evidence = [
        json.loads(line) for line in prepared.rows_path.read_text(encoding="utf-8").splitlines()
    ]
    assert evidence[0]["source_line"] == 2
    assert evidence[0]["raw_payload"]
    assert all(isinstance(row[field], str) for row in evidence for field in BUSINESS_FIELDS)


def test_omitted_store_is_not_hidden_by_manifest(tmp_path: Path) -> None:
    folder = write_batch(tmp_path / "input", fixture_rows()[:3])
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "MISSING_STORE" in codes(prepared)
    assert prepared.coverage["missing"] == ["S02"]


def test_missing_delivery_repaired_with_original_manifest(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    original = (folder / "S02.csv").read_bytes()
    (folder / "S02.csv").unlink()
    missing = prepare_batch(folder, tmp_path / "evidence1", "run-1")
    (folder / "S02.csv").write_bytes(original)
    fixed = prepare_batch(folder, tmp_path / "evidence2", "run-2")
    assert "MISSING_FILE" in codes(missing)
    assert fixed.issues == []
    assert missing.manifest_hash == fixed.manifest_hash


def test_hash_corruption_preserves_actual_bytes(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    with (folder / "S01.csv").open("ab") as handle:
        handle.write(b"broken\n")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert {"HASH_MISMATCH", "ROW_COUNT_MISMATCH", "ROW_WIDTH_MISMATCH"} <= codes(prepared)
    assert prepared.stats["received"] == 5 and prepared.stats["rejected"] == 1
    assert (tmp_path / "evidence/raw/S01.csv").read_bytes().endswith(b"broken\n")


def test_multiviolation_counts_rejected_once(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input", scenario="multi_invalid")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert prepared.stats == {"received": 5, "valid": 4, "rejected": 1, "violations": 4}
    assert {
        "INVALID_QUANTITY",
        "INVALID_UNIT_PRICE_BRL",
        "UNKNOWN_PRODUCT",
        "INVALID_SOLD_AT",
    } <= codes(prepared)


def test_header_only_requires_explicit_zero(tmp_path: Path) -> None:
    folder = write_batch(tmp_path / "input", [], zero_movement=("S01", "S02", "S03"))
    path = folder / "S01.csv"
    path.write_text(",".join(BUSINESS_FIELDS) + "\n", encoding="utf-8")
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["files"] = [
        {
            "path": "S01.csv",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "row_count": 0,
            "store_id": "S01",
        }
    ]
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    good = prepare_batch(folder, tmp_path / "good", "run-1")
    assert not good.issues
    assert good.rows_path.read_text() == ""
    manifest["zero_movement"].remove("S01")
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    bad = prepare_batch(folder, tmp_path / "bad", "run-2")
    assert "EMPTY_WITHOUT_ZERO_CONFIRMATION" in codes(bad)


@pytest.mark.parametrize(
    "unsafe", ["../escape.csv", "/absolute.csv", "C:/drive.csv", "x\\y.csv", "x//y.csv", "./x.csv"]
)
def test_unsafe_manifest_paths(tmp_path: Path, unsafe: str) -> None:
    folder = generate_scenario(tmp_path / "input")
    path = folder / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"][0]["path"] = unsafe
    path.write_text(json.dumps(manifest), encoding="utf-8")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "UNSAFE_PATH" in codes(prepared)


def test_missing_configuration_is_quality_failure(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    (folder / "catalog.json").unlink()
    (folder / "schedule.json").write_text("[]", encoding="utf-8")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert {"INVALID_CATALOG", "INVALID_SCHEDULE"} <= codes(prepared)


def test_invalid_utf8_preserved_and_blocked(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    (folder / "S01.csv").write_bytes(b"\xff\xfe\x00")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "CSV_DECODE_ERROR" in codes(prepared)
    assert (tmp_path / "evidence/raw/S01.csv").read_bytes() == b"\xff\xfe\x00"


@pytest.mark.skipif(os.name == "nt", reason="Teste real de symlink executado no container Linux.")
def test_symlink_is_rejected_without_copying_target(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    target = tmp_path / "private.csv"
    target.write_text("private", encoding="utf-8")
    (folder / "leak.csv").symlink_to(target)
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "UNSAFE_SYMLINK" in codes(prepared)
    assert not (tmp_path / "evidence/raw/leak.csv").exists()


@pytest.mark.skipif(os.name == "nt", reason="FIFO é um tipo de arquivo Linux.")
def test_special_file_cannot_block_the_snapshot(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    os.mkfifo(folder / "unexpected.csv")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "UNSAFE_FILE_TYPE" in codes(prepared)
    assert not (tmp_path / "evidence/raw/unexpected.csv").exists()


def test_exact_csv_schema_and_unknown_reference(tmp_path: Path) -> None:
    rows = fixture_rows()
    rows[0]["product_id"] = "P404"
    folder = write_batch(tmp_path / "input", rows)
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "UNKNOWN_PRODUCT" in codes(prepared)
    with (folder / "S01.csv").open(encoding="utf-8", newline="") as handle:
        data = list(csv.reader(handle))
    data[0][0] = "source"
    with (folder / "S01.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(data)
    bad = prepare_batch(folder, tmp_path / "evidence2", "run-2")
    assert "SCHEMA_MISMATCH" in codes(bad)


def test_reordering_manifest_lists_keeps_logical_identity(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    first = prepare_batch(folder, tmp_path / "evidence1", "run-1")
    path = folder / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"].reverse()
    manifest["covered_stores"].reverse()
    path.write_text(json.dumps(manifest, indent=4), encoding="utf-8")
    second = prepare_batch(folder, tmp_path / "evidence2", "run-2")
    assert first.manifest_hash == second.manifest_hash


@pytest.mark.parametrize("filename", ["extra.txt", "external.avro", "external.parquet"])
def test_unexpected_file_is_kept_but_blocks(tmp_path: Path, filename: str) -> None:
    folder = generate_scenario(tmp_path / "input")
    (folder / filename).write_text("unexpected", encoding="utf-8")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "UNEXPECTED_FILE" in codes(prepared)
    assert (tmp_path / "evidence/raw" / filename).read_text() == "unexpected"


@pytest.mark.parametrize(
    "text",
    [
        '{"schema_version":NaN}',
        '{"schema_version":1,"schema_version":2}',
        '{"batch_id":"\\ud800"}',
        '{"nested":' + "[" * 1500 + "0" + "]" * 1500 + "}",
    ],
)
def test_invalid_json_never_escapes_as_technical_error(tmp_path: Path, text: str) -> None:
    folder = generate_scenario(tmp_path / "input")
    (folder / "manifest.json").write_text(text, encoding="utf-8")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert "INVALID_MANIFEST" in codes(prepared)


def test_delivery_interval_is_not_business_date_filter(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    path = folder / "schedule.json"
    schedule = json.loads(path.read_text())
    schedule["windows"][0]["starts_at"] = "2026-02-01T00:00:00-03:00"
    path.write_text(json.dumps(schedule), encoding="utf-8")
    good = prepare_batch(folder, tmp_path / "good", "run-1")
    assert not good.issues
    schedule["windows"][0]["ends_at"] = "2026-01-01T00:00:00-03:00"
    path.write_text(json.dumps(schedule), encoding="utf-8")
    bad = prepare_batch(folder, tmp_path / "bad", "run-2")
    assert "INVALID_DELIVERY_INTERVAL" in codes(bad)


def test_catalog_and_unselected_schedule_are_validated(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    catalog_path = folder / "catalog.json"
    catalog = json.loads(catalog_path.read_text())
    catalog["stores"][0]["active"] = False
    catalog["products"].append(dict(catalog["products"][0]))
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    schedule_path = folder / "schedule.json"
    schedule = json.loads(schedule_path.read_text())
    schedule["windows"].append(
        {**schedule["windows"][0], "window_id": "unselected", "stores": ["S999"]}
    )
    schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    assert {"DUPLICATE_REFERENCE", "UNKNOWN_STORE", "INVALID_SCHEDULE_STORES"} <= codes(prepared)


def test_evidence_remains_stable_when_original_changes(tmp_path: Path) -> None:
    folder = generate_scenario(tmp_path / "input")
    prepared = prepare_batch(folder, tmp_path / "evidence", "run-1")
    evidence = prepared.rows_path.read_bytes()
    (folder / "S01.csv").write_bytes(b"changed later")
    assert prepared.rows_path.read_bytes() == evidence
    assert (tmp_path / "evidence/raw/S01.csv").read_bytes() != b"changed later"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("quantity", "", "INVALID_QUANTITY"),
        ("quantity", "-1", "INVALID_QUANTITY"),
        ("quantity", "1e3", "INVALID_QUANTITY"),
        ("quantity", "１", "INVALID_QUANTITY"),
        ("quantity", "9" * 5000, "INVALID_QUANTITY"),
        ("revision", "0", "INVALID_REVISION"),
        ("revision", "-1", "INVALID_REVISION"),
        ("unit_price_brl", "-0.01", "INVALID_UNIT_PRICE_BRL"),
        ("unit_price_brl", "1,00", "INVALID_UNIT_PRICE_BRL"),
        ("unit_price_brl", "1e2", "INVALID_UNIT_PRICE_BRL"),
        ("unit_price_brl", " 1.00", "INVALID_UNIT_PRICE_BRL"),
        ("unit_price_brl", "1000000000.00", "INVALID_UNIT_PRICE_BRL"),
        ("line_discount_brl", "-0.01", "INVALID_LINE_DISCOUNT_BRL"),
        ("line_discount_brl", "10000000000000000.00", "INVALID_LINE_DISCOUNT_BRL"),
        ("sale_id", "A" * 65, "INVALID_SALE_ID"),
        ("sale_id", "venda com espaço", "INVALID_SALE_ID"),
        ("source_system", "other", "SOURCE_MISMATCH"),
        ("store_id", "S02", "FILE_STORE_MISMATCH"),
        ("sold_at", "2026-01-01T12:00:60Z", "INVALID_SOLD_AT"),
        ("sold_at", "2026-01-01T12:00:00+24:00", "INVALID_SOLD_AT"),
        ("sold_at", "0001-01-01T00:00:00Z", "INVALID_SOLD_AT"),
        ("sold_at", "9999-12-31T23:59:59-23:59", "INVALID_SOLD_AT"),
        ("source_updated_at", "0001-01-01T00:00:00+23:59", "INVALID_SOURCE_UPDATED_AT"),
        ("source_updated_at", "9999-12-31T23:59:59-01:00", "INVALID_SOURCE_UPDATED_AT"),
    ],
)
def test_boundary_values_are_rejections_not_conversion_exceptions(
    field: str, value: str, code: str
) -> None:
    assert code in validate({**fixture_rows()[0], field: value})[1]


def test_zero_price_and_full_discount_are_valid_sales() -> None:
    base = fixture_rows()[0]
    assert validate({**base, "unit_price_brl": "0", "line_discount_brl": "0"})[1] == []
    assert validate({**base, "line_discount_brl": "20.00"})[1] == []
    assert validate({**base, "revision": "2147483647", "sale_id": "A" * 64})[1] == []


def test_explicit_empty_catalog_is_preserved_and_rejected(tmp_path: Path) -> None:
    source = write_batch(tmp_path / "input", fixture_rows(), catalog={})
    assert json.loads((source / "catalog.json").read_text()) == {}
    prepared = prepare_batch(source, tmp_path / "evidence", "empty-catalog")
    assert {"CATALOG_SCHEMA_VERSION", "INVALID_CATALOG"} <= codes(prepared)


@pytest.mark.parametrize(
    "document,field,value,expected",
    [
        ("manifest.json", "schema_version", True, "UNSUPPORTED_SCHEMA_VERSION"),
        ("manifest.json", "zero_movement", ["S03", "S03"], "INVALID_ZERO_CONFIRMATION"),
        ("manifest.json", "covered_stores", ["S01", "S02"], "COVERAGE_MISMATCH"),
        ("manifest.json", "correction_of", "../base", "INVALID_MANIFEST_FIELD"),
        ("manifest.json", "unknown", 1, "UNKNOWN_MANIFEST_FIELDS"),
        ("catalog.json", "schema_version", True, "CATALOG_SCHEMA_VERSION"),
        ("catalog.json", "stores", [], "INVALID_CATALOG"),
        ("catalog.json", "products", "P01", "INVALID_CATALOG"),
        ("schedule.json", "schema_version", True, "SCHEDULE_SCHEMA_VERSION"),
        ("schedule.json", "windows", {}, "INVALID_SCHEDULE"),
        ("schedule.json", "windows", [], "UNKNOWN_OR_DUPLICATE_WINDOW"),
    ],
)
def test_document_shapes_preserve_diagnostics(
    tmp_path: Path, document: str, field: str, value: object, expected: str
) -> None:
    source = generate_scenario(tmp_path / "input")
    path = source / document
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    assert expected in codes(prepare_batch(source, tmp_path / "evidence", "shape"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("row_count", True),
        ("row_count", -1),
        ("row_count", "4"),
        ("sha256", "0" * 63),
        ("store_id", "../S01"),
    ],
)
def test_manifest_entry_types_are_strict(tmp_path: Path, field: str, value: object) -> None:
    source = generate_scenario(tmp_path / "input")
    path = source / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"][0][field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "INVALID_MANIFEST_FILE" in codes(prepare_batch(source, tmp_path / "evidence", "entry"))

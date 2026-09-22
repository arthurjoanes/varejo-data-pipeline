"""Snapshot físico primeiro; validação streaming do contrato depois."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from retail_pipeline.batch_contracts import add_issue, validate_manifest, validate_references
from retail_pipeline.contracts import (
    BUSINESS_FIELDS,
    logical_hash,
    stable_json,
    valid_identifier,
    validate_row,
)
from retail_pipeline.input_limits import InputLimits
from retail_pipeline.references import ReferenceConfig


@dataclass(frozen=True)
class PreparedBatch:
    batch_id: str
    manifest_hash: str
    manifest: dict[str, object]
    rows_path: Path
    issues: list[dict[str, object]]
    stats: dict[str, int]
    coverage: dict[str, list[str]]
    reference_hashes: dict[str, str | None]


def _snapshot(
    source: Path, target: Path, issues: list[dict[str, object]], limits: InputLimits
) -> bool:
    target.mkdir(parents=True, exist_ok=False)
    copied_bytes = 0
    file_count = 0

    def finish(complete: bool, code: str | None = None, path: str | None = None) -> bool:
        if code:
            add_issue(issues, code, file=path, message="Entrega excede o orçamento configurado.")
        (target.parent / "snapshot.json").write_text(
            stable_json(
                {
                    "complete": complete,
                    "copied_bytes": copied_bytes,
                    "files_seen": file_count,
                    "limits": asdict(limits),
                    "stopped_at": path,
                    "reason": code,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return complete

    if not source.is_dir() or source.is_symlink():
        add_issue(issues, "INPUT_NOT_DIRECTORY")
        return finish(False)
    for parent, directories, files in os.walk(source, followlinks=False):
        directories.sort()
        files.sort()
        for name in list(directories):
            candidate = Path(parent) / name
            if candidate.is_symlink():
                add_issue(issues, "UNSAFE_SYMLINK", file=candidate.relative_to(source).as_posix())
                directories.remove(name)
        for name in files:
            candidate = Path(parent) / name
            relative = candidate.relative_to(source)
            file_count += 1
            if file_count > limits.files:
                return finish(False, "INPUT_FILE_COUNT_LIMIT", relative.as_posix())
            if candidate.is_symlink():
                add_issue(issues, "UNSAFE_SYMLINK", file=relative.as_posix())
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                if not stat.S_ISREG(candidate.lstat().st_mode):
                    add_issue(issues, "UNSAFE_FILE_TYPE", file=relative.as_posix())
                    continue
                descriptor = os.open(
                    candidate,
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                    | getattr(os, "O_BINARY", 0),
                )
                with os.fdopen(descriptor, "rb") as original:
                    if not stat.S_ISREG(os.fstat(original.fileno()).st_mode):
                        add_issue(issues, "UNSAFE_FILE_TYPE", file=relative.as_posix())
                        continue
                    with destination.open("wb") as copied:
                        file_bytes = 0
                        ceiling = limits.file_bytes
                        code = "INPUT_FILE_BYTES_LIMIT"
                        if relative.suffix.lower() == ".json" and limits.json_bytes < ceiling:
                            ceiling, code = limits.json_bytes, "INPUT_JSON_BYTES_LIMIT"
                        while True:
                            available = min(ceiling - file_bytes, limits.total_bytes - copied_bytes)
                            # One extra byte distinguishes exact-fit from oversized input,
                            # including a file that grows after it was opened/stat'ed.
                            block = original.read(min(64 * 1024, available + 1))
                            if not block:
                                break
                            accepted = block[:available]
                            copied.write(accepted)
                            file_bytes += len(accepted)
                            copied_bytes += len(accepted)
                            if len(block) > available:
                                if file_bytes < ceiling:
                                    code = "INPUT_TOTAL_BYTES_LIMIT"
                                return finish(False, code, relative.as_posix())
            except OSError as error:
                add_issue(issues, "FILE_COPY_FAILED", file=relative.as_posix(), message=str(error))
    return finish(True)


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Constante JSON inválida: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Campo JSON duplicado: {key}")
        result[key] = value
    return result


def _read_json(
    path: Path, issues: list[dict[str, object]], label: str, *, limits: InputLimits | None = None
) -> dict[str, object]:
    limits = limits or InputLimits.from_environment()
    try:
        with path.open("rb") as handle:
            payload = handle.read(limits.json_bytes + 1)
        if len(payload) > limits.json_bytes:
            add_issue(issues, "INPUT_JSON_BYTES_LIMIT", file=path.name, limit=limits.json_bytes)
            return {}
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=_reject_nonfinite,
            object_pairs_hook=_unique_object,
        )
        if not isinstance(value, dict):
            raise ValueError("A raiz deve ser um objeto JSON.")
        stable_json(value).encode("utf-8")
        return value
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        add_issue(issues, f"INVALID_{label}", file=path.name, message=str(error))
        return {}


def _rows(
    path: Path,
    entry: dict[str, object],
    manifest: dict[str, object],
    run_id: str,
    stores: set[str],
    products: set[str],
    output: TextIO,
    stats: dict[str, int],
    issues: list[dict[str, object]],
) -> int:
    count = 0
    digest = hashlib.sha256()
    with path.open("rb") as binary:
        for block in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != entry["sha256"]:
        add_issue(issues, "HASH_MISMATCH", file=entry["path"])
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                header = next(reader)
            except StopIteration:
                add_issue(issues, "EMPTY_FILE", file=entry["path"])
                return 0
            schema_ok = tuple(header) == BUSINESS_FIELDS
            if not schema_ok:
                add_issue(issues, "SCHEMA_MISMATCH", file=entry["path"], observed=header)
            while True:
                line = reader.line_num + 1
                try:
                    cells = next(reader)
                except StopIteration:
                    break
                count += 1
                payload = dict(zip(header, cells, strict=False))
                row, errors = validate_row(
                    payload,
                    source_system=str(manifest.get("source_system", "")),
                    store_id=str(entry["store_id"]),
                    stores=stores,
                    products=products,
                )
                if not schema_ok:
                    errors.insert(0, "SCHEMA_MISMATCH")
                if len(cells) != len(header):
                    errors.insert(0, "ROW_WIDTH_MISMATCH")
                row_payload: dict[str, object] = dict(row)
                row_payload.update(
                    batch_id=manifest.get("batch_id", ""),
                    run_id=run_id,
                    source_file=entry["path"],
                    source_line=line,
                    payload_hash=logical_hash(row),
                    errors=errors,
                    raw_payload=stable_json({"header": header, "values": cells}),
                )
                output.write(stable_json(row_payload) + "\n")
                stats["received"] += 1
                stats["rejected"] += bool(errors)
                stats["valid"] += not errors
                stats["violations"] += len(errors)
                for code in errors:
                    # Detalhes por linha ficam no NDJSON; o resumo em memória tem tamanho limitado.
                    found = next(
                        (
                            item
                            for item in issues
                            if item.get("code") == code and item.get("scope") == "row"
                        ),
                        None,
                    )
                    if found is None:
                        add_issue(issues, code, scope="row", count=1, file=entry["path"], line=line)
                    else:
                        found["count"] = int(str(found["count"])) + 1
    except (UnicodeError, csv.Error) as error:
        add_issue(issues, "CSV_DECODE_ERROR", file=entry["path"], message=str(error))
    return count


def prepare_batch(
    input_dir: Path,
    evidence_dir: Path,
    run_id: str,
    *,
    operator_references: ReferenceConfig | None = None,
    limits: InputLimits | None = None,
) -> PreparedBatch:
    """Valida documentos; `process_batch` sempre exige referências externas aprovadas.

    Sem referências externas, esta função só verifica o contrato declarado da entrega;
    esse modo isolado não autoriza publicação e serve aos testes de formato.
    """
    issues: list[dict[str, object]] = []
    limits = limits or InputLimits.from_environment()
    raw = evidence_dir / "raw"
    input_dir = input_dir.absolute()
    if raw.resolve().is_relative_to(input_dir.resolve()):
        raise ValueError("A cópia deve ficar fora do diretório de entrada.")
    complete = _snapshot(input_dir, raw, issues, limits)
    if operator_references is not None:
        (evidence_dir / "operator-references.json").write_text(
            stable_json(operator_references.document) + "\n", encoding="utf-8"
        )
    if not complete:
        rows_path = evidence_dir / "rows.ndjson"
        rows_path.write_text("", encoding="utf-8")
        stats = {"received": 0, "valid": 0, "rejected": 0, "violations": 0}
        incomplete_coverage: dict[str, list[str]] = {
            "expected": [],
            "received": [],
            "missing": [],
            "zero_movement": [],
        }
        (evidence_dir / "quality.json").write_text(
            stable_json({"issues": issues, "stats": stats, "coverage": incomplete_coverage}) + "\n",
            encoding="utf-8",
        )
        return PreparedBatch(
            f"incomplete-{run_id}",
            logical_hash({}),
            {},
            rows_path,
            issues,
            stats,
            incomplete_coverage,
            {"catalog.json": None, "schedule.json": None},
        )
    manifest = _read_json(raw / "manifest.json", issues, "MANIFEST", limits=limits)
    manifest_hash, files, zero = validate_manifest(manifest, issues)
    catalog = _read_json(raw / "catalog.json", issues, "CATALOG", limits=limits)
    schedule = _read_json(raw / "schedule.json", issues, "SCHEDULE", limits=limits)
    stores, products, expected = validate_references(catalog, schedule, manifest, issues)
    if operator_references is not None:
        stores, products, expected = validate_references(
            operator_references.catalog, operator_references.schedule, manifest, issues
        )
    reference_hashes = {
        name: hashlib.sha256((raw / name).read_bytes()).hexdigest()
        if (raw / name).is_file()
        else None
        for name in ("catalog.json", "schedule.json")
    }
    batch_id = str(manifest.get("batch_id", ""))
    if not valid_identifier(batch_id):
        batch_id = f"invalid-{manifest_hash[:12]}"
    stats = {"received": 0, "valid": 0, "rejected": 0, "violations": 0}
    received: set[str] = set()
    rows_path = evidence_dir / "rows.ndjson"
    known = {"manifest.json", "catalog.json", "schedule.json"} | {
        str(entry["path"]) for entry in files
    }
    observed = {path.relative_to(raw).as_posix() for path in raw.rglob("*") if path.is_file()}
    for unexpected_path in sorted(observed - known):
        add_issue(issues, "UNEXPECTED_FILE", file=unexpected_path)
    counts: dict[str, int] = {}
    with rows_path.open("w", encoding="utf-8", newline="\n") as output:
        for entry in files:
            path = raw / str(entry["path"])
            store = str(entry["store_id"])
            if store not in stores or store not in expected:
                add_issue(issues, "UNEXPECTED_STORE", store_id=store)
            if not path.is_file():
                add_issue(issues, "MISSING_FILE", file=entry["path"], store_id=store)
                continue
            received.add(store)
            count = _rows(path, entry, manifest, run_id, stores, products, output, stats, issues)
            counts[store] = counts.get(store, 0) + count
            if count != entry["row_count"]:
                add_issue(
                    issues,
                    "ROW_COUNT_MISMATCH",
                    file=entry["path"],
                    expected=entry["row_count"],
                    received=count,
                )
            if count == 0 and store not in zero:
                add_issue(issues, "EMPTY_WITHOUT_ZERO_CONFIRMATION", store_id=store)
    for store in sorted(zero):
        if store not in expected or counts.get(store, 0) != 0:
            add_issue(issues, "INVALID_ZERO_CONFIRMATION", store_id=store)
    received |= zero & expected
    missing = expected - received
    for store in sorted(missing):
        add_issue(issues, "MISSING_STORE", store_id=store)
    declared = {str(entry["store_id"]) for entry in files} | zero
    if "covered_stores" in manifest:
        coverage = manifest["covered_stores"]
        if (
            not isinstance(coverage, list)
            or not all(valid_identifier(item) for item in coverage)
            or len(set(coverage)) != len(coverage)
            or set(coverage) != declared
        ):
            add_issue(issues, "COVERAGE_MISMATCH")
    coverage_result = {
        "expected": sorted(expected),
        "received": sorted(received),
        "missing": sorted(missing),
        "zero_movement": sorted(zero),
    }
    (evidence_dir / "quality.json").write_text(
        stable_json({"issues": issues, "stats": stats, "coverage": coverage_result}) + "\n",
        encoding="utf-8",
    )
    return PreparedBatch(
        batch_id,
        manifest_hash,
        manifest,
        rows_path,
        issues,
        stats,
        coverage_result,
        reference_hashes,
    )

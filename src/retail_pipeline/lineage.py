"""Offline OpenLineage adapter; durable publication remains the commit authority."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]
from referencing import Registry, Resource

from retail_pipeline.contracts import BUSINESS_FIELDS

UPSTREAM_COMMIT = "4e4a9186962094ce5fd29c5e4bc9d5ddb5fa39a8"
UPSTREAM = f"https://raw.githubusercontent.com/OpenLineage/OpenLineage/{UPSTREAM_COMMIT}/spec"
UPSTREAM_SCHEMA_HASHES = {
    "OpenLineage.json": "69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2",
    "SchemaDatasetFacet.json": "b1ed03c11391ebb89ffc5212f303702a46cc0f528dbf1ddeb591616288c8c10f",
    "DatasetVersionDatasetFacet.json": "91f57b67bc6d639bb6d600e26b827dac551e3520a233d1785d65870da263dc34",
    "ErrorMessageRunFacet.json": "b11b4ee8b0f99f6846264f87cad48390255c7ef142ce623216660c7097be0ea6",
}
EVENT_SCHEMA_URL = f"{UPSTREAM}/OpenLineage.json#/$defs/RunEvent"
PRODUCER = "https://github.com/arthurjoanes/varejo-data-pipeline"
JOB_NAMESPACE = "urn:varejo-data-pipeline:local"
DATASET_NAMESPACE = "urn:varejo-data-pipeline:delta"
REFERENCE_NAMESPACE = "urn:varejo-data-pipeline:references"
LEGACY_UUID_NAMESPACE = uuid.UUID("b04ef31f-0b44-5cfa-9300-c6bba32ea0b0")
SCHEMA_DIR = Path(__file__).with_name("schemas")
TERMINAL_TYPES = {
    "PUBLISHED": "COMPLETE",
    "NO_CHANGE": "COMPLETE",
    "VALIDATED": "COMPLETE",
    "BLOCKED": "FAIL",
    "TECHNICAL_FAILURE": "FAIL",
}
_HASH = re.compile(r"^[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _format_checker() -> FormatChecker:
    checker = FormatChecker()
    required = {"uuid", "date", "date-time", "uri"}
    if not required <= checker.checkers.keys():
        raise RuntimeError("Validadores locais de UUID/data/URI ausentes; confira as dependências.")
    return checker


def canonical_run_id(run_id: str) -> str:
    """UUID hex keeps its identity; non-UUID legacy identifiers use a fixed UUIDv5."""
    if not run_id:
        raise ValueError("run_id não pode ser vazio.")
    try:
        return str(uuid.UUID(run_id))
    except ValueError:
        return str(uuid.uuid5(LEGACY_UUID_NAMESPACE, run_id))


def _identifier(value: object) -> str:
    text = str(value)
    return (
        text
        if _IDENTIFIER.fullmatch(text)
        else "sha256:" + hashlib.sha256(text.encode()).hexdigest()
    )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Objeto JSON esperado em {path.name}.")
    return cast(dict[str, Any], value)


@lru_cache(maxsize=1)
def _schema_resources() -> tuple[dict[str, dict[str, Any]], Registry[Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    registry: Registry[Any] = Registry()
    for name in (
        "OpenLineage.json",
        "SchemaDatasetFacet.json",
        "DatasetVersionDatasetFacet.json",
        "ErrorMessageRunFacet.json",
        "VarejoFacets.json",
    ):
        content = (SCHEMA_DIR / name).read_bytes()
        if (
            name in UPSTREAM_SCHEMA_HASHES
            and hashlib.sha256(content).hexdigest() != UPSTREAM_SCHEMA_HASHES[name]
        ):
            raise ValueError(f"Schema oficial fixado adulterado: {name}.")
        schema = json.loads(content)
        Draft202012Validator.check_schema(schema)
        schemas[name] = schema
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(
            "urn:sha256:" + hashlib.sha256(content).hexdigest(), resource
        )
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
        relative = name if name == "OpenLineage.json" else f"facets/{name}"
        if name != "VarejoFacets.json":
            registry = registry.with_resource(f"{UPSTREAM}/{relative}", resource)
    return schemas, registry


@lru_cache(maxsize=3)
def _custom_url(definition: str) -> str:
    content = (SCHEMA_DIR / "VarejoFacets.json").read_bytes()
    return f"urn:sha256:{hashlib.sha256(content).hexdigest()}#/$defs/{definition}"


def _facet(schema_url: str, **values: Any) -> dict[str, Any]:
    return {"_producer": PRODUCER, "_schemaURL": schema_url, **values}


def validate_event(event: Mapping[str, Any]) -> None:
    """Validate the pinned core and used facets with formats, resolving locally only."""
    schemas, registry = _schema_resources()
    checker = _format_checker()
    Draft202012Validator(
        schemas["OpenLineage.json"], registry=registry, format_checker=checker
    ).validate(event)
    if event.get("eventType") not in {"START", "COMPLETE", "FAIL"}:
        raise ValueError("O adaptador exige START, COMPLETE ou FAIL.")
    if event.get("schemaURL") != EVENT_SCHEMA_URL:
        raise ValueError("Evento não usa o schema OpenLineage fixado.")
    validators = {
        "schema": ("SchemaDatasetFacet.json", "SchemaDatasetFacet"),
        "version": ("DatasetVersionDatasetFacet.json", "DatasetVersionDatasetFacet"),
        "errorMessage": ("ErrorMessageRunFacet.json", "ErrorMessageRunFacet"),
        "varejo_outcome": ("VarejoFacets.json", "VarejoOutcomeRunFacet"),
        "varejo_timing": ("VarejoFacets.json", "VarejoTimingRunFacet"),
        "varejo_provenance": ("VarejoFacets.json", "VarejoProvenanceDatasetFacet"),
    }
    entities = [event["run"], event["job"], *event.get("inputs", []), *event.get("outputs", [])]
    for entity in entities:
        for name, facet in entity.get("facets", {}).items():
            if name not in validators:
                raise ValueError(f"Faceta não suportada pelo contrato local: {name}.")
            filename, definition = validators[name]
            validator_schema = {"$ref": f"#/$defs/{definition}", **schemas[filename]}
            # Facet files have a top-level property wrapper; $ref validates its definition.
            Draft202012Validator(
                validator_schema, registry=registry, format_checker=checker
            ).validate(facet)
            relative = f"facets/{filename}"
            expected = (
                _custom_url(definition)
                if filename == "VarejoFacets.json"
                else f"{UPSTREAM}/{relative}#/$defs/{definition}"
            )
            if facet.get("_schemaURL") != expected:
                raise ValueError(f"schemaURL divergente na faceta {name}.")


def _timestamp(value: object) -> str | None:
    if isinstance(value, str) and _format_checker().conforms(value, "date-time"):
        return value
    return None


def _timing(
    attempt: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None,
    *,
    start: bool,
    reconstructed: bool,
) -> tuple[str, dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    source = "attempt.started_at" if start else "attempt.finished_at"
    original = _timestamp(attempt.get("started_at" if start else "finished_at"))
    if not start and original is None and snapshot and attempt.get("state") == "PUBLISHED":
        source, original = "publication.published_at", _timestamp(snapshot.get("published_at"))
    run_id = str(attempt["run_id"])
    try:
        uuid.UUID(run_id)
        mapping = "uuid"
    except ValueError:
        mapping = "uuid5"
    values: dict[str, Any] = {
        "originalTimeAvailable": original is not None,
        "eventTimeSource": source if original else "reconstruction",
        "identityMapping": mapping,
    }
    if original:
        values["originalEventTime"] = original
    if reconstructed or original is None:
        values["reconstructedAt"] = now
    return original or now, _facet(_custom_url("VarejoTimingRunFacet"), **values)


def _fields(table: str) -> list[dict[str, str]]:
    fields = {name: "string" for name in BUSINESS_FIELDS}
    fields.update(
        batch_id="string",
        run_id="string",
        source_file="string",
        source_line="integer",
        payload_hash="string",
        raw_payload="string",
        errors="array<string>",
    )
    if table in {"history", "silver"}:
        fields.update(
            revision="integer",
            quantity="integer",
            unit_price_brl="decimal(18,2)",
            line_discount_brl="decimal(18,2)",
            sold_at="timestamp",
            source_updated_at="timestamp",
            business_date="date",
            line_net_brl="decimal(24,2)",
        )
    if table.startswith("gold_"):
        dimension = "store_id" if table == "gold_store_day" else "product_id"
        fields = {
            "business_date": "date",
            dimension: "string",
            "net_revenue_brl": "decimal(28,2)",
            "units": "long",
            "item_lines": "long",
        }
        if table == "gold_store_day":
            fields.update(sales_count="long", average_ticket_brl="decimal(28,2)")
    return [{"name": name, "type": datatype} for name, datatype in fields.items()]


def _dataset(name: str, version: int, table: str) -> dict[str, Any]:
    if type(version) is not int or version < 0:
        raise ValueError("Versão Delta precisa ser um inteiro não negativo.")
    return {
        "namespace": DATASET_NAMESPACE,
        "name": name,
        "facets": {
            "version": _facet(
                f"{UPSTREAM}/facets/DatasetVersionDatasetFacet.json#/$defs/DatasetVersionDatasetFacet",
                datasetVersion=str(version),
            ),
            "schema": _facet(
                f"{UPSTREAM}/facets/SchemaDatasetFacet.json#/$defs/SchemaDatasetFacet",
                fields=_fields(table),
            ),
        },
    }


def _inputs(snapshot: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    datasets: dict[tuple[str, str], dict[str, Any]] = {}
    if snapshot is None:
        return []
    for source in snapshot.get("sources", []):
        run_id = canonical_run_id(str(source["run_id"]))
        dataset = _dataset(f"bronze/{run_id}", source["bronze_version"], "bronze")
        provenance: dict[str, Any] = {
            "batchId": _identifier(source["batch_id"]),
            "sourceRunId": run_id,
            "accepted": True,
        }
        hashes = source.get("reference_hashes")
        if isinstance(hashes, dict):
            provenance["referenceHashes"] = {
                _identifier(key): value
                for key, value in hashes.items()
                if value is None or (isinstance(value, str) and _HASH.fullmatch(value))
            }
            for kind, digest in provenance["referenceHashes"].items():
                if digest:
                    ref = {"namespace": REFERENCE_NAMESPACE, "name": f"{kind}/sha256:{digest}"}
                    datasets[(ref["namespace"], ref["name"])] = ref
        digest = source.get("operator_reference_hash")
        if isinstance(digest, str) and _HASH.fullmatch(digest):
            provenance["operatorReferenceHash"] = digest
            ref = {"namespace": REFERENCE_NAMESPACE, "name": f"approved/sha256:{digest}"}
            datasets[(ref["namespace"], ref["name"])] = ref
        manifest_hash = source.get("manifest_hash")
        if isinstance(manifest_hash, str) and _HASH.fullmatch(manifest_hash):
            provenance["manifestHash"] = manifest_hash
        dataset["facets"]["varejo_provenance"] = _facet(
            _custom_url("VarejoProvenanceDatasetFacet"), **provenance
        )
        datasets[(DATASET_NAMESPACE, dataset["name"])] = dataset
    return [datasets[key] for key in sorted(datasets)]


def build_event(
    attempt: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None = None,
    start: bool = False,
    reconstructed: bool = False,
) -> dict[str, Any]:
    """Pure mapping. Only pass snapshots proved committed, never a candidate file."""
    state = "RUNNING" if start else str(attempt["state"])
    if not start and state not in TERMINAL_TYPES:
        raise ValueError(f"Estado sem terminal: {state}.")
    job_mode = attempt.get(
        "job_mode", "validate" if attempt.get("state") == "VALIDATED" else "publish"
    )
    if job_mode not in {"publish", "validate"}:
        raise ValueError("Modo do job inválido.")
    if state == "PUBLISHED" and (
        snapshot is None or str(snapshot["run_id"]) != str(attempt["run_id"])
    ):
        raise ValueError("PUBLISHED exige publicação comprometida da mesma execução.")
    if state == "NO_CHANGE" and (
        snapshot is None or snapshot["publication_id"] != attempt.get("publication_id")
    ):
        raise ValueError("NO_CHANGE exige sua publicação oficial original.")
    publication = snapshot if state in {"PUBLISHED", "NO_CHANGE"} else None
    event_time, timing = _timing(attempt, publication, start=start, reconstructed=reconstructed)
    reason_codes = sorted(
        {
            _identifier(issue["code"])
            for issue in attempt.get("issues", [])
            if isinstance(issue, dict) and "code" in issue and issue.get("severity") == "ERROR"
        }
    )
    if start:
        reason_codes = []
    if state in {"BLOCKED", "TECHNICAL_FAILURE"} and not reason_codes:
        reason_codes = [state]
    outcome = _facet(
        _custom_url("VarejoOutcomeRunFacet"),
        state=state,
        jobMode=job_mode,
        newPublication=state == "PUBLISHED",
        publicationId=_identifier(publication["publication_id"]) if publication else None,
        acceptedBatches=[_identifier(value) for value in publication["accepted_batches"]]
        if publication
        else [],
        reasonCodes=reason_codes,
    )
    facets = {"varejo_outcome": outcome, "varejo_timing": timing}
    if state in {"BLOCKED", "TECHNICAL_FAILURE"}:
        facets["errorMessage"] = _facet(
            f"{UPSTREAM}/facets/ErrorMessageRunFacet.json#/$defs/ErrorMessageRunFacet",
            message="; ".join(reason_codes),
            programmingLanguage="Python",
        )
    outputs = []
    if publication and state == "PUBLISHED":
        for name, reference in publication["tables"].items():
            dataset_name = (
                f"bronze/{canonical_run_id(str(publication['run_id']))}"
                if name == "bronze"
                else name
            )
            dataset = _dataset(dataset_name, reference["version"], name)
            dataset["facets"]["varejo_provenance"] = _facet(
                _custom_url("VarejoProvenanceDatasetFacet"),
                publicationId=_identifier(publication["publication_id"]),
                accepted=True,
            )
            outputs.append(dataset)
    inputs = _inputs(publication)
    # NO_CHANGE consumes the official versions; it did not write these datasets again.
    if state == "NO_CHANGE" and publication:
        inputs.extend(
            _dataset(name, reference["version"], name)
            for name, reference in publication["tables"].items()
            if name != "bronze"
        )
    event = {
        "eventType": "START" if start else TERMINAL_TYPES[state],
        "eventTime": event_time,
        "run": {"runId": canonical_run_id(str(attempt["run_id"])), "facets": facets},
        "job": {"namespace": JOB_NAMESPACE, "name": f"retail.{job_mode}"},
        "inputs": sorted(inputs, key=lambda item: (item["namespace"], item["name"])),
        "outputs": sorted(outputs, key=lambda item: (item["namespace"], item["name"])),
        "producer": PRODUCER,
        "schemaURL": EVENT_SCHEMA_URL,
    }
    validate_event(event)
    return event


def _persist(root: Path, event: Mapping[str, Any]) -> Path:
    # Lazy import keeps schema/serialization tests usable without Spark or Linux fcntl.
    from retail_pipeline.publication import atomic_json

    validate_event(event)
    kind = "start" if event["eventType"] == "START" else "terminal"
    path = root / "lineage" / "events" / event["run"]["runId"] / f"{kind}.json"
    if path.exists():
        existing = _load(path)
        validate_event(existing)
        if (
            existing["run"]["runId"] != event["run"]["runId"]
            or existing["eventType"] != event["eventType"]
            or existing["job"] != event["job"]
            or existing.get("inputs", []) != event.get("inputs", [])
            or existing.get("outputs", []) != event.get("outputs", [])
            or {
                key: value
                for key, value in existing["run"].get("facets", {}).items()
                if key != "varejo_timing"
            }
            != {
                key: value
                for key, value in event["run"].get("facets", {}).items()
                if key != "varejo_timing"
            }
        ):
            raise ValueError("Evento imutável existente diverge da identidade/estado reconstruído.")
        return path
    atomic_json(path, event)
    return path


def emit_start(root: Path, attempt: Mapping[str, Any], *, job_mode: str | None = None) -> Path:
    """Called under the writer lock after persisting attempt.json."""
    record = dict(attempt)
    if job_mode is not None:
        record["job_mode"] = job_mode
    return _persist(root, build_event(record, start=True))


def emit_terminal(
    root: Path,
    attempt: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None = None,
    job_mode: str | None = None,
) -> Path:
    """Called best-effort under the writer lock after saving the terminal attempt."""
    record = dict(attempt)
    if job_mode is not None:
        record["job_mode"] = job_mode
    return _persist(root, build_event(record, snapshot=snapshot))


def _committed_publications(
    root: Path, attempts: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    pointer = root / "publication.json"
    if not pointer.exists():
        return {}
    current = _load(pointer)
    committed = {str(current["publication_id"]): current}
    legacy_ancestor = "previous_publication_id" not in current
    parent = current.get("previous_publication_id")
    while parent is not None:
        if parent in committed:
            raise ValueError("Ciclo na cadeia de publicações.")
        path = root / "publications" / f"{_identifier(parent)}.json"
        previous = _load(path)
        if previous.get("publication_id") != parent:
            raise ValueError("Identidade divergente na cadeia de publicações.")
        committed[str(parent)] = previous
        legacy_ancestor |= "previous_publication_id" not in previous
        parent = previous.get("previous_publication_id")
    # Legacy snapshots lack ancestry. A saved PUBLISHED attempt can prove a past commit;
    # a manifest alone cannot: publish writes its immutable audit before the pointer.
    if legacy_ancestor:
        for attempt in attempts.values():
            publication_id = attempt.get("publication_id")
            if attempt.get("state") != "PUBLISHED" or not publication_id:
                continue
            path = root / "publications" / f"{_identifier(publication_id)}.json"
            if path.exists():
                publication = _load(path)
                if (
                    publication.get("run_id") == attempt.get("run_id")
                    and publication.get("publication_id") == publication_id
                ):
                    committed[str(publication_id)] = publication
    return committed


def _export_locked(root: Path) -> dict[str, Any]:
    attempts: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "runs").glob("*/attempt.json")):
        attempt = _load(path)
        if "run_id" not in attempt:
            raise ValueError("Tentativa sem run_id.")
        attempts[str(attempt["run_id"])] = attempt
    committed = _committed_publications(root, attempts)
    for committed_snapshot in committed.values():
        run_id = str(committed_snapshot["run_id"])
        attempts.setdefault(run_id, {"run_id": run_id, "state": "PUBLISHED", "issues": []})
    published_by_run = {str(item["run_id"]): item for item in committed.values()}
    paths: list[str] = []
    errors: list[dict[str, str]] = []
    reconstructed_runs = 0
    for run_id, saved_attempt in sorted(attempts.items()):
        attempt = dict(saved_attempt)
        publication = published_by_run.get(run_id)
        if publication is not None:
            attempt.update(state="PUBLISHED", publication_id=publication["publication_id"])
        elif attempt.get("state") == "NO_CHANGE":
            publication = committed.get(str(attempt.get("publication_id")))
            if publication is None:
                attempt.update(
                    state="TECHNICAL_FAILURE",
                    issues=[{"code": "PUBLICATION_UNAVAILABLE", "severity": "ERROR"}],
                )
        elif attempt.get("state") in {"RUNNING", "PUBLISHED"}:
            # Lock ownership proves no pipeline writer is still running in this volume.
            attempt.update(
                state="TECHNICAL_FAILURE",
                issues=[{"code": "INTERRUPTED_ATTEMPT", "severity": "ERROR"}],
            )
        if attempt.get("state") not in TERMINAL_TYPES:
            errors.append({"run_id": canonical_run_id(run_id), "code": "UNKNOWN_STATE"})
            continue
        try:
            paths.append(str(_persist(root, build_event(attempt, start=True, reconstructed=True))))
            paths.append(
                str(_persist(root, build_event(attempt, snapshot=publication, reconstructed=True)))
            )
            reconstructed_runs += 1
        except Exception as error:
            # Report codes only: raw exception strings can include private filesystem paths.
            errors.append({"run_id": canonical_run_id(run_id), "code": type(error).__name__})
    return {
        "contract_version": 1,
        "runs": reconstructed_runs,
        "events": len(paths),
        "paths": paths,
        "errors": errors,
        "schema_url": EVENT_SCHEMA_URL,
    }


def export_lineage(root: Path) -> dict[str, Any]:
    """Reconcile/export only while holding the same nonblocking lock as the writer."""
    from retail_pipeline.publication import writer_lock

    with writer_lock(root):
        return _export_locked(root)

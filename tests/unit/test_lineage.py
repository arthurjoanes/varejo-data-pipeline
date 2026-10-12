"""OpenLineage contract/recovery tests do not require Spark or Linux fcntl."""

import copy
import hashlib
import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest
from jsonschema import ValidationError

from retail_pipeline import lineage

RUN = "12345678123446789234123456781234"
NEXT_RUN = "22345678123446789234123456781234"
START = "2026-10-12T09:00:00+00:00"
END = "2026-10-12T09:05:00+00:00"
HASH = "a" * 64


def attempt(state="PUBLISHED", **values):
    return {
        "run_id": RUN,
        "state": state,
        "started_at": START,
        "finished_at": END,
        "job_mode": "validate" if state == "VALIDATED" else "publish",
        "publication_id": "publication-1" if state in {"PUBLISHED", "NO_CHANGE"} else None,
        "issues": [],
        **values,
    }


def publication(**values):
    return {
        "publication_id": "publication-1",
        "previous_publication_id": None,
        "run_id": RUN,
        "published_at": END,
        "accepted_batches": ["batch-1"],
        "tables": {
            "silver": {"path": "/data/tables/silver", "version": 2},
            "gold_store_day": {"path": "/data/tables/gold_store_day", "version": 3},
            "gold_product_day": {"path": "/data/tables/gold_product_day", "version": 4},
        },
        "sources": [
            {
                "batch_id": "batch-1",
                "run_id": RUN,
                "bronze_path": "/data/runs/private/bronze",
                "bronze_version": 0,
                "manifest_hash": "b" * 64,
                "reference_hashes": {"catalog": HASH, "schedule": HASH},
                "operator_reference_hash": HASH,
            }
        ],
        **values,
    }


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")


@pytest.fixture
def io_adapter(monkeypatch):
    module = ModuleType("retail_pipeline.publication")
    writes = []
    locks = []

    def atomic_json(path, value):
        writes.append(path)
        write(path, value)

    @contextmanager
    def writer_lock(root):
        locks.append(root)
        yield

    module.atomic_json = atomic_json
    module.writer_lock = writer_lock
    monkeypatch.setitem(sys.modules, "retail_pipeline.publication", module)
    return module, writes, locks


def events(root):
    return [json.loads(path.read_text()) for path in sorted(root.glob("lineage/events/*/*.json"))]


def test_uuid_hex_preserves_identity_and_legacy_mapping_is_stable():
    assert lineage.canonical_run_id(RUN) == str(uuid.UUID(RUN))
    assert lineage.canonical_run_id(str(uuid.UUID(RUN))) == str(uuid.UUID(RUN))
    assert lineage.canonical_run_id("legacy-run") == str(
        uuid.uuid5(lineage.LEGACY_UUID_NAMESPACE, "legacy-run")
    )
    assert lineage.canonical_run_id("legacy-run") != lineage.canonical_run_id("other-run")
    with pytest.raises(ValueError, match="vazio"):
        lineage.canonical_run_id("")


@pytest.mark.parametrize(
    ("state", "event_type", "new_publication"),
    [
        ("PUBLISHED", "COMPLETE", True),
        ("NO_CHANGE", "COMPLETE", False),
        ("VALIDATED", "COMPLETE", False),
        ("BLOCKED", "FAIL", False),
        ("TECHNICAL_FAILURE", "FAIL", False),
    ],
)
def test_state_mapping(state, event_type, new_publication):
    event = lineage.build_event(attempt(state), snapshot=publication())
    assert event["eventType"] == event_type
    assert event["run"]["facets"]["varejo_outcome"]["newPublication"] is new_publication
    assert bool(event["outputs"]) is new_publication
    if event_type == "FAIL":
        assert event["run"]["facets"]["errorMessage"]["message"] == state
    lineage.validate_event(event)


def test_start_and_validation_do_not_advertise_new_gold():
    start = lineage.build_event(attempt(), snapshot=publication(), start=True)
    validated = lineage.build_event(attempt("VALIDATED"), snapshot=publication())
    assert start["eventType"] == "START"
    assert start["eventTime"] == START
    assert start["outputs"] == []
    assert validated["job"]["name"] == "retail.validate"
    assert validated["outputs"] == []
    assert validated["run"]["facets"]["varejo_outcome"]["publicationId"] is None


def test_legacy_validated_attempt_keeps_the_same_job_for_start_and_terminal():
    record = attempt("VALIDATED")
    del record["job_mode"]
    start = lineage.build_event(record, start=True, reconstructed=True)
    terminal = lineage.build_event(record, reconstructed=True)
    assert (
        start["job"]
        == terminal["job"]
        == {
            "namespace": lineage.JOB_NAMESPACE,
            "name": "retail.validate",
        }
    )
    assert start["run"]["runId"] == terminal["run"]["runId"]


def test_outputs_have_exact_versions_standard_schemas_and_sanitized_provenance():
    event = lineage.build_event(attempt(), snapshot=publication())
    output_versions = {
        item["name"]: item["facets"]["version"]["datasetVersion"] for item in event["outputs"]
    }
    assert output_versions == {"silver": "2", "gold_store_day": "3", "gold_product_day": "4"}
    silver = next(item for item in event["outputs"] if item["name"] == "silver")
    fields = {field["name"]: field["type"] for field in silver["facets"]["schema"]["fields"]}
    assert fields["unit_price_brl"] == "decimal(18,2)"
    assert fields["line_net_brl"] == "decimal(24,2)"
    bronze = next(item for item in event["inputs"] if item["name"].startswith("bronze/"))
    assert bronze["facets"]["varejo_provenance"]["manifestHash"] == "b" * 64
    assert bronze["facets"]["varejo_provenance"]["operatorReferenceHash"] == HASH
    serialized = json.dumps(event)
    assert "/data" not in serialized
    assert "private" not in serialized


@pytest.mark.parametrize(
    "path,value",
    [
        (("run", "runId"), RUN),
        (("eventTime",), "2026-02-31T00:00:00Z"),
        (("eventTime",), "2026-10-12"),
        (("producer",), "relative/path"),
        (("schemaURL",), "bad uri"),
        (("run", "facets", "varejo_timing", "reconstructedAt"), "not-a-date"),
        (("run", "facets", "varejo_outcome", "_producer"), "no uri"),
    ],
)
def test_formats_are_checked_as_well_as_structure(path, value):
    event = lineage.build_event(attempt(), snapshot=publication())
    target = event
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises((ValidationError, ValueError)):
        lineage.validate_event(event)


def test_format_dependencies_cannot_silently_disable_checks(monkeypatch):
    monkeypatch.delitem(lineage.FormatChecker.checkers, "uri")
    with pytest.raises(RuntimeError, match="ausentes"):
        lineage.build_event(attempt("VALIDATED"))


def test_fail_reason_does_not_export_private_message_or_raw_payload():
    event = lineage.build_event(
        attempt(
            "BLOCKED",
            issues=[
                {
                    "code": "BAD_CONTRACT",
                    "severity": "ERROR",
                    "message": "C:/Users/Private/token=secret",
                }
            ],
        )
    )
    assert event["run"]["facets"]["errorMessage"]["message"] == "BAD_CONTRACT"
    assert "secret" not in json.dumps(event)


def test_no_change_references_original_official_versions_without_outputs():
    event = lineage.build_event(attempt("NO_CHANGE", run_id=NEXT_RUN), snapshot=publication())
    versions = {
        item["name"]: item["facets"]["version"]["datasetVersion"]
        for item in event["inputs"]
        if item["name"].startswith("gold_")
    }
    assert versions == {"gold_store_day": "3", "gold_product_day": "4"}
    assert event["outputs"] == []
    with pytest.raises(ValueError, match="original"):
        lineage.build_event(attempt("NO_CHANGE"), snapshot=publication(publication_id="other"))


def test_export_after_commit_recovers_complete_and_preserves_evidence(tmp_path, io_adapter):
    write(tmp_path / "publication.json", publication())
    write(tmp_path / "publications/publication-1.json", publication())
    write(tmp_path / f"runs/{RUN}/attempt.json", attempt("RUNNING", finished_at=None))
    write(tmp_path / f"runs/{RUN}/candidate.json", publication())
    evidence = tmp_path / f"runs/{RUN}/evidence/raw.csv"
    evidence.parent.mkdir()
    evidence.write_bytes(b"opaque\x00bytes\r\n")
    originals = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    first = lineage.export_lineage(tmp_path)
    assert first["events"] == 2 and first["errors"] == []
    terminal = next(event for event in events(tmp_path) if event["eventType"] == "COMPLETE")
    assert terminal["eventTime"] == END
    timing = terminal["run"]["facets"]["varejo_timing"]
    assert timing["originalTimeAvailable"] is True
    assert timing["eventTimeSource"] == "publication.published_at"
    assert "reconstructedAt" in timing
    assert terminal["outputs"]
    assert all(path.read_bytes() == content for path, content in originals.items())
    exported = {Path(path): Path(path).read_bytes() for path in first["paths"]}
    second = lineage.export_lineage(tmp_path)
    assert second == first
    assert all(path.read_bytes() == content for path, content in exported.items())
    assert len(io_adapter[1]) == 2
    assert io_adapter[2] == [tmp_path, tmp_path]


def test_orphan_manifest_and_candidate_never_become_published(tmp_path, io_adapter):
    write(tmp_path / "publication.json", publication())
    write(tmp_path / "publications/publication-1.json", publication())
    orphan = publication(
        publication_id="orphan", run_id=NEXT_RUN, previous_publication_id="publication-1"
    )
    write(tmp_path / "publications/orphan.json", orphan)
    write(tmp_path / f"runs/{NEXT_RUN}/candidate.json", orphan)
    write(
        tmp_path / f"runs/{NEXT_RUN}/attempt.json",
        attempt("RUNNING", run_id=NEXT_RUN, finished_at=None),
    )
    lineage.export_lineage(tmp_path)
    terminal = next(
        event
        for event in events(tmp_path)
        if event["run"]["runId"] == str(uuid.UUID(NEXT_RUN)) and event["eventType"] != "START"
    )
    assert terminal["eventType"] == "FAIL"
    assert terminal["outputs"] == []
    assert terminal["run"]["facets"]["varejo_outcome"]["publicationId"] is None
    assert terminal["run"]["facets"]["errorMessage"]["message"] == "INTERRUPTED_ATTEMPT"
    assert terminal["run"]["facets"]["varejo_timing"]["originalTimeAvailable"] is False


def test_reconcile_no_change_uses_publication_ancestry(tmp_path, io_adapter):
    unchanged_run = "32345678123446789234123456781234"
    first = publication()
    second = publication(
        publication_id="publication-2",
        previous_publication_id="publication-1",
        run_id=NEXT_RUN,
        tables={"gold_store_day": {"path": "/data/tables/gold", "version": 99}},
    )
    write(tmp_path / "publication.json", second)
    write(tmp_path / "publications/publication-1.json", first)
    write(tmp_path / "publications/publication-2.json", second)
    write(
        tmp_path / f"runs/{unchanged_run}/attempt.json", attempt("NO_CHANGE", run_id=unchanged_run)
    )
    result = lineage.export_lineage(tmp_path)
    assert result["errors"] == []
    terminal = next(
        event
        for event in events(tmp_path)
        if event["run"]["runId"] == str(uuid.UUID(unchanged_run))
        and event["eventType"] == "COMPLETE"
    )
    gold = next(item for item in terminal["inputs"] if item["name"] == "gold_store_day")
    assert gold["facets"]["version"]["datasetVersion"] == "3"


def test_active_writer_lock_prevents_reconcile_from_marking_failure(tmp_path, io_adapter):
    @contextmanager
    def busy_lock(root):
        raise RuntimeError("busy writer")
        yield

    io_adapter[0].writer_lock = busy_lock
    write(tmp_path / f"runs/{RUN}/attempt.json", attempt("RUNNING"))
    with pytest.raises(RuntimeError, match="busy"):
        lineage.export_lineage(tmp_path)
    assert events(tmp_path) == []


def test_existing_terminal_rejects_changed_outputs_and_preserves_bytes(tmp_path, io_adapter):
    path = lineage.emit_terminal(tmp_path, attempt(), snapshot=publication())
    before = path.read_bytes()
    modified = publication()
    modified["tables"]["silver"]["version"] = 90
    with pytest.raises(ValueError, match="diverge"):
        lineage.emit_terminal(tmp_path, attempt(), snapshot=modified)
    assert path.read_bytes() == before


def test_missing_old_timestamps_explicitly_use_reconstruction(tmp_path, io_adapter):
    snapshot = publication(published_at=None)
    write(tmp_path / "publication.json", snapshot)
    lineage.export_lineage(tmp_path)
    for event in events(tmp_path):
        timing = event["run"]["facets"]["varejo_timing"]
        assert timing["originalTimeAvailable"] is False
        assert timing["eventTimeSource"] == "reconstruction"
        assert "originalEventTime" not in timing
        assert timing["reconstructedAt"] == event["eventTime"]


def test_legacy_proof_fallback_reached_from_new_ancestry(tmp_path, io_adapter):
    legacy = publication(publication_id="legacy-current")
    legacy.pop("previous_publication_id")
    historical = publication(publication_id="historical")
    historical.pop("previous_publication_id")
    newer = publication(
        publication_id="new", run_id=NEXT_RUN, previous_publication_id="legacy-current"
    )
    write(tmp_path / "publication.json", newer)
    write(tmp_path / "publications/legacy-current.json", legacy)
    write(tmp_path / "publications/historical.json", historical)
    write(tmp_path / f"runs/{RUN}/attempt.json", attempt(publication_id="historical"))
    result = lineage.export_lineage(tmp_path)
    assert result["errors"] == []
    assert len([event for event in events(tmp_path) if event["eventType"] == "COMPLETE"]) == 2


def test_official_schema_bytes_and_custom_urls_are_pinned():
    expected = {
        "OpenLineage.json": "69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2",
        "SchemaDatasetFacet.json": "b1ed03c11391ebb89ffc5212f303702a46cc0f528dbf1ddeb591616288c8c10f",
        "DatasetVersionDatasetFacet.json": "91f57b67bc6d639bb6d600e26b827dac551e3520a233d1785d65870da263dc34",
        "ErrorMessageRunFacet.json": "b11b4ee8b0f99f6846264f87cad48390255c7ef142ce623216660c7097be0ea6",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((lineage.SCHEMA_DIR / name).read_bytes()).hexdigest() == digest
    event = lineage.build_event(attempt("VALIDATED"))
    custom_digest = hashlib.sha256(
        (lineage.SCHEMA_DIR / "VarejoFacets.json").read_bytes()
    ).hexdigest()
    assert (
        event["run"]["facets"]["varejo_outcome"]["_schemaURL"]
        == f"urn:sha256:{custom_digest}#/$defs/VarejoOutcomeRunFacet"
    )
    modified = copy.deepcopy(event)
    modified["run"]["facets"]["varejo_outcome"]["_schemaURL"] = (
        "https://example.org/main/schema.json"
    )
    with pytest.raises(ValueError, match="schemaURL"):
        lineage.validate_event(modified)

"""Contrato do perfil sem iniciar Spark, Docker ou JVM."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from retail_pipeline.profiling import (
    CALCULATION_VERSION,
    MAX_PROFILE_BYTES,
    ProfileParameters,
    _catalog_context,
    compare_metrics,
    load_profile,
    persist_profile,
    validate_profile,
)


def empty_totals() -> dict[str, Any]:
    return {
        "active_lines": 0,
        "sales": 0,
        "units": 0,
        "net_revenue_brl": "0.00",
        "gross_revenue_brl": "0.00",
        "discount_brl": "0.00",
    }


def empty_profile(tmp_path: Path) -> dict[str, Any]:
    coverage = {"expected": ["S01"], "received": ["S01"], "missing": [], "zero_movement": ["S01"]}
    return {
        "contract_version": 1,
        "calculation_version": CALCULATION_VERSION,
        "publication_id": "pub-first",
        "run_id": "run-first",
        "delta_versions": {"silver": {"path": str(tmp_path / "silver"), "version": 0}},
        "parameters": ProfileParameters().document(),
        "reference_hashes": {"catalog.json": "a" * 64, "schedule.json": "b" * 64},
        "coverage": {
            **coverage,
            "scope_complete": True,
            "origin": "cumulative_confirmed_stores_with_latest_batch_zero_movement",
        },
        "date_range": {
            "start": None,
            "end": None,
            "date_count": 0,
            "dates": [],
            "dates_truncated": False,
        },
        "batch": {
            "stats": {"received": 0, "valid": 0, "rejected": 0},
            "coverage": coverage,
            "received_operations": {"valid_cancel_events": 0, "valid_revision_gt1_events": 0},
            "received_operations_include_duplicates_and_stale": True,
        },
        "active_state": {
            "totals": empty_totals(),
            "cancelled_keys": 0,
            "distributions": {
                name: {"min": None, "max": None, "mean": None, "quantiles": []}
                for name in ("quantity", "unit_price_brl", "line_discount_brl")
            },
            "groups": {
                name: {"values": [], "group_count": 0, "truncated": False}
                for name in ("stores", "products")
            },
        },
        "state_changes": {
            "origin": "initial_silver_state",
            "new_keys": 0,
            "revised_keys": 0,
            "cancelled_keys": 0,
            "reactivated_keys": 0,
            "effective_changes": 0,
        },
        "comparison": {
            "status": "NO_BASELINE",
            "baseline_publication_id": None,
            "baseline_delta_versions": None,
            "reason": "Primeira publicação.",
            "context": {
                "current_date_range": {
                    "start": None,
                    "end": None,
                    "date_count": 0,
                    "dates": [],
                    "dates_truncated": False,
                },
            },
            "scope": None,
            "original_totals": {"previous": None, "current": empty_totals()},
            "equivalent_totals": None,
            "rules": [],
            "warnings": 0,
        },
    }


def snapshot_for(profile: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "publication_id": profile["publication_id"],
        "run_id": profile["run_id"],
        "tables": profile["delta_versions"],
        "profile": reference,
    }


def test_immutable_profile_roundtrip_and_explicit_absence_states(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    reference = persist_profile(tmp_path, profile)
    snapshot = snapshot_for(profile, reference)
    payload = Path(reference["path"]).read_bytes()
    assert reference["contract_version"] == 1
    assert reference["sha256"] == hashlib.sha256(payload).hexdigest()
    assert load_profile(snapshot) == {"status": "AVAILABLE", "profile": profile, "reason": None}
    assert persist_profile(tmp_path, profile) == reference
    assert load_profile(None)["status"] == "NO_PUBLICATION"
    assert load_profile({"publication_id": "legacy"})["status"] == "LEGACY"
    modified = copy.deepcopy(profile)
    modified["batch"]["stats"]["received"] = 1
    with pytest.raises(ValueError, match="não pode ser substituído"):
        persist_profile(tmp_path, modified)
    assert Path(reference["path"]).read_bytes() == payload
    Path(reference["path"]).unlink()
    assert load_profile(snapshot)["status"] == "MISSING"


@pytest.mark.parametrize("mutation", ["bytes", "run", "publication", "version", "hash", "contract"])
def test_reader_rejects_tampering_and_snapshot_mismatch(tmp_path: Path, mutation: str) -> None:
    profile = empty_profile(tmp_path)
    snapshot = snapshot_for(profile, persist_profile(tmp_path, profile))
    if mutation == "bytes":
        Path(snapshot["profile"]["path"]).write_text("{}", encoding="utf-8")
    elif mutation == "run":
        snapshot["run_id"] = "another-run"
    elif mutation == "publication":
        snapshot["publication_id"] = "another-publication"
    elif mutation == "version":
        snapshot["tables"] = {"silver": {"path": "/data/tables/silver", "version": 99}}
    elif mutation == "hash":
        snapshot["profile"]["sha256"] = "invalid"
    else:
        snapshot["profile"]["contract_version"] = 2
    result = load_profile(snapshot)
    assert result["status"] == "INVALID"
    assert result["profile"] is None


def test_reader_rejects_duplicate_keys_even_with_matching_hash(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    snapshot = snapshot_for(profile, persist_profile(tmp_path, profile))
    path = Path(snapshot["profile"]["path"])
    payload = path.read_bytes().replace(
        b'"contract_version": 1,', b'"contract_version": 1, "contract_version": 1,'
    )
    path.write_bytes(payload)
    snapshot["profile"]["sha256"] = hashlib.sha256(payload).hexdigest()
    assert load_profile(snapshot)["status"] == "INVALID"


def test_reader_rejects_nonfinite_json_constant_even_with_matching_hash(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    snapshot = snapshot_for(profile, persist_profile(tmp_path, profile))
    path = Path(snapshot["profile"]["path"])
    payload = path.read_bytes().replace(b'"warnings": 0', b'"warnings": NaN')
    path.write_bytes(payload)
    snapshot["profile"]["sha256"] = hashlib.sha256(payload).hexdigest()
    assert load_profile(snapshot)["status"] == "INVALID"


def test_failure_before_profile_replace_preserves_previous_bytes(
    tmp_path: Path, monkeypatch: Any
) -> None:
    profile = empty_profile(tmp_path)
    reference = persist_profile(tmp_path, profile)
    payload = Path(reference["path"]).read_bytes()
    candidate = copy.deepcopy(profile)
    candidate["publication_id"] = "pub-second"

    def fail_replace(*args: object) -> None:
        raise OSError("volume indisponível")

    monkeypatch.setattr("retail_pipeline.profiling.os.replace", fail_replace)
    with pytest.raises(OSError, match="volume indisponível"):
        persist_profile(tmp_path, candidate)
    assert Path(reference["path"]).read_bytes() == payload
    assert not (tmp_path / "profiles/pub-second.json").exists()
    assert list((tmp_path / "profiles").glob(".pending-*")) == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"group_limit": 101},
        {"date_display_limit": 367},
        {"scope_limit": 1001},
        {"max_json_bytes": MAX_PROFILE_BYTES + 1},
        {"quantile_accuracy": 0},
        {"quantile_probabilities": tuple(index / 10 for index in range(10))},
        {"quantile_probabilities": (0.5, 0.25)},
        {"quantile_probabilities": (float("nan"),)},
        {"min_active_lines": 0},
        {"quantity_mean_relative_threshold": "NaN"},
        {"unit_price_mean_relative_threshold": "-0.25"},
        {"group_limit": True},
    ],
)
def test_profile_parameters_bound_driver_output(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ProfileParameters(**arguments)


@pytest.mark.parametrize(
    "field,value", [("net_revenue_brl", 0.0), ("gross_revenue_brl", "1e0"), ("discount_brl", "0")]
)
def test_totals_require_exact_decimal_text(tmp_path: Path, field: str, value: object) -> None:
    profile = empty_profile(tmp_path)
    profile["active_state"]["totals"][field] = value
    with pytest.raises(ValueError, match="Decimal exato"):
        validate_profile(profile)


def test_json_budget_applies_before_creating_official_profile(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    profile["parameters"] = ProfileParameters(max_json_bytes=1024).document()
    with pytest.raises(ValueError, match="limite configurado"):
        persist_profile(tmp_path, profile)
    assert not (tmp_path / "profiles").exists()


def metrics(lines: int, units: int, gross: str) -> dict[str, Any]:
    return {**empty_totals(), "active_lines": lines, "units": units, "gross_revenue_brl": gross}


def test_comparison_uses_normalized_means_and_warning_only() -> None:
    previous = metrics(4, 8, "80.00")
    current = metrics(4, 16, "240.00")
    comparison = compare_metrics(previous, current)
    assert comparison["status"] == "COMPARABLE"
    assert comparison["warnings"] == 2
    assert comparison["rules"][0]["previous"] == "2.000000"
    assert comparison["rules"][0]["current"] == "4.000000"
    assert comparison["rules"][1]["previous"] == "10.000000"
    assert comparison["rules"][1]["current"] == "15.000000"
    assert comparison["rules"][1]["relative_change"] == "0.500000"
    assert {rule["severity"] for rule in comparison["rules"]} == {"WARNING"}
    # Dobrar o volume com o mesmo valor por linha/unidade não produz alerta.
    repeated = compare_metrics(previous, metrics(8, 16, "160.00"))
    assert repeated["warnings"] == 0


def test_comparison_keeps_significance_beyond_default_decimal_context() -> None:
    previous = metrics(4, 4, "40000000000000000000000000000.00")
    current = metrics(4, 4, "40000000000000000000000000001.00")
    comparison = compare_metrics(
        previous, current, ProfileParameters(unit_price_mean_relative_threshold="0")
    )
    rule = comparison["rules"][1]
    assert rule["difference"] == "0.250000"
    assert rule["severity"] == "WARNING"
    assert rule["previous_numerator"] == previous["gross_revenue_brl"]


@pytest.mark.parametrize(
    "previous,current,status",
    [
        (metrics(0, 0, "0.00"), metrics(0, 0, "0.00"), "EMPTY"),
        (metrics(0, 0, "0.00"), metrics(4, 4, "10.00"), "NOT_COMPARABLE"),
        (metrics(2, 2, "10.00"), metrics(4, 4, "10.00"), "INSUFFICIENT_SAMPLE"),
    ],
)
def test_empty_or_small_comparison_has_own_state(
    previous: dict[str, Any], current: dict[str, Any], status: str
) -> None:
    result = compare_metrics(previous, current)
    assert result["status"] == status
    assert result["warnings"] == 0
    assert all(rule["status"] == status for rule in result["rules"])


def test_zero_price_baseline_has_no_relative_variation() -> None:
    result = compare_metrics(metrics(4, 4, "0.00"), metrics(4, 4, "10.00"))
    rule = result["rules"][1]
    assert rule["status"] == "ZERO_BASELINE"
    assert rule["relative_change"] is None
    assert rule["difference"] == "2.500000"


def test_group_cardinality_and_algorithm_are_validated(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    profile["parameters"]["quantile_algorithm"] = "exact_financial_quantiles"
    with pytest.raises(ValueError, match="algoritmo"):
        validate_profile(profile)
    profile = empty_profile(tmp_path)
    profile["active_state"]["groups"]["stores"]["values"] = [{"store_id": "S01"}] * 21
    with pytest.raises(ValueError, match="grupos fora"):
        validate_profile(profile)


def test_invalid_comparison_cannot_claim_warning_without_equivalent_totals(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    profile["comparison"]["status"] = "COMPARABLE"
    with pytest.raises(ValueError, match="totais equivalentes"):
        validate_profile(profile)


def test_excessive_file_is_rejected_before_json_decode(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    snapshot = snapshot_for(profile, persist_profile(tmp_path, profile))
    path = Path(snapshot["profile"]["path"])
    path.write_bytes(b"x" * (MAX_PROFILE_BYTES + 1))
    assert load_profile(snapshot)["status"] == "INVALID"


def test_serialization_preserves_large_financial_totals(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    profile["active_state"]["totals"] = {
        "active_lines": 4,
        "sales": 4,
        "units": 4,
        "gross_revenue_brl": "40000000000000000000000000000.01",
        "discount_brl": "0.01",
        "net_revenue_brl": "40000000000000000000000000000.00",
    }
    profile["comparison"]["original_totals"]["current"] = profile["active_state"]["totals"]
    reference = persist_profile(tmp_path, profile)
    decoded = json.loads(Path(reference["path"]).read_bytes())
    assert decoded["active_state"]["totals"] == profile["active_state"]["totals"]


def test_catalog_context_uses_approved_identity_and_explicit_legacy_origin() -> None:
    before = {"reference_hashes": {"catalog.json": "a" * 64, "operator_catalog_hash": "c" * 64}}
    after = {"reference_hashes": {"catalog.json": "b" * 64, "operator_catalog_hash": "c" * 64}}
    context = _catalog_context(before, after)
    assert context["catalog_changed"] is False
    assert context["catalog_reference_origin"] == "approved_operator_catalog"
    del before["reference_hashes"]["operator_catalog_hash"]
    context = _catalog_context(before, after)
    assert context["catalog_changed"] is True
    assert context["catalog_reference_origin"] == "received_catalog_bytes"


@pytest.mark.parametrize("field", ["previous_date_range", "baseline_delta_versions"])
def test_comparison_renderer_metadata_is_validated(tmp_path: Path, field: str) -> None:
    profile = empty_profile(tmp_path)
    if field == "previous_date_range":
        profile["comparison"]["context"][field] = {
            "start": None,
            "end": None,
            "date_count": "not-an-int",
            "dates": [],
            "dates_truncated": False,
        }
    else:
        profile["comparison"][field] = {"silver": {"path": "/data/silver", "version": "not-an-int"}}
    with pytest.raises(ValueError, match="inteiro"):
        validate_profile(profile)


def test_reader_rejects_deep_json_without_aborting_report(tmp_path: Path) -> None:
    profile = empty_profile(tmp_path)
    snapshot = snapshot_for(profile, persist_profile(tmp_path, profile))
    path = Path(snapshot["profile"]["path"])
    payload = b"[" * 2000 + b"0" + b"]" * 2000
    path.write_bytes(payload)
    snapshot["profile"]["sha256"] = hashlib.sha256(payload).hexdigest()
    assert load_profile(snapshot)["status"] == "INVALID"

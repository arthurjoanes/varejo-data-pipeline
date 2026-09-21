from datetime import datetime
from pathlib import PurePosixPath

from retail_pipeline.contracts import HASH, TIMESTAMP, logical_hash, stable_json, valid_identifier


def add_issue(issues: list[dict[str, object]], code: str, **context: object) -> None:
    issues.append({"code": code, "severity": "ERROR", **context})


def validate_references(
    catalog: dict[str, object],
    schedule: dict[str, object],
    manifest: dict[str, object],
    issues: list[dict[str, object]],
) -> tuple[set[str], set[str], set[str]]:
    stores: set[str] = set()
    products: set[str] = set()
    if catalog.get("schema_version") != 1 or type(catalog.get("schema_version")) is not int:
        add_issue(issues, "CATALOG_SCHEMA_VERSION")
    for collection, identifier, result in (
        ("stores", "store_id", stores),
        ("products", "product_id", products),
    ):
        records = catalog.get(collection, [])
        if not isinstance(records, list) or not records:
            add_issue(issues, "INVALID_CATALOG", field=collection)
            continue
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or not valid_identifier(record.get(identifier)):
                add_issue(issues, "INVALID_CATALOG", field=collection)
                continue
            key = record[identifier]
            if key in seen:
                add_issue(issues, "DUPLICATE_REFERENCE", field=identifier, value=key)
            seen.add(key)
            if not isinstance(record.get("name"), str) or not record["name"]:
                add_issue(issues, "INVALID_CATALOG", field="name", value=key)
            if collection == "stores":
                if (
                    type(record.get("active")) is not bool
                    or record.get("timezone") != "America/Sao_Paulo"
                    or not isinstance(record.get("state"), str)
                ):
                    add_issue(issues, "INVALID_CATALOG", field="store_metadata", value=key)
                if record.get("active") is True:
                    result.add(key)
            else:
                if not isinstance(record.get("category"), str) or not record["category"]:
                    add_issue(issues, "INVALID_CATALOG", field="category", value=key)
                result.add(key)
    expected: set[str] = set()
    if schedule.get("schema_version") != 1 or type(schedule.get("schema_version")) is not int:
        add_issue(issues, "SCHEDULE_SCHEMA_VERSION")
    windows = schedule.get("windows", [])
    if not isinstance(windows, list):
        add_issue(issues, "INVALID_SCHEDULE")
        windows = []
    window_keys: set[tuple[str, str]] = set()
    for window in windows:
        if not isinstance(window, dict):
            add_issue(issues, "INVALID_SCHEDULE_WINDOW")
            continue
        if not valid_identifier(window.get("window_id")) or not valid_identifier(
            window.get("source_system")
        ):
            add_issue(issues, "INVALID_SCHEDULE_WINDOW")
            continue
        key = (window["source_system"], window["window_id"])
        if key in window_keys:
            add_issue(issues, "DUPLICATE_SCHEDULE_WINDOW")
        window_keys.add(key)
        requested = window.get("stores")
        if (
            not isinstance(requested, list)
            or not requested
            or not all(valid_identifier(item) for item in requested)
            or len(set(requested)) != len(requested)
            or not set(requested) <= stores
        ):
            add_issue(issues, "INVALID_SCHEDULE_STORES", window_id=window.get("window_id"))
        try:
            stamps = []
            for field in ("starts_at", "ends_at"):
                value = window.get(field)
                if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
                    raise ValueError
                stamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
            if stamps[0] >= stamps[1]:
                raise ValueError
        except (ValueError, OverflowError):
            add_issue(issues, "INVALID_DELIVERY_INTERVAL", window_id=window.get("window_id"))
    matching = [
        window
        for window in windows
        if isinstance(window, dict)
        and window.get("window_id") == manifest.get("window_id")
        and window.get("source_system") == manifest.get("source_system")
    ]
    if len(matching) != 1:
        add_issue(issues, "UNKNOWN_OR_DUPLICATE_WINDOW")
    else:
        requested = matching[0].get("stores")
        if (
            not isinstance(requested, list)
            or not requested
            or not all(valid_identifier(item) for item in requested)
        ):
            expected = set()
        else:
            expected = set(requested)
    return stores, products, expected


def _safe_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 for character in value)
    ):
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and ".." not in path.parts
        and all(part not in ("", ".") for part in path.parts)
        and path.suffix == ".csv"
    )


def validate_manifest(
    manifest: dict[str, object], issues: list[dict[str, object]]
) -> tuple[str, list[dict[str, object]], set[str]]:
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1:
        add_issue(issues, "UNSUPPORTED_SCHEMA_VERSION")
    for field in ("batch_id", "source_system", "window_id"):
        if not valid_identifier(manifest.get(field)):
            add_issue(issues, "INVALID_MANIFEST_FIELD", field=field)
    if "correction_of" in manifest and not valid_identifier(manifest["correction_of"]):
        add_issue(issues, "INVALID_MANIFEST_FIELD", field="correction_of")
    allowed = {
        "schema_version",
        "batch_id",
        "source_system",
        "window_id",
        "files",
        "zero_movement",
        "covered_stores",
        "correction_of",
    }
    if set(manifest) - allowed:
        add_issue(issues, "UNKNOWN_MANIFEST_FIELDS", fields=sorted(set(manifest) - allowed))
    entries = manifest.get("files")
    files: list[dict[str, object]] = []
    if not isinstance(entries, list):
        add_issue(issues, "INVALID_MANIFEST_FILES")
    else:
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                add_issue(issues, "INVALID_MANIFEST_FILE")
                continue
            path = entry.get("path")
            if not _safe_path(path):
                add_issue(issues, "UNSAFE_PATH", file=path)
                continue
            assert isinstance(path, str)
            if path in seen:
                add_issue(issues, "DUPLICATE_MANIFEST_FILE", file=path)
                continue
            seen.add(path)
            if (
                set(entry) != {"path", "sha256", "row_count", "store_id"}
                or not isinstance(entry.get("sha256"), str)
                or not HASH.fullmatch(entry["sha256"])
                or type(entry.get("row_count")) is not int
                or entry["row_count"] < 0
                or not valid_identifier(entry.get("store_id"))
            ):
                add_issue(issues, "INVALID_MANIFEST_FILE", file=path)
                continue
            files.append(entry)
    zero = manifest.get("zero_movement")
    if (
        not isinstance(zero, list)
        or not all(valid_identifier(item) for item in zero)
        or len(set(zero)) != len(zero)
    ):
        add_issue(issues, "INVALID_ZERO_CONFIRMATION")
        zero = []
    canonical = dict(manifest)
    if isinstance(entries, list):
        canonical["files"] = sorted(entries, key=stable_json)
    for field in ("zero_movement", "covered_stores"):
        value = canonical.get(field)
        if isinstance(value, list):
            canonical[field] = sorted(value, key=stable_json)
    return logical_hash(canonical), files, set(zero)

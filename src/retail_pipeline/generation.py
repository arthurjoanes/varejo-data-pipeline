from __future__ import annotations

import csv
import hashlib
import random
from collections.abc import Iterable, Mapping
from contextlib import ExitStack
from pathlib import Path

from retail_pipeline.contracts import BUSINESS_FIELDS, stable_json, valid_identifier

GENERATOR_VERSION = 2
SCENARIOS = (
    "valid",
    "missing",
    "corrected",
    "cancelled",
    "reordered",
    "conflict",
    "multi_invalid",
    "timezone",
    "duplicate",
    "old",
    "date_corrected",
    "reactivated",
)


def fixture_rows() -> list[dict[str, str]]:
    base = {
        "source_system": "synthetic-pos",
        "revision": "1",
        "operation": "UPSERT",
        "sold_at": "2026-01-01T12:00:00-03:00",
        "source_updated_at": "2026-01-02T08:00:00-03:00",
    }
    lines = [
        ("S01", "A1", "1", "P01", "2", "10.00", "1.00"),
        ("S01", "A1", "2", "P02", "1", "5.00", "0.00"),
        ("S01", "A2", "1", "P03", "3", "7.50", "2.50"),
        ("S02", "B1", "1", "P01", "1", "20.00", "0.00"),
    ]
    fields = (
        "store_id",
        "sale_id",
        "line_id",
        "product_id",
        "quantity",
        "unit_price_brl",
        "line_discount_brl",
    )
    return [{**base, **dict(zip(fields, values, strict=False))} for values in lines]


def default_catalog(store_count: int = 3, product_count: int = 3) -> dict[str, object]:
    states = ("SP", "MG", "RJ", "PR")
    categories = ("Mercearia", "Casa", "Higiene")
    return {
        "schema_version": 1,
        "stores": [
            {
                "store_id": f"S{number:02d}",
                "name": f"Loja Horizonte {number:02d}",
                "state": states[(number - 1) % len(states)],
                "timezone": "America/Sao_Paulo",
                "active": True,
            }
            for number in range(1, store_count + 1)
        ],
        "products": [
            {
                "product_id": f"P{number:02d}",
                "name": f"Produto Aurora {number:02d}",
                "category": categories[(number - 1) % len(categories)],
            }
            for number in range(1, product_count + 1)
        ],
    }


def default_schedule(
    stores: Iterable[str] = ("S01", "S02", "S03"),
    *,
    source_system: str = "synthetic-pos",
    window_id: str = "jan-2026",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "windows": [
            {
                "window_id": window_id,
                "source_system": source_system,
                "stores": sorted(set(stores)),
                "starts_at": "2026-01-01T00:00:00-03:00",
                "ends_at": "2026-03-01T00:00:00-03:00",
            }
        ],
    }


def write_batch(
    output: Path,
    rows: Iterable[Mapping[str, object]],
    *,
    batch_id: str = "fixture-valid",
    source_system: str = "synthetic-pos",
    window_id: str = "jan-2026",
    expected_stores: Iterable[str] = ("S01", "S02", "S03"),
    zero_movement: Iterable[str] = ("S03",),
    catalog: dict[str, object] | None = None,
    correction_of: str | None = None,
) -> Path:
    """Escreve um CSV por loja em fluxo; não conserva a massa no driver."""
    if not all(valid_identifier(value) for value in (batch_id, source_system, window_id)):
        raise ValueError("Lote, origem e janela devem usar identificadores válidos.")
    output.mkdir(parents=True, exist_ok=True)
    expected = sorted(set(expected_stores))
    zero = sorted(set(zero_movement))
    if not all(valid_identifier(store) for store in expected + zero):
        raise ValueError("Identificador de loja inválido.")
    writers: dict[str, csv.DictWriter[str]] = {}
    counts: dict[str, int] = {}
    with ExitStack() as stack:
        for row in rows:
            store = str(row.get("store_id", ""))
            # Guarda a loja inválida para diagnóstico sem usá-la como nome de arquivo.
            file_store = store if valid_identifier(store) else (expected[0] if expected else "S01")
            if file_store not in writers:
                handle = stack.enter_context(
                    (output / f"{file_store}.csv").open("w", encoding="utf-8", newline="")
                )
                writer = csv.DictWriter(
                    handle, fieldnames=BUSINESS_FIELDS, lineterminator="\n", extrasaction="ignore"
                )
                writer.writeheader()
                writers[file_store] = writer
                counts[file_store] = 0
            writer = writers[file_store]
            writer.writerow(dict(row))
            counts[file_store] += 1
    entries: list[dict[str, object]] = []
    for store, count in sorted(counts.items()):
        path = output / f"{store}.csv"
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        entries.append(
            {"path": path.name, "store_id": store, "row_count": count, "sha256": digest.hexdigest()}
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "batch_id": batch_id,
        "source_system": source_system,
        "window_id": window_id,
        "files": entries,
        "zero_movement": zero,
        "covered_stores": sorted(set(counts) | set(zero)),
    }
    if correction_of is not None:
        manifest["correction_of"] = correction_of
    schedule = default_schedule(expected, source_system=source_system, window_id=window_id)
    for name, document in (
        ("manifest.json", manifest),
        ("catalog.json", catalog if catalog is not None else default_catalog()),
        ("schedule.json", schedule),
    ):
        (output / name).write_text(stable_json(document) + "\n", encoding="utf-8", newline="\n")
    return output


def _large_rows(count: int, seed: int) -> Iterable[dict[str, str]]:
    randomizer = random.Random(seed)
    for index in range(count):
        store = index % 12 + 1
        group = index // 36
        day = group % 30 + 1
        product = randomizer.randrange(1, 13)
        quantity = randomizer.randrange(1, 6)
        price_cents = 250 + product * 137 + randomizer.randrange(0, 250)
        discount_cents = randomizer.randrange(0, 101) if group % 7 in (5, 6) else 0
        yield {
            "source_system": "synthetic-pos",
            "store_id": f"S{store:02d}",
            "sale_id": f"D{day:02d}-{group:07d}",
            "line_id": str((index // 12) % 3 + 1),
            "revision": "1",
            "operation": "UPSERT",
            "product_id": f"P{product:02d}",
            "sold_at": f"2026-01-{day:02d}T{8 + store % 12:02d}:00:00-03:00",
            "quantity": str(quantity),
            "unit_price_brl": f"{price_cents // 100}.{price_cents % 100:02d}",
            "line_discount_brl": f"{discount_cents // 100}.{discount_cents % 100:02d}",
            "source_updated_at": "2026-02-01T08:00:00-03:00",
        }


def generate_scenario(
    output: Path,
    size: str = "fixture",
    seed: int = 42,
    rows: int = 30_000,
    batch_id: str = "fixture-valid",
    scenario: str = "valid",
) -> Path:
    if size not in ("fixture", "demo", "scale") or scenario not in SCENARIOS:
        raise ValueError("Tamanho ou cenário desconhecido.")
    if rows <= 0:
        raise ValueError("A escala deve ter pelo menos uma linha.")
    if size != "fixture":
        if scenario not in ("valid", "missing"):
            raise ValueError(
                "Cenários de revisão usam a fixture manual; demo/scale aceitam valid/missing."
            )
        count = 30_000 if size == "demo" else rows
        expected = [f"S{number:02d}" for number in range(1, 13)]
        zero = expected[min(count, 12) :]
        write_batch(
            output,
            _large_rows(count, seed),
            batch_id=batch_id,
            expected_stores=expected,
            zero_movement=zero,
            catalog=default_catalog(12, 12),
        )
        if scenario == "missing":
            (output / "S01.csv").unlink()
        return output
    events = fixture_rows()
    if scenario == "corrected":
        events[0].update(
            revision="2",
            quantity="3",
            unit_price_brl="11.00",
            source_updated_at="2026-02-02T09:00:00-03:00",
        )
    elif scenario == "cancelled":
        events[-1].update(
            revision="2", operation="CANCEL", source_updated_at="2026-02-03T09:00:00-03:00"
        )
    elif scenario == "date_corrected":
        for event in events[:2]:
            event.update(
                revision="3",
                sold_at="2026-01-02T12:00:00-03:00",
                source_updated_at="2026-02-04T09:00:00-03:00",
            )
    elif scenario == "reactivated":
        events[-1].update(
            revision="3", operation="UPSERT", source_updated_at="2026-02-04T09:00:00-03:00"
        )
    elif scenario == "reordered":
        events.reverse()
    elif scenario == "duplicate":
        events.extend(dict(event) for event in list(events))
    elif scenario == "conflict":
        events.append({**events[0], "unit_price_brl": "11.00"})
    elif scenario == "multi_invalid":
        events.append(
            {
                **events[0],
                "sale_id": "INVALID",
                "quantity": "0",
                "unit_price_brl": "-1.00",
                "product_id": "P999",
                "sold_at": "2026-01-01T12:00:00",
            }
        )
    elif scenario == "timezone":
        events[0]["sold_at"] = "2026-01-02T02:59:59Z"
        events[1]["sold_at"] = "2026-01-02T03:00:00Z"
        events[1]["sale_id"] = "A3"
    correction = (
        "fixture-valid"
        if scenario in ("corrected", "cancelled", "date_corrected", "reactivated")
        else None
    )
    write_batch(output, events, batch_id=batch_id, correction_of=correction)
    if scenario == "missing":
        (output / "S02.csv").unlink()
    return output

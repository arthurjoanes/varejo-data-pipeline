from pathlib import Path

from retail_pipeline.generation import generate_scenario
from retail_pipeline.ingestion import prepare_batch


def test_generator_is_byte_deterministic(tmp_path: Path) -> None:
    first = generate_scenario(tmp_path / "one", size="scale", rows=200, seed=42)
    second = generate_scenario(tmp_path / "two", size="scale", rows=200, seed=42)
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    prepared = prepare_batch(first, tmp_path / "evidence", "deterministic")
    assert prepared.stats["received"] == 200
    assert not prepared.issues
    assert len(prepared.coverage["expected"]) == 12


def test_fixture_business_total_calculated_manually(tmp_path: Path) -> None:
    import csv
    from decimal import Decimal

    folder = generate_scenario(tmp_path / "input")
    with (folder / "S01.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    amounts = [
        int(row["quantity"]) * Decimal(row["unit_price_brl"]) - Decimal(row["line_discount_brl"])
        for row in rows
    ]
    assert amounts == [Decimal("19.00"), Decimal("5.00"), Decimal("20.00")]
    assert len({row["sale_id"] for row in rows}) == 2

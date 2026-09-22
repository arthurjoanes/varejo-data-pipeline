"""Verifica uma fixture em volume descartável, executando seed no runtime antigo e resume no novo."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from pyspark.sql import functions as F

from retail_pipeline.generation import default_catalog, default_schedule, generate_scenario
from retail_pipeline.pipeline import process_batch
from retail_pipeline.publication import load_snapshot, read_table
from retail_pipeline.references import configure_references
from retail_pipeline.reporting import generate_report
from retail_pipeline.spark import create_spark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seed", "resume"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state, inputs = args.root / "state", args.root / "inputs"
    spark = create_spark()

    def total(snapshot):
        return (
            read_table(spark, snapshot, "gold_store_day").agg(F.sum("net_revenue_brl")).first()[0]
        )

    try:
        if args.phase == "seed":
            if state.exists():
                raise ValueError("seed exige estado novo; nenhum dado existente será removido.")
            configure_references(state, default_catalog(), default_schedule())
            valid = generate_scenario(inputs / "valid")
            result = process_batch(spark, state, valid)
            assert result.state == "PUBLISHED", result.issues
            assert total(load_snapshot(state)) == Decimal("64.00")
            evidence = {"phase": "seed", "spark": spark.version, "total_brl": "64.00"}
        else:
            previous = load_snapshot(state)
            assert previous is not None
            assert total(previous) == Decimal("64.00")
            replay = process_batch(spark, state, inputs / "valid")
            assert replay.state == "NO_CHANGE", replay.issues
            corrected = generate_scenario(
                inputs / "corrected", scenario="corrected", batch_id="migration-corrected"
            )
            result = process_batch(spark, state, corrected)
            assert result.state == "PUBLISHED", result.issues
            assert total(load_snapshot(state)) == Decimal("77.00")
            assert total(previous) == Decimal("64.00")
            report = generate_report(spark, state, args.root / "report.html", synthetic_data=True)
            assert "77,00" in report.read_text(encoding="utf-8")
            evidence = {
                "phase": "resume",
                "spark": spark.version,
                "total_brl": "77.00",
                "previous_version_total_brl": "64.00",
                "replay": replay.state,
                "report": "passed",
            }
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()

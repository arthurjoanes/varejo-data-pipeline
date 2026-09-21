from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from retail_pipeline.generation import default_catalog, default_schedule, generate_scenario
from retail_pipeline.pipeline import process_batch
from retail_pipeline.publication import atomic_json, load_snapshot, read_table
from retail_pipeline.references import configure_references
from retail_pipeline.reporting import explain_indicator, generate_report


def run_demo(spark: SparkSession, data_dir: Path, export_dir: Path) -> dict[str, object]:
    # Cada demonstração nasce isolada. Repetir nunca apaga estado anterior.
    root = data_dir / "demos" / uuid.uuid4().hex
    export_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    steps: list[dict[str, object]] = []

    # A ausência de publicação tem uma demonstração própria, sem alterar a
    # jornada de correções e recuperação que começa com a fixture válida.
    quality_root = root / "quality-check"
    configure_references(root, default_catalog(), default_schedule())
    configure_references(quality_root, default_catalog(), default_schedule())
    quality_input = generate_scenario(
        root / "quality-input", scenario="multi_invalid", batch_id="quality-review"
    )
    quality_result = process_batch(spark, quality_root, quality_input)
    if (
        quality_result.state != "BLOCKED"
        or quality_result.stats["rejected"] != 1
        or quality_result.stats["violations"] != 4
        or load_snapshot(quality_root) is not None
    ):
        raise RuntimeError("Demonstração de qualidade sem publicação divergiu do contrato.")
    generate_report(spark, quality_root, export_dir / "quality-review.html", synthetic_data=True)

    def revenue() -> Decimal:
        snapshot = load_snapshot(root)
        if snapshot is None:
            return Decimal(0)
        row = read_table(spark, snapshot, "gold_store_day").agg(F.sum("net_revenue_brl")).first()
        if row is None:
            raise ValueError("Agregação não retornou totais.")
        return Decimal(row[0] or 0)

    def run(
        name: str,
        scenario: str,
        expected: str,
        expected_revenue: str,
        *,
        fail_at: str | None = None,
    ) -> Path:
        path = generate_scenario(root / "input" / name, batch_id=name, scenario=scenario)
        result = process_batch(spark, root, path, fail_at=fail_at, allow_failures=bool(fail_at))
        amount = revenue()
        if result.state != expected or amount != Decimal(expected_revenue):
            raise RuntimeError(
                f"Demo {name}: estado {result.state}, receita {amount}; esperado {expected}/{expected_revenue}. {result.issues}"
            )
        steps.append({"step": name, "result": asdict(result), "revenue_brl": str(amount)})
        return path

    valid = run("fixture-valid", "valid", "PUBLISHED", "64.00")
    explanation = explain_indicator(spark, root, store_id="S01", business_date="2026-01-01")
    atomic_json(export_dir / "explain.json", explanation)
    repeated = process_batch(spark, root, valid)
    if repeated.state != "NO_CHANGE" or revenue() != Decimal("64.00"):
        raise RuntimeError("Repetição alterou o resultado de negócio.")
    steps.append({"step": "repeat", "result": asdict(repeated), "revenue_brl": str(revenue())})
    incomplete = run("missing-delivery", "missing", "BLOCKED", "64.00")
    generate_report(spark, root, export_dir / "blocked-report.html", synthetic_data=True)
    generate_scenario(incomplete, batch_id="missing-delivery", scenario="valid")
    completed = process_batch(spark, root, incomplete)
    if completed.state != "PUBLISHED" or revenue() != Decimal("64.00"):
        raise RuntimeError("Reposição da entrega original falhou.")
    steps.append(
        {"step": "complete-delivery", "result": asdict(completed), "revenue_brl": str(revenue())}
    )
    run("late-correction", "corrected", "PUBLISHED", "77.00")
    run("late-cancellation", "cancelled", "PUBLISHED", "57.00")
    snapshot_before = load_snapshot(root)
    pending = run(
        "recoverable", "reactivated", "TECHNICAL_FAILURE", "57.00", fail_at="before_publish"
    )
    if load_snapshot(root) != snapshot_before:
        raise RuntimeError("Falha tornou candidato visível.")
    generate_report(spark, root, export_dir / "failure-report.html", synthetic_data=True)
    recovered = process_batch(spark, root, pending)
    if recovered.state != "PUBLISHED" or revenue() != Decimal("77.00"):
        raise RuntimeError("Retomada não recuperou o total esperado.")
    steps.append({"step": "recovery", "result": asdict(recovered), "revenue_brl": str(revenue())})
    generate_report(spark, root, export_dir / "report.html", synthetic_data=True)
    evidence: dict[str, object] = {
        "data_dir": str(root),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "steps": steps,
        "quality_check": asdict(quality_result),
        "report": str(export_dir / "report.html"),
    }
    atomic_json(export_dir / "demo-evidence.json", evidence)
    atomic_json(data_dir / "last-demo.json", {"data_dir": str(root)})
    print(
        json.dumps(
            {
                "demo": "concluída",
                "data_dir": str(root),
                "duration_seconds": evidence["duration_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return evidence

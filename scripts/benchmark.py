"""Mede o processamento de 30 mil linhas em estado separado."""

from __future__ import annotations

import os
import platform
import time
import uuid
from pathlib import Path

from pyspark.sql import functions as F

from retail_pipeline.generation import (
    GENERATOR_VERSION,
    default_catalog,
    default_schedule,
    generate_scenario,
)
from retail_pipeline.pipeline import process_batch
from retail_pipeline.publication import atomic_json, load_snapshot, read_table
from retail_pipeline.references import configure_references
from retail_pipeline.reporting import generate_report
from retail_pipeline.spark import create_spark


def main() -> None:
    started = time.perf_counter()
    root = Path(os.getenv("RETAIL_DATA_DIR", "/data")) / "benchmarks" / uuid.uuid4().hex
    output = Path(os.getenv("RETAIL_EXPORT_DIR", "/app/artifacts"))
    configure_references(
        root, default_catalog(12, 12), default_schedule(f"S{number:02d}" for number in range(1, 13))
    )
    source = generate_scenario(root / "input", size="demo", seed=42, batch_id="demo30k")
    generation_seconds = time.perf_counter() - started
    spark = create_spark()
    try:
        outcome = process_batch(spark, root, source)
        if outcome.state != "PUBLISHED" or outcome.stats["received"] != 30_000:
            raise RuntimeError(f"Experimento não publicou 30 mil registros: {outcome.issues}")
        snapshot = load_snapshot(root)
        if snapshot is None:
            raise RuntimeError("Manifesto ausente após publicação.")
        totals = (
            read_table(spark, snapshot, "gold_store_day")
            .agg(
                F.sum("net_revenue_brl").alias("net_revenue_brl"),
                F.sum("units").alias("units"),
                F.sum("sales_count").alias("sales_count"),
                F.countDistinct("store_id").alias("stores"),
                F.countDistinct("business_date").alias("days"),
            )
            .first()
        )
        if totals is None or totals["stores"] != 12 or totals["days"] != 30:
            raise RuntimeError("Escopo de 12 lojas/30 dias não reconciliado.")
        generate_report(spark, root, output / "demo30k-report.html")
        memory = Path("/sys/fs/cgroup/memory.peak")
        evidence = {
            "data_dir": str(root),
            "rows": 30_000,
            "seed": 42,
            "generator_version": GENERATOR_VERSION,
            "python": platform.python_version(),
            "spark": spark.version,
            "generation_seconds": round(generation_seconds, 3),
            "pipeline_seconds": outcome.duration_seconds,
            "elapsed_including_report_seconds": round(time.perf_counter() - started, 3),
            "container_peak_memory_bytes": int(memory.read_text()) if memory.exists() else None,
            "memory_scope": "cgroup memory.peak: container inteiro, inclusive cache de páginas",
            "container_limit": "3 GiB / 2 CPUs; Spark local[2], driver 1 GiB, shuffle 2",
            "network": "none (Compose)",
            "totals": totals.asDict(),
            "publication": snapshot,
        }
        atomic_json(output / "benchmark.json", evidence)
        print(f"Resultado: {output / 'benchmark.json'}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()

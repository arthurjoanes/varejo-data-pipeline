"""Fases locais da prova; Spark só inicia nas fases explicitamente solicitadas."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from proof_contracts import (
    MEASUREMENT_PLAN,
    csv_oracle,
    digest,
    inventory,
    make_archive,
    reject_referenced_removal,
    restore_archive,
    retention_contract,
    write_json,
)

INTERNAL_ROOT = "/data/proof"


def cgroup_observation():
    return {
        name: path.read_text().strip()
        for name in (
            "pids.current",
            "pids.max",
            "pids.events",
            "pids.peak",
            "memory.current",
            "memory.peak",
            "memory.events",
        )
        for path in [Path("/sys/fs/cgroup") / name]
        if path.is_file()
    }


def dependency_identity():
    import pyspark

    lock_path = Path("/app/runtime-jars.lock.json")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    jar_root = Path(pyspark.__file__).parent / "jars"
    actual = []
    for item in [*lock["replacements"], *lock["rebuilt_components"]]:
        path = jar_root / item["target"]
        checksum = digest(path)
        if checksum != item["sha256"]:
            raise ValueError("JAR efetivo diverge do lock de runtime montado.")
        actual.append({"name": path.name, "sha256": checksum})
    removed = [
        item["path"]
        for item in lock["removed_optional_components"]
        if (jar_root / item["path"]).exists()
    ]
    if removed:
        raise ValueError("Runtime conserva artefatos declarados removidos pelo lock.")
    return {
        "python": platform.python_version(),
        "pyspark": importlib.metadata.version("pyspark"),
        "delta_spark": importlib.metadata.version("delta-spark"),
        "runtime_lock_sha256": digest(lock_path),
        "locked_jars": actual,
        "removed_artifacts_absent": True,
        "delta_jars": [
            {"name": path.name, "sha256": digest(path)}
            for path in sorted(Path("/opt/delta-jars").glob("*.jar"))
        ],
        "embedded_build_records": [
            {"name": path.name, "sha256": digest(path)}
            for path in sorted(Path("/opt/varejo-runtime-builds").glob("*.json"))
        ],
    }


def publication_observations(spark, state):
    from pyspark.sql import functions as F

    from retail_pipeline.publication import load_snapshot, read_table

    current = load_snapshot(state)
    if current is None:
        raise ValueError("Estado sem publicação vigente.")
    publications = []
    for path in sorted((state / "publications").glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        tables = {}
        for name in sorted(snapshot["tables"]):
            frame = read_table(spark, snapshot, name)
            checksum = hashlib.sha256()
            count = 0
            ordered = frame.select(F.to_json(F.struct(*frame.columns)).alias("row")).orderBy("row")
            for row in ordered.toLocalIterator():
                checksum.update(row["row"].encode("utf-8") + b"\n")
                count += 1
            tables[name] = {"rows": count, "rows_sha256": checksum.hexdigest()}
            if name.startswith("gold_"):
                value = frame.agg(F.sum("net_revenue_brl")).first()[0]
                tables[name]["net_revenue_cents"] = int(value * 100) if value else 0
        publications.append({"snapshot": snapshot, "tables": tables})
    return {"current_publication_id": current["publication_id"], "publications": publications}


def prepare_restore(spark, root, evidence):
    from retail_pipeline.generation import default_catalog, default_schedule, generate_scenario
    from retail_pipeline.pipeline import process_batch
    from retail_pipeline.publication import load_snapshot
    from retail_pipeline.references import configure_references
    from retail_pipeline.reporting import generate_report

    state = root / "state"
    configure_references(state, default_catalog(), default_schedule())
    steps = []
    reports = []
    for name, scenario, expected in [
        ("fixture-valid", "valid", "PUBLISHED"),
        ("missing-delivery", "missing", "BLOCKED"),
        ("missing-delivery", "valid", "PUBLISHED"),
        ("late-correction", "corrected", "PUBLISHED"),
    ]:
        before = load_snapshot(state)
        source = generate_scenario(root / "inputs" / name, scenario=scenario, batch_id=name)
        result = process_batch(spark, state, source)
        if result.state != expected:
            raise ValueError(f"Fixture {name}/{scenario} retornou {result.state}.")
        after = load_snapshot(state)
        if expected == "BLOCKED" and after != before:
            raise ValueError("Bloqueio alterou a publicação vigente.")
        label = {0: "publication", 1: "blocked", 2: "recovery", 3: "corrected"}[len(steps)]
        report = generate_report(
            spark, state, evidence / "reports" / (label + ".html"), synthetic_data=True
        )
        reports.append(
            {
                "state": label,
                "path": "reports/" + report.name,
                "sha256": digest(report),
                "publication_id": after["publication_id"],
                "run_id": result.run_id,
            }
        )
        steps.append(
            {
                "batch_id": name,
                "scenario": scenario,
                "state": result.state,
                "publication_id": after["publication_id"],
                "run_id": result.run_id,
            }
        )
    observed = publication_observations(spark, state)
    totals = [
        item["tables"]["gold_store_day"]["net_revenue_cents"] for item in observed["publications"]
    ]
    if sorted(totals) != [6400, 6400, 7700]:
        raise ValueError("Totais da fixture não correspondem ao oráculo literal 64/64/77.")
    return {"observed": observed, "steps": steps, "reports": reports}


def prepare_measurement(spark, root, size):
    from retail_pipeline.generation import (
        _large_rows,
        default_catalog,
        default_schedule,
        write_batch,
    )
    from retail_pipeline.pipeline import process_batch
    from retail_pipeline.references import configure_references

    started = time.perf_counter()
    stores = [f"S{number:02d}" for number in range(1, 13)]
    configure_references(root / "state", default_catalog(12, 12), default_schedule(stores))
    paths = []
    for name, count in [("history", size), ("incoming", MEASUREMENT_PLAN["incoming_rows"])]:
        # Reusa o gerador existente; prefixo muda apenas a identidade das vendas entre batches.
        rows = (
            {**row, "sale_id": name + "-" + row["sale_id"]}
            for row in _large_rows(count, MEASUREMENT_PLAN["seed"])
        )
        paths.append(
            write_batch(
                root / "inputs" / name,
                rows,
                batch_id=name,
                expected_stores=stores,
                zero_movement=(),
                catalog=default_catalog(12, 12),
            )
        )
    oracle = csv_oracle(paths)
    write_json(root / "oracle.json", oracle)
    generation_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result = process_batch(spark, root / "state", paths[0])
    if result.state != "PUBLISHED" or result.stats["received"] != size:
        raise ValueError("Baseline histórica não publicada integralmente.")
    return {
        "history_rows": size,
        "incoming_rows": MEASUREMENT_PLAN["incoming_rows"],
        "generation_seconds": generation_seconds,
        "baseline_pipeline_seconds": time.perf_counter() - started,
        "oracle": oracle,
    }


def measure(spark, root, evidence):
    from pyspark.sql import functions as F

    from retail_pipeline.pipeline import process_batch
    from retail_pipeline.publication import load_snapshot, read_table
    from retail_pipeline.reporting import generate_report

    state = root / "state"
    before = load_snapshot(state)
    before_bytes = sum(entry["bytes"] for entry in inventory(root).values())
    started = time.perf_counter()
    result = process_batch(spark, state, root / "inputs/incoming")
    processing = time.perf_counter() - started
    if result.state != "PUBLISHED" or result.stats["received"] != MEASUREMENT_PLAN["incoming_rows"]:
        raise ValueError("Recomputação não publicou o segundo batch completo.")
    snapshot = load_snapshot(state)
    if snapshot is None or before is None or snapshot["publication_id"] == before["publication_id"]:
        raise ValueError("Recomputação não produziu nova publicação.")
    started = time.perf_counter()
    rows = (
        read_table(spark, snapshot, "gold_store_day")
        .select(
            F.col("business_date").cast("string"),
            "store_id",
            (F.col("net_revenue_brl") * 100).cast("long").alias("net_revenue_cents"),
            "units",
            "item_lines",
            "sales_count",
        )
        .orderBy("business_date", "store_id")
        .collect()
    )
    actual = [row.asDict() for row in rows]
    oracle = json.loads((root / "oracle.json").read_text(encoding="utf-8"))
    if actual != oracle["rows"]:
        raise ValueError("Indicadores publicados diferem do oráculo CSV/Decimal independente.")
    validation = time.perf_counter() - started
    started = time.perf_counter()
    report = generate_report(spark, state, evidence / "report.html", synthetic_data=True)
    reporting = time.perf_counter() - started
    memory = Path("/sys/fs/cgroup/memory.peak")
    return {
        "pipeline_seconds": processing,
        "pipeline_internal_seconds": result.duration_seconds,
        "pipeline_stages_seconds": result.stages,
        "validation_seconds": validation,
        "report_seconds": reporting,
        "report_sha256": digest(report),
        "publication_id": snapshot["publication_id"],
        "baseline_publication_id": before["publication_id"],
        "oracle_matched": True,
        "oracle_rows": len(actual),
        "oracle_received_rows": oracle["received_rows"],
        "net_revenue_cents": oracle["net_revenue_cents"],
        "peak_memory_bytes": int(memory.read_text()) if memory.is_file() else None,
        "memory_scope": "memory.peak do container inteiro desta amostra, incluindo JVM e cache de páginas; não é heap Spark",
        "disk_before_bytes": before_bytes,
        "disk_after_bytes": sum(entry["bytes"] for entry in inventory(root).values()),
        "disk_scope": "Bytes lógicos dos arquivos em /data/proof; exclui temporários Spark, imagem, cópia tar e overhead do filesystem.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=[
            "prepare",
            "observe",
            "inventory",
            "archive",
            "install",
            "measure-seed",
            "measure",
            "regress",
        ],
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--size", type=int, choices=MEASUREMENT_PLAN["history_rows"])
    args = parser.parse_args()
    root = Path(INTERNAL_ROOT)
    evidence = args.output.parent
    started = time.perf_counter()
    result = {"phase": args.phase, "status": "failed"}
    result["cgroup_before"] = cgroup_observation()
    spark = None
    try:
        if args.phase in {"prepare", "measure-seed"}:
            if root.exists() and any(root.iterdir()):
                raise ValueError(
                    "Preparação exige estado novo; não há seed sobre estado existente."
                )
            root.mkdir(parents=True, exist_ok=True)
        if args.phase == "regress":
            result["dependencies"] = dependency_identity()
            Path("/data/tmp/spark").mkdir(parents=True, exist_ok=True)
            selection = [
                "tests/unit/test_state_proof.py",
                "tests/unit/test_generation.py",
                "tests/unit/test_contracts.py",
                "tests/unit/test_input_limits.py",
                "tests/unit/test_reporting.py",
                "tests/integration/test_commit_boundary.py",
            ]
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--junitxml=" + str(evidence / "regressions.xml"),
                    *selection,
                ],
                check=False,
            )
            result["selection"] = selection
            result["pytest_exit_code"] = completed.returncode
            if completed.returncode:
                raise ValueError("Regressões Linux não aprovadas; preserve JUnit e log.")
        elif args.phase == "inventory":
            result["inventory"] = inventory(root)
        elif args.phase == "archive":
            result["manifest"] = make_archive(root, args.archive, internal_root=INTERNAL_ROOT)
            write_json(args.manifest, result["manifest"])
        elif args.phase == "install":
            restore_archive(
                args.archive,
                root,
                json.loads(args.manifest.read_text(encoding="utf-8")),
                internal_root=INTERNAL_ROOT,
            )
            result["inventory"] = inventory(root)
        else:
            from retail_pipeline.spark import create_spark

            if args.phase in {"observe", "measure"}:
                retention_contract(root / "state")
            Path("/data/tmp/spark").mkdir(parents=True, exist_ok=True)
            start = time.perf_counter()
            spark = create_spark()
            result["spark_startup_seconds"] = time.perf_counter() - start
            result["startup_scope"] = (
                "Chamada create_spark medida; inicialização lazy posterior permanece no processamento, sem subtração estimada."
            )
            result["runtime"] = {"spark": spark.version, "python": platform.python_version()}
            if args.phase == "prepare":
                result.update(prepare_restore(spark, root, evidence))
            elif args.phase == "measure-seed":
                if args.size is None:
                    raise ValueError("Baseline exige um dos dois tamanhos registrados.")
                result.update(prepare_measurement(spark, root, args.size))
            elif args.phase == "measure":
                result.update(measure(spark, root, evidence))
            else:
                result["observed"] = publication_observations(spark, root / "state")
            result["retention"] = retention_contract(root / "state")
            try:
                reject_referenced_removal(
                    root / "state",
                    result["retention"],
                    [result["retention"]["protected_paths"][-1]],
                )
            except ValueError:
                result["referenced_removal_refused"] = True
            else:
                raise ValueError("Retenção não recusou proposta referenciada.")
        result["status"] = "passed"
    except Exception as error:
        result["error_type"] = type(error).__name__
        raise
    finally:
        try:
            if spark is not None:
                spark.stop()
        except Exception as error:
            result.update(status="failed", stop_error_type=type(error).__name__)
            raise
        finally:
            result["cgroup_after"] = cgroup_observation()
            result["root_exists"] = root.exists()
            result["total_seconds"] = time.perf_counter() - started
            write_json(args.output, result)


if __name__ == "__main__":
    main()

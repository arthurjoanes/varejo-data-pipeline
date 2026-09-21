from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from retail_pipeline.contracts import KEY_FIELDS
from retail_pipeline.ingestion import prepare_batch
from retail_pipeline.publication import (
    Publication,
    atomic_json,
    load_snapshot,
    publish,
    read_table,
    table_reference,
    writer_lock,
)
from retail_pipeline.references import load_references
from retail_pipeline.transformations import (
    REVISION_KEY,
    bronze_schema,
    conflicting_keys,
    current_state,
    eligible_history,
    gold_tables,
    merge_state,
    reconcile,
    type_events,
)


class InjectedFailure(RuntimeError):
    pass


@dataclass
class RunResult:
    run_id: str
    batch_id: str = "unknown"
    state: str = "RUNNING"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    duration_seconds: float = 0.0
    stages: dict[str, float] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
    coverage: dict[str, list[str]] = field(default_factory=dict)
    issues: list[dict[str, object]] = field(default_factory=list)
    publication_id: str | None = None

    @property
    def exit_code(self) -> int:
        if self.state == "BLOCKED":
            return 2
        if self.state == "TECHNICAL_FAILURE":
            return 3
        return 0


def log_event(root: Path, result: RunResult, stage: str, duration: float) -> None:
    event = {
        "stage": stage,
        "run_id": result.run_id,
        "batch_id": result.batch_id,
        "duration_seconds": round(duration, 4),
        "state": result.state,
        "counts": result.stats,
    }
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    print(line, flush=True)
    (root / "logs").mkdir(exist_ok=True)
    with (root / "logs" / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


@contextmanager
def stage(root: Path, result: RunResult, name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        result.stages[name] = round(elapsed, 4)
        log_event(root, result, name, elapsed)


def inject_failure(requested: str | None, point: str) -> None:
    if requested == point:
        raise InjectedFailure(f"Falha de teste: {point}")


def record_failure(root: Path, result: RunResult, error: Exception) -> None:
    # O manifesto continua sendo a autoridade mesmo se a auditoria falhar
    # depois do commit, inclusive no fechamento da tentativa.
    committed = load_snapshot(root)
    visible = committed is not None and committed["run_id"] == result.run_id
    result.state = "PUBLISHED" if visible else "TECHNICAL_FAILURE"
    if committed and visible:
        result.publication_id = committed["publication_id"]
    result.issues.append(
        {
            "code": "AUDIT_WRITE_FAILURE" if visible else "TECHNICAL_FAILURE",
            "severity": "WARNING" if visible else "ERROR",
            "message": str(error),
            "type": type(error).__name__,
        }
    )


def process_batch(
    spark: SparkSession,
    root: Path,
    input_dir: Path,
    *,
    validate_only: bool = False,
    fail_at: str | None = None,
    allow_failures: bool = False,
) -> RunResult:
    if fail_at and (
        not allow_failures or fail_at not in {"after_ingestion", "after_gold", "before_publish"}
    ):
        raise ValueError("Injeção de falha exige modo demo/teste e ponto conhecido.")
    with writer_lock(root):
        result = RunResult(run_id=uuid.uuid4().hex)
        run_dir = root / "runs" / result.run_id
        run_dir.mkdir(parents=True)
        atomic_json(run_dir / "attempt.json", asdict(result))
        start = time.perf_counter()
        try:
            _process(spark, root, input_dir, run_dir, result, validate_only, fail_at)
        except Exception as exc:
            record_failure(root, result, exc)
        finally:
            result.duration_seconds = round(time.perf_counter() - start, 4)
            try:
                atomic_json(run_dir / "attempt.json", asdict(result))
                log_event(root, result, "complete", result.duration_seconds)
            except Exception as exc:
                record_failure(root, result, exc)
                # Saída estruturada continua disponível ao operador quando
                # o volume não aceita o registro final de auditoria.
                print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
        return result


def _process(
    spark: SparkSession,
    root: Path,
    input_dir: Path,
    run_dir: Path,
    result: RunResult,
    validate_only: bool,
    fail_at: str | None,
) -> None:
    snapshot = load_snapshot(root)
    references = load_references(root)
    if references is None:
        result.state = "BLOCKED"
        result.issues.append(
            {
                "code": "OPERATOR_REFERENCES_MISSING",
                "severity": "ERROR",
                "message": "Configure catálogo e calendário do operador antes de validar/publicar.",
            }
        )
        return
    with stage(root, result, "ingestion"):
        prepared = prepare_batch(
            input_dir, run_dir / "evidence", result.run_id, operator_references=references
        )
        result.batch_id = prepared.batch_id
        result.stats = dict(prepared.stats)
        result.stats.update(duplicates=0, conflicts=0, stale=0, revision_checks_executed=0)
        result.coverage = dict(prepared.coverage)
        result.issues = list(prepared.issues)
        identity = hashlib.sha256(prepared.batch_id.encode()).hexdigest()
        registry = root / "batches" / f"{identity}.json"
        if registry.exists():
            known = json.loads(registry.read_text(encoding="utf-8"))
            if known["manifest_hash"] != prepared.manifest_hash:
                result.issues.append(
                    {
                        "code": "BATCH_ID_CONFLICT",
                        "severity": "ERROR",
                        "message": "batch_id usado por outro manifesto. Use um novo batch_id.",
                    }
                )
            if known.get("reference_hashes") != prepared.reference_hashes:
                result.issues.append(
                    {
                        "code": "BATCH_REFERENCE_CONFLICT",
                        "severity": "ERROR",
                        "message": "Catálogo/calendário divergem da primeira tentativa, ou o registro legado não contém seus hashes. Use novo batch_id para revalidar a configuração.",
                    }
                )
        elif prepared.manifest:
            atomic_json(
                registry,
                {
                    "batch_id": prepared.batch_id,
                    "manifest_hash": prepared.manifest_hash,
                    "manifest": prepared.manifest,
                    "reference_hashes": prepared.reference_hashes,
                },
            )
        bronze = spark.read.schema(bronze_schema()).json(str(prepared.rows_path))
        bronze_path = run_dir / "bronze"
        bronze.write.format("delta").save(str(bronze_path))
        bronze = spark.read.format("delta").load(str(bronze_path))
        quarantine = bronze.filter(F.size("errors") > 0)
        quarantine.write.format("delta").save(str(run_dir / "quarantine"))
    inject_failure(fail_at, "after_ingestion")
    if any(issue.get("severity", "ERROR") == "ERROR" for issue in result.issues):
        result.state = "BLOCKED"
        return

    with stage(root, result, "quality"):
        incoming = type_events(bronze)
        previous = read_table(spark, snapshot, "history") if snapshot else None
        combined = incoming if previous is None else previous.unionByName(incoming)
        conflicts = conflicting_keys(combined)
        rejected = incoming.join(conflicts, REVISION_KEY, "inner")
        conflict_count = rejected.count()
        result.stats["conflicts"] = conflict_count
        distinct_incoming = incoming.select(*REVISION_KEY, "payload_hash").distinct()
        duplicate_count = result.stats["received"] - distinct_incoming.count()
        if previous is not None:
            duplicate_count += distinct_incoming.join(
                previous.select(*REVISION_KEY, "payload_hash"),
                [*REVISION_KEY, "payload_hash"],
                "inner",
            ).count()
        result.stats["duplicates"] = duplicate_count
        maxima = combined.groupBy(*KEY_FIELDS).agg(F.max("revision").alias("max_revision"))
        result.stats["stale"] = (
            incoming.join(maxima, list(KEY_FIELDS))
            .filter(F.col("revision") < F.col("max_revision"))
            .count()
        )
        result.stats["revision_checks_executed"] = 1
        if conflict_count:
            result.stats["rejected"] += conflict_count
            result.stats["valid"] -= conflict_count
            result.stats["violations"] += conflict_count
            rejected.withColumn("errors", F.array(F.lit("REVISION_CONFLICT"))).write.format(
                "delta"
            ).save(str(run_dir / "revision_conflicts"))
            result.issues.append(
                {
                    "code": "REVISION_CONFLICT",
                    "severity": "ERROR",
                    "message": "Payloads diferentes para a mesma chave e revisão no lote ou histórico publicado.",
                    "count": conflict_count,
                }
            )
            result.state = "BLOCKED"
            return
        for code, count in (
            ("EXACT_DUPLICATE", duplicate_count),
            ("STALE_REVISION", result.stats["stale"]),
        ):
            if count:
                result.issues.append(
                    {
                        "code": code,
                        "severity": "INFO",
                        "message": "Revisão antiga guardada; o estado atual não mudou.",
                        "count": count,
                    }
                )
        # Receita reconciliada não detecta uma venda contada em dois dias.
        candidate_history = eligible_history(previous, incoming)
        candidate_state = current_state(candidate_history)
        sale_key = ["source_system", "store_id", "sale_id"]
        split_sales = (
            candidate_state.filter(F.col("operation") == "UPSERT")
            .groupBy(*sale_key)
            .agg(F.countDistinct("business_date").alias("business_dates"))
            .filter(F.col("business_dates") > 1)
        )
        split_count = split_sales.count()
        if split_count:
            affected = incoming.join(split_sales.select(*sale_key), sale_key, "inner")
            affected_count = affected.count()
            result.stats["rejected"] += affected_count
            result.stats["valid"] -= affected_count
            result.stats["violations"] += affected_count
            affected.withColumn("errors", F.array(F.lit("SALE_DATE_CONFLICT"))).write.format(
                "delta"
            ).save(str(run_dir / "sale_date_conflicts"))
            result.issues.append(
                {
                    "code": "SALE_DATE_CONFLICT",
                    "severity": "ERROR",
                    "message": "Itens ativos da mesma origem/loja/venda têm dias comerciais diferentes. Corrija a venda integralmente.",
                    "count": split_count,
                }
            )
            result.state = "BLOCKED"
            return
    if validate_only:
        result.state = "VALIDATED"
        return
    if snapshot and prepared.batch_id in snapshot["accepted_batches"]:
        result.state = "NO_CHANGE"
        result.publication_id = snapshot["publication_id"]
        return

    table_dir = root / "tables"
    history_path = table_dir / "history"
    silver_path = table_dir / "silver"
    store_path = table_dir / "gold_store_day"
    product_path = table_dir / "gold_product_day"
    with stage(root, result, "silver"):
        history = candidate_history
        history.write.format("delta").mode("overwrite").save(str(history_path))
        history = spark.read.format("delta").load(str(history_path))
        silver = merge_state(spark, current_state(history), silver_path)
    with stage(root, result, "gold"):
        store, product = gold_tables(spark, silver)
        store.write.format("delta").mode("overwrite").save(str(store_path))
        inject_failure(fail_at, "after_gold")
        product.write.format("delta").mode("overwrite").save(str(product_path))
    with stage(root, result, "reconciliation"):
        # Valida as tabelas persistidas, não apenas DataFrames antes da gravação.
        reconcile(
            silver,
            spark.read.format("delta").load(str(store_path)),
            spark.read.format("delta").load(str(product_path)),
        )
    with stage(root, result, "publication"):
        publication_id = uuid.uuid4().hex
        candidate: Publication = {
            "publication_id": publication_id,
            "run_id": result.run_id,
            "published_at": datetime.now(UTC).isoformat(),
            "accepted_batches": [
                *(snapshot["accepted_batches"] if snapshot else []),
                prepared.batch_id,
            ],
            "tables": {
                name: table_reference(spark, path)
                for name, path in (
                    ("history", history_path),
                    ("silver", silver_path),
                    ("gold_store_day", store_path),
                    ("gold_product_day", product_path),
                    ("bronze", bronze_path),
                )
            },
            "sources": [
                *(snapshot["sources"] if snapshot else []),
                {
                    "batch_id": prepared.batch_id,
                    "run_id": result.run_id,
                    "bronze_path": str(bronze_path),
                    "bronze_version": 0,
                    "reference_hashes": prepared.reference_hashes,
                    "operator_reference_hash": references.digest,
                },
            ],
        }
        atomic_json(run_dir / "candidate.json", candidate)
        inject_failure(fail_at, "before_publish")
        publish(root, candidate)
        result.publication_id = publication_id
        result.state = "PUBLISHED"

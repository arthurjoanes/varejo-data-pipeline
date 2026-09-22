from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from retail_pipeline.report_model import CHART_LIMIT, PRODUCT_LIMIT, TABLE_LIMIT, ReportPayload
from retail_pipeline.report_view import build_report_html

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

    from retail_pipeline.publication import Publication


def _read_attempts(
    root: Path, snapshot: Mapping[str, object] | None = None
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    latest = None
    failed = None
    files = sorted(
        root.glob("runs/*/attempt.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for path in files:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Registro de tentativa inválido: {path}")
        if (
            snapshot
            and value.get("run_id") == snapshot.get("run_id")
            and value.get("state") != "PUBLISHED"
        ):
            value = {
                **value,
                "state": "PUBLISHED",
                "audit_incomplete": True,
                "publication_id": snapshot.get("publication_id"),
            }
        if latest is None:
            latest = value
        if value.get("state") in {"BLOCKED", "TECHNICAL_FAILURE"}:
            failed = value
        if latest is not None and failed is not None:
            break
    return latest, failed


def _limited_rows(frame: DataFrame, limit: int) -> tuple[list[dict[str, object]], bool]:
    rows = [row.asDict() for row in frame.limit(limit + 1).collect()]
    return rows[:limit], len(rows) > limit


def _read_published_tables(
    spark: SparkSession, root: Path, names: Sequence[str]
) -> tuple[Publication | None, dict[str, DataFrame]]:
    from retail_pipeline.publication import load_snapshot, read_table

    snapshot = load_snapshot(root)
    frames = {name: read_table(spark, snapshot, name) for name in names} if snapshot else {}
    return snapshot, frames


def generate_report(
    spark: SparkSession, root: Path, output: Path, *, synthetic_data: bool = False
) -> Path:
    from pyspark.sql import functions as F

    snapshot, frames = _read_published_tables(spark, root, ("gold_store_day", "gold_product_day"))
    latest, failed = _read_attempts(root, snapshot)
    if snapshot is None:
        payload = ReportPayload(
            synthetic_data=synthetic_data, latest_attempt=latest, last_failed_attempt=failed
        )
    else:
        store_frame = frames["gold_store_day"]
        product_frame = frames["gold_product_day"]
        summary = (
            store_frame.agg(
                F.count(F.lit(1)).alias("_store_day_rows"),
                F.sum("net_revenue_brl").alias("net_revenue_brl"),
                F.sum("units").alias("units"),
                F.sum("item_lines").alias("item_lines"),
                F.sum("sales_count").alias("sales_count"),
                F.min("business_date").alias("first_date"),
                F.max("business_date").alias("last_date"),
            )
            .limit(1)
            .collect()[0]
            .asDict()
        )
        # SUM over a confirmed empty publication returns null in Spark. These
        # additive totals are known zeros; an absent metric in a nonempty
        # publication must remain absent. Dates and the undefined ticket stay null.
        if summary.pop("_store_day_rows") == 0:
            summary.update(net_revenue_brl=Decimal("0.00"), units=0, item_lines=0, sales_count=0)
        sales = Decimal(str(summary.get("sales_count") or 0))
        summary["average_ticket_brl"] = (
            Decimal(str(summary.get("net_revenue_brl") or 0)) / sales if sales else None
        )
        daily, daily_truncated = _limited_rows(
            store_frame.groupBy("business_date")
            .agg(F.sum("net_revenue_brl").alias("net_revenue_brl"))
            .orderBy("business_date"),
            CHART_LIMIT,
        )
        stores, stores_truncated = _limited_rows(
            store_frame.orderBy("business_date", "store_id"), TABLE_LIMIT
        )
        products, products_truncated = _limited_rows(
            product_frame.groupBy("product_id")
            .agg(F.sum("units").alias("units"), F.sum("net_revenue_brl").alias("net_revenue_brl"))
            .orderBy(F.desc("units"), F.desc("net_revenue_brl"), "product_id"),
            PRODUCT_LIMIT,
        )
        payload = ReportPayload(
            synthetic_data=synthetic_data,
            snapshot=snapshot,
            latest_attempt=latest,
            last_failed_attempt=failed,
            summary=summary,
            daily=daily,
            stores=stores,
            products=products,
            daily_truncated=daily_truncated,
            stores_truncated=stores_truncated,
            products_truncated=products_truncated,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report_html(payload), encoding="utf-8")
    return output


def explain_indicator(
    spark: SparkSession,
    root: Path,
    store_id: str | None = None,
    business_date: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    """Amostra limitada de contribuições e revisões, com versões oficiais fixas."""
    from pyspark.sql import functions as F

    if not 1 <= limit <= 100:
        raise ValueError("O limite da amostra deve ficar entre 1 e 100.")
    if business_date is not None:
        date.fromisoformat(business_date)
    snapshot, frames = _read_published_tables(spark, root, ("silver", "history"))
    if snapshot is None:
        raise ValueError("Sem publicação para consultar.")
    current = frames["silver"].where(F.col("operation") == "UPSERT")
    if store_id is not None:
        current = current.where(F.col("store_id") == store_id)
    if business_date is not None:
        current = current.where(F.col("business_date") == F.lit(business_date).cast("date"))
    keys = ["source_system", "store_id", "sale_id", "line_id"]
    columns = keys + [
        "revision",
        "operation",
        "business_date",
        "product_id",
        "quantity",
        "line_net_brl",
        "batch_id",
        "run_id",
        "source_file",
        "source_line",
        "payload_hash",
    ]
    contributions, truncated = _limited_rows(current.select(*columns).orderBy(*keys), limit)
    totals = (
        current.agg(
            F.sum("line_net_brl").alias("net_revenue_brl"),
            F.sum("quantity").alias("units"),
            F.count("*").alias("item_lines"),
        )
        .limit(1)
        .collect()[0]
        .asDict()
    )
    sample_keys = current.select(*keys).orderBy(*keys).limit(limit)
    history = frames["history"].join(sample_keys, keys, "inner")
    revisions, history_truncated = _limited_rows(
        history.select(*columns).orderBy(*keys, "revision"), limit
    )
    return {
        "publication_id": snapshot["publication_id"],
        "publication_run_id": snapshot["run_id"],
        "published_at": snapshot["published_at"],
        "tables": snapshot["tables"],
        "sources": snapshot["sources"],
        "filter": {"store_id": store_id, "business_date": business_date},
        "totals": totals,
        "sample_limit": limit,
        "sample_truncated": truncated,
        "contributions": contributions,
        "revisions_of_sample_keys": revisions,
        "revisions_truncated": history_truncated,
        "note": "Contribuições ativas no recorte; revisões limitadas às chaves da amostra. CANCEL não contribui para receita. Valores monetários devem ser serializados como decimais.",
    }

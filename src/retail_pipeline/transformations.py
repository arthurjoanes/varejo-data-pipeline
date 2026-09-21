from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, IntegerType, StringType, StructField, StructType

from retail_pipeline.contracts import BUSINESS_FIELDS, KEY_FIELDS

REVISION_KEY = [*KEY_FIELDS, "revision"]


def bronze_schema() -> StructType:
    return StructType(
        [StructField(name, StringType(), True) for name in BUSINESS_FIELDS]
        + [
            StructField("batch_id", StringType(), False),
            StructField("run_id", StringType(), False),
            StructField("source_file", StringType(), False),
            StructField("source_line", IntegerType(), False),
            StructField("payload_hash", StringType(), True),
            StructField("raw_payload", StringType(), True),
            StructField("errors", ArrayType(StringType()), False),
        ]
    )


def type_events(bronze: DataFrame) -> DataFrame:
    result = bronze.filter(F.size("errors") == 0)
    for name in ("revision", "quantity"):
        result = result.withColumn(name, F.col(name).cast("int"))
    for name in ("unit_price_brl", "line_discount_brl"):
        result = result.withColumn(name, F.col(name).cast("decimal(18,2)"))
    for name in ("sold_at", "source_updated_at"):
        result = result.withColumn(name, F.to_timestamp(name))
    return result.withColumn(
        "business_date", F.to_date(F.from_utc_timestamp("sold_at", "America/Sao_Paulo"))
    ).withColumn(
        "line_net_brl",
        (F.col("quantity") * F.col("unit_price_brl") - F.col("line_discount_brl")).cast(
            "decimal(24,2)"
        ),
    )


def conflicting_keys(events: DataFrame) -> DataFrame:
    return (
        events.groupBy(*REVISION_KEY)
        .agg(F.countDistinct("payload_hash").alias("payloads"))
        .filter(F.col("payloads") > 1)
        .select(*REVISION_KEY)
    )


def eligible_history(previous: DataFrame | None, incoming: DataFrame) -> DataFrame:
    candidates = incoming.withColumn("_priority", F.lit(1))
    if previous is not None:
        candidates = previous.withColumn("_priority", F.lit(0)).unionByName(candidates)
    window = Window.partitionBy(*REVISION_KEY).orderBy(
        "_priority", "batch_id", "source_file", "source_line"
    )
    return (
        candidates.withColumn("_position", F.row_number().over(window))
        .filter(F.col("_position") == 1)
        .drop("_position", "_priority")
    )


def current_state(history: DataFrame) -> DataFrame:
    window = Window.partitionBy(*KEY_FIELDS).orderBy(F.col("revision").desc())
    return (
        history.withColumn("_position", F.row_number().over(window))
        .filter(F.col("_position") == 1)
        .drop("_position")
    )


def merge_state(spark: SparkSession, expected: DataFrame, path: Path) -> DataFrame:
    if not DeltaTable.isDeltaTable(spark, str(path)):
        expected.write.format("delta").save(str(path))
    else:
        condition = " AND ".join(f"target.{key} = source.{key}" for key in KEY_FIELDS)
        (
            DeltaTable.forPath(spark, str(path))
            .alias("target")
            .merge(expected.alias("source"), condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .whenNotMatchedBySourceDelete()
            .execute()
        )
    actual = spark.read.format("delta").load(str(path))
    # Verifica equivalência da projeção, inclusive após candidato anterior falhar.
    if expected.exceptAll(actual).limit(1).count() or actual.exceptAll(expected).limit(1).count():
        raise ValueError("Silver não corresponde à projeção do histórico elegível.")
    return actual


def gold_tables(spark: SparkSession, silver: DataFrame) -> tuple[DataFrame, DataFrame]:
    silver.createOrReplaceTempView("candidate_silver")
    store = spark.sql("""
        SELECT business_date, store_id,
               CAST(SUM(line_net_brl) AS DECIMAL(28,2)) AS net_revenue_brl,
               SUM(quantity) AS units, COUNT(*) AS item_lines,
               COUNT(DISTINCT struct(source_system, sale_id)) AS sales_count,
               CAST(SUM(line_net_brl) / COUNT(DISTINCT struct(source_system, sale_id))
                    AS DECIMAL(28,2)) AS average_ticket_brl
        FROM candidate_silver WHERE operation = 'UPSERT'
        GROUP BY business_date, store_id
    """)
    product = spark.sql("""
        SELECT business_date, product_id,
               CAST(SUM(line_net_brl) AS DECIMAL(28,2)) AS net_revenue_brl,
               SUM(quantity) AS units, COUNT(*) AS item_lines
        FROM candidate_silver WHERE operation = 'UPSERT'
        GROUP BY business_date, product_id
    """)
    return store, product


def totals(
    frame: DataFrame, revenue: str, units: str, count_rows: bool
) -> tuple[Decimal, int, int]:
    row = frame.agg(
        F.sum(revenue).alias("revenue"),
        F.sum(units).alias("units"),
        (F.count("*") if count_rows else F.sum("item_lines")).alias("lines"),
    ).first()
    if row is None:
        raise ValueError("Agregação não retornou a linha de totais.")
    return Decimal(row["revenue"] or 0), int(row["units"] or 0), int(row["lines"] or 0)


def reconcile(silver: DataFrame, store: DataFrame, product: DataFrame) -> None:
    active = silver.filter(F.col("operation") == "UPSERT")
    expected = totals(active, "line_net_brl", "quantity", True)
    if expected != totals(store, "net_revenue_brl", "units", False):
        raise ValueError("Reconciliação silver/gold por loja falhou.")
    if expected != totals(product, "net_revenue_brl", "units", False):
        raise ValueError("Reconciliação silver/gold por produto falhou.")

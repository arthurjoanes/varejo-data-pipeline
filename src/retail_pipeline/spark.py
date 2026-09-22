import os
from pathlib import Path

from pyspark.sql import SparkSession


def create_spark() -> SparkSession:
    """Usa apenas os jars instalados no build."""
    jar_dir = Path(os.environ.get("DELTA_JARS_DIR", "/opt/delta-jars"))
    jars = [jar_dir / f"{name}-4.4.0.jar" for name in ("delta-spark_4.2_2.13", "delta-storage")]
    missing = [str(path) for path in jars if not path.is_file()]
    if missing:
        raise RuntimeError(f"Jars Delta ausentes; execute o setup Docker: {', '.join(missing)}")
    temp_dir = Path(os.environ.get("SPARK_LOCAL_DIRS", "/data/tmp/spark"))
    temp_dir.mkdir(parents=True, exist_ok=True)
    spark = (
        SparkSession.builder.appName("Varejo Data Pipeline")
        .master("local[2]")
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "1g"))
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.jars", ",".join(map(str, jars)))
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
        .config("spark.sql.session.timeZone", "UTC")
        # O contrato usa calendário gregoriano; não converter para o calendário
        # híbrido de leitores legados ao persistir datas históricas válidas.
        .config("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED")
        .config("spark.sql.parquet.int96RebaseModeInWrite", "CORRECTED")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .config("spark.databricks.delta.snapshotPartitions", "2")
        .config("spark.sql.warehouse.dir", str(temp_dir / "warehouse"))
        .config("spark.local.dir", str(temp_dir))
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.ansi.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark

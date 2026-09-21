from pathlib import Path

import pytest
from delta.tables import DeltaTable
from pyspark.sql import SparkSession


@pytest.mark.integration
def test_real_delta_merge_and_time_travel(spark: SparkSession, tmp_path: Path) -> None:
    assert spark.version == "3.5.9"
    target = str(tmp_path / "smoke_delta")
    original = spark.createDataFrame([(1, 10), (2, 20)], "id long, amount long")
    original.write.format("delta").mode("overwrite").save(target)
    assert spark.read.format("delta").load(target).count() == 2

    changes = spark.createDataFrame([(1, 15), (3, 30)], "id long, amount long")
    (
        DeltaTable.forPath(spark, target)
        .alias("target")
        .merge(changes.alias("source"), "target.id = source.id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
    current = spark.read.format("delta").load(target).orderBy("id").collect()
    previous = (
        spark.read.format("delta").option("versionAsOf", 0).load(target).orderBy("id").collect()
    )
    assert [tuple(row) for row in current] == [(1, 15), (2, 20), (3, 30)]
    assert [tuple(row) for row in previous] == [(1, 10), (2, 20)]
    assert DeltaTable.forPath(spark, target).history(1).first()["version"] == 1

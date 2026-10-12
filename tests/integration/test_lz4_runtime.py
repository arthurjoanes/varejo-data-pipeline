"""Pinned security release retains the block-stream API used by Spark."""

import hashlib
import json
from pathlib import Path

import pytest
from pyspark.sql import SparkSession


@pytest.mark.integration
def test_lz4_block_stream_roundtrip_uses_pinned_release(spark: SparkSession) -> None:
    import pyspark

    lock = json.loads((Path(__file__).parents[2] / "runtime-jars.lock.json").read_text())
    replacement = next(
        item for item in lock["replacements"] if item["target"].startswith("lz4-java")
    )
    assert replacement["target"] == "lz4-java-1.11.4.jar"
    jars = Path(pyspark.__file__).parent / "jars"
    assert not (jars / "lz4-java-1.11.3.jar").exists()
    assert (
        hashlib.sha256((jars / replacement["target"]).read_bytes()).hexdigest()
        == replacement["sha256"]
    )
    jvm = spark.sparkContext._jvm
    output = jvm.java.io.ByteArrayOutputStream()
    compressor = jvm.net.jpountz.lz4.LZ4BlockOutputStream(output)
    payload = bytes(range(256)) * 257
    try:
        compressor.write(bytearray(payload))
    finally:
        compressor.close()
    compressed = bytearray(output.toByteArray())
    assert len(compressed) < len(payload)
    decompressor = jvm.net.jpountz.lz4.LZ4BlockInputStream(
        jvm.java.io.ByteArrayInputStream(compressed)
    )
    try:
        assert bytes(decompressor.readAllBytes()) == payload
    finally:
        decompressor.close()

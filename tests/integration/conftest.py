from collections.abc import Iterator
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from retail_pipeline.generation import default_catalog, default_schedule
from retail_pipeline.references import configure_references
from retail_pipeline.spark import create_spark


@pytest.fixture(autouse=True)
def operator_config(tmp_path: Path) -> None:
    # Cadastro aprovado antes de criar qualquer entrega; três origens registradas.
    schedule = default_schedule()
    schedule["windows"] = [
        default_schedule(source_system=source)["windows"][0]
        for source in ("synthetic-pos", "pos-a", "pos-b")
    ]
    configure_references(tmp_path / "state", default_catalog(), schedule)


@pytest.fixture(scope="session")
def spark() -> Iterator[SparkSession]:
    engine = create_spark()
    yield engine
    engine.stop()

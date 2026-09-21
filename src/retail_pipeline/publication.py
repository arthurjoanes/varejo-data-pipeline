from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession


class TableReference(TypedDict):
    path: str
    version: int


class SourceReference(TypedDict):
    batch_id: str
    run_id: str
    bronze_path: str
    bronze_version: int
    reference_hashes: NotRequired[dict[str, str | None]]
    operator_reference_hash: NotRequired[str]


class Publication(TypedDict):
    publication_id: str
    run_id: str
    published_at: str
    accepted_batches: list[str]
    tables: dict[str, TableReference]
    sources: list[SourceReference]


class WriterBusy(RuntimeError):
    pass


def json_scalar(value: object) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Tipo não serializável no contrato JSON: {type(value).__name__}")


@contextmanager
def writer_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "writer.lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WriterBusy("Outro processo está gravando neste volume.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=json_scalar
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_snapshot(root: Path) -> Publication | None:
    pointer = root / "publication.json"
    if not pointer.exists():
        return None
    with pointer.open(encoding="utf-8") as handle:
        return cast(Publication, json.load(handle))


def read_table(spark: SparkSession, snapshot: Publication, name: str) -> DataFrame:
    reference = snapshot["tables"][name]
    return (
        spark.read.format("delta")
        .option("versionAsOf", reference["version"])
        .load(reference["path"])
    )


def table_reference(spark: SparkSession, path: Path) -> TableReference:
    record = DeltaTable.forPath(spark, str(path)).history(1).first()
    if record is None:
        raise ValueError("Tabela Delta sem histórico de versão.")
    version = int(record["version"])
    return {"path": str(path), "version": version}


def publish(root: Path, snapshot: Publication) -> None:
    # O arquivo de auditoria é preparado antes do único ponto de visibilidade.
    atomic_json(root / "publications" / f"{snapshot['publication_id']}.json", snapshot)
    atomic_json(root / "publication.json", snapshot)

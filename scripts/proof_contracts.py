"""Contratos puros de cópia integral, retenção conservadora e observações limitadas."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import stat
import tarfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

MAX_FILES = 100_000
MAX_BYTES = 2 * 1024**3
MEASUREMENT_PLAN = {
    "schema_version": 1,
    "history_rows": [3600, 10800],
    "incoming_rows": 360,
    "batches_per_sample": 2,
    "repetitions": 3,
    "seed": 42,
    "sample_deadline_seconds": 600,
    "measurement_deadline_seconds": 1800,
    "cleanup_allowance_seconds": 60,
    "memory_bytes": 3 * 1024**3,
    "cpus": 2,
    "pids_limit": 1024,
    "cache_policy": "Caches do host não são limpos; as cópias e leituras anteriores podem aquecer o cache. Não é uma medição de I/O frio.",
    "scope": "Dois tamanhos sintéticos; três repetições não sustentam inferência geral ou capacidade comercial.",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def relative_name(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("Caminho relativo inválido.")
    return path.as_posix()


def no_link_ancestors(path: Path) -> None:
    """Recusa symlinks/junctions antes de acessar o conteúdo do caminho."""
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
        ):
            raise ValueError("Links e junctions não pertencem à cópia integral.")


def inventory(root: Path) -> dict[str, dict[str, object]]:
    no_link_ancestors(root)
    if not root.is_dir():
        raise ValueError("A origem deve ser um diretório regular existente.")
    result = {}
    total = 0
    entries = 0
    for parent, directories, files in os.walk(root, followlinks=False):
        # Valida antes que os.walk visite qualquer subdiretório, inclusive junctions Windows.
        directories.sort()
        for name in sorted(directories + files):
            entries += 1
            if entries > MAX_FILES:
                raise ValueError("Estado ultrapassa o limite de entradas da cópia.")
            path = Path(parent) / name
            no_link_ancestors(path)
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError("Links e arquivos especiais não pertencem à cópia.")
            if stat.S_ISDIR(info.st_mode):
                continue
            total += info.st_size
            if total > MAX_BYTES:
                raise ValueError("Estado ultrapassa o limite previamente fixado da cópia.")
            name = relative_name(path.relative_to(root).as_posix())
            result[name] = {"bytes": info.st_size, "sha256": digest(path)}
    return result


def inspect_archive(path: Path) -> dict[str, dict[str, object]]:
    result = {}
    total = 0
    with tarfile.open(path, "r:") as archive:
        for member in archive:
            name = relative_name(member.name)
            if name in result or not member.isfile():
                raise ValueError("Arquivo de cópia contém link, duplicata ou entrada especial.")
            total += member.size
            if len(result) >= MAX_FILES or total > MAX_BYTES:
                raise ValueError("Arquivo de cópia ultrapassa o limite fixado.")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Entrada sem conteúdo.")
            with source:
                checksum = hashlib.file_digest(source, "sha256").hexdigest()
            result[name] = {"bytes": member.size, "sha256": checksum}
    return result


def make_archive(root: Path, destination: Path, *, internal_root: str) -> dict:
    no_link_ancestors(destination)
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("Arquivo de cópia deve ficar fora da origem.")
    before = inventory(root)
    if not before:
        raise ValueError("Não arquivar estado vazio como prova funcional.")
    with destination.open("xb") as output, tarfile.open(fileobj=output, mode="w") as archive:
        for name in before:
            archive.add(root / name, arcname=name, recursive=False)
    if inspect_archive(destination) != before or inventory(root) != before:
        raise ValueError("Origem mudou durante a cópia; backup não aprovado.")
    return {
        "schema_version": 1,
        "internal_root": internal_root,
        "files": before,
        "archive_sha256": digest(destination),
        "archive_bytes": destination.stat().st_size,
    }


def restore_archive(archive_path: Path, root: Path, manifest: dict, *, internal_root: str) -> None:
    no_link_ancestors(root)
    no_link_ancestors(archive_path)
    if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
        raise ValueError("Destino deve estar ausente ou vazio; nada existente será substituído.")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("internal_root") != internal_root
        or not manifest.get("files")
        or archive_path.is_symlink()
        or digest(archive_path) != manifest.get("archive_sha256")
        or archive_path.stat().st_size != manifest.get("archive_bytes")
        or inspect_archive(archive_path) != manifest.get("files")
    ):
        raise ValueError("Cópia adulterada, incompleta ou com caminhos internos incompatíveis.")
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:") as archive:
        for member in archive:
            target = root / relative_name(member.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Entrada sem conteúdo.")
            with source, target.open("xb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
    if inventory(root) != manifest["files"]:
        raise ValueError("Inventário restaurado diverge da cópia verificada.")


def normalized_member(root: Path, value: str) -> Path:
    """resolve/commonpath recusam escapes inclusive por links em ancestrais."""
    no_link_ancestors(root)
    base = root.resolve(strict=True)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base / candidate
    no_link_ancestors(candidate)
    candidate = candidate.resolve(strict=True)
    try:
        contained = os.path.commonpath([base, candidate]) == str(base)
    except ValueError:
        contained = False
    if not contained:
        raise ValueError("Referência de publicação fora do estado autorizado.")
    return candidate


def retention_contract(root: Path) -> dict:
    pointer = normalized_member(root, "publication.json")
    current = json.loads(pointer.read_text(encoding="utf-8"))
    documents = sorted(normalized_member(root, "publications").glob("*.json"))
    publications = []
    protected = {"publication.json", "publications"}
    current_found = False
    for path in documents:
        path = normalized_member(root, str(path.resolve()))
        publication = json.loads(path.read_text(encoding="utf-8"))
        if path.stem != publication.get("publication_id"):
            raise ValueError("Identidade do manifesto não corresponde ao arquivo.")
        if publication["publication_id"] == current.get("publication_id"):
            if publication != current:
                raise ValueError("Ponteiro difere do manifesto imutável correspondente.")
            current_found = True
        required = {"history", "silver", "gold_store_day", "gold_product_day", "bronze"}
        if not required.issubset(publication.get("tables", {})) or not publication.get("sources"):
            raise ValueError("Manifesto incompleto: tabelas e fontes Bronze são obrigatórias.")
        accepted = publication.get("accepted_batches", [])
        if not accepted or set(accepted) != {
            source["batch_id"] for source in publication["sources"]
        }:
            raise ValueError("Batches aceitos não correspondem às fontes Bronze preservadas.")
        refs = []
        for name, reference in publication.get("tables", {}).items():
            refs.append(("table:" + name, reference["path"], reference["version"]))
        for source in publication.get("sources", []):
            refs.append(
                ("bronze:" + source["batch_id"], source["bronze_path"], source["bronze_version"])
            )
        if not refs:
            raise ValueError("Publicação não identifica tabelas/fontes a preservar.")
        preserved = []
        for kind, value, version in refs:
            if type(version) is not int or version < 0:
                raise ValueError("Versão Delta inválida.")
            table = normalized_member(root, value)
            if not table.is_dir():
                raise ValueError("Referência Delta não aponta para um diretório existente.")
            relative = table.relative_to(root.resolve()).as_posix()
            protected.add(relative)
            preserved.append({"kind": kind, "path": relative, "version": version})
        publications.append(
            {"publication_id": publication["publication_id"], "references": preserved}
        )
    if not current_found:
        raise ValueError("Publicação vigente não possui manifesto imutável.")
    return {
        "current_publication_id": current["publication_id"],
        "publications": publications,
        "protected_paths": sorted(protected),
        "scope": "Contrato conservador: preservar diretórios Delta completos, incluindo logs e arquivos de versões anteriores; não autoriza remoção individual ou VACUUM.",
    }


def reject_referenced_removal(root: Path, contract: dict, proposals: list[str]) -> None:
    protected = [normalized_member(root, path) for path in contract["protected_paths"]]
    for value in proposals:
        proposed = normalized_member(root, value)
        if any(
            proposed == item or proposed in item.parents or item in proposed.parents
            for item in protected
        ):
            raise ValueError("Proposta alcança publicação, versão Delta ou Bronze referenciada.")


def csv_oracle(paths: list[Path]) -> dict:
    """Oráculo para batches disjuntos desta medição; não usa transformações Spark."""
    totals: dict[tuple[str, str], dict] = {}
    keys = set()
    for folder in paths:
        for path in sorted(folder.glob("*.csv")):
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    identity = tuple(
                        row[key] for key in ("source_system", "store_id", "sale_id", "line_id")
                    )
                    if identity in keys or row["operation"] != "UPSERT" or row["revision"] != "1":
                        raise ValueError(
                            "Oráculo desta medição exige chaves disjuntas sem revisões."
                        )
                    keys.add(identity)
                    day = (
                        datetime.fromisoformat(row["sold_at"])
                        .astimezone(ZoneInfo("America/Sao_Paulo"))
                        .date()
                        .isoformat()
                    )
                    group = totals.setdefault(
                        (day, row["store_id"]),
                        {"cents": 0, "units": 0, "item_lines": 0, "sales": set()},
                    )
                    amount = int(row["quantity"]) * Decimal(row["unit_price_brl"]) - Decimal(
                        row["line_discount_brl"]
                    )
                    cents = amount * 100
                    if cents != cents.to_integral_value():
                        raise ValueError("Valor fora do contrato de centavos.")
                    group["cents"] += int(cents)
                    group["units"] += int(row["quantity"])
                    group["item_lines"] += 1
                    group["sales"].add((row["source_system"], row["sale_id"]))
    rows = [
        {
            "business_date": day,
            "store_id": store,
            "net_revenue_cents": value["cents"],
            "units": value["units"],
            "item_lines": value["item_lines"],
            "sales_count": len(value["sales"]),
        }
        for (day, store), value in sorted(totals.items())
    ]
    return {
        "rows": rows,
        "received_rows": len(keys),
        "net_revenue_cents": sum(row["net_revenue_cents"] for row in rows),
    }


def distribution(samples: list[dict]) -> dict:
    measured = sorted(
        float(sample["pipeline_seconds"]) for sample in samples if sample.get("status") == "passed"
    )
    if any(not math.isfinite(value) or value < 0 for value in measured):
        raise ValueError("Duração observada inválida.")
    return {
        "planned": len(samples),
        "completed": len(measured),
        "censored_or_failed": sum(sample.get("status") != "passed" for sample in samples),
        "completed_only_seconds": measured,
        "median_completed_only_seconds": (
            measured[(len(measured) - 1) // 2] + measured[len(measured) // 2]
        )
        / 2
        if measured
        else None,
        "p95": None,
        "interpretation": "Observações individuais e mediana apenas das concluídas; censura não foi descartada e três repetições não estimam uma distribuição geral.",
    }

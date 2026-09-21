"""Referências aprovadas pelo operador, fora da pasta entregue pelo remetente."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from retail_pipeline.batch_contracts import validate_references
from retail_pipeline.contracts import stable_json
from retail_pipeline.publication import atomic_json, writer_lock


@dataclass(frozen=True)
class ReferenceConfig:
    catalog: dict[str, object]
    schedule: dict[str, object]

    @property
    def document(self) -> dict[str, object]:
        return {"catalog": self.catalog, "schedule": self.schedule}

    @property
    def digest(self) -> str:
        return hashlib.sha256(stable_json(self.document).encode("utf-8")).hexdigest()


def _validated(document: object) -> ReferenceConfig:
    if not isinstance(document, dict):
        raise ValueError("Configuração do operador deve ser um objeto JSON.")
    catalog, schedule = document.get("catalog"), document.get("schedule")
    if not isinstance(catalog, dict) or not isinstance(schedule, dict):
        raise ValueError("Configuração exige catálogo e calendário como objetos JSON.")
    windows = schedule.get("windows")
    first = windows[0] if isinstance(windows, list) and windows else {}
    manifest = first if isinstance(first, dict) else {}
    issues: list[dict[str, object]] = []
    validate_references(catalog, schedule, manifest, issues)
    if issues:
        raise ValueError(f"Referências do operador inválidas: {[i['code'] for i in issues]}")
    return ReferenceConfig(catalog, schedule)


def configure_references(root: Path, catalog: object, schedule: object) -> ReferenceConfig:
    """Operação explícita e idempotente; um estado não troca de calendário em silêncio."""
    config = _validated({"catalog": catalog, "schedule": schedule})
    with writer_lock(root):
        existing = load_references(root)
        if existing is not None and existing.digest != config.digest:
            raise ValueError("Referências já fixadas neste estado. Use um novo --data-dir.")
        if existing is None:
            if (root / "publication.json").exists():
                raise ValueError(
                    "Publicação legada sem referências fixadas. Use um novo --data-dir."
                )
            atomic_json(root / "operator-references.json", config.document)
    return config


def load_references(root: Path) -> ReferenceConfig | None:
    path = root / "operator-references.json"
    if not path.exists():
        return None
    return _validated(json.loads(path.read_text(encoding="utf-8")))

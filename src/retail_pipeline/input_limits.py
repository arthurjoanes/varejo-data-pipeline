"""Orçamento por entrega; não substitui a retenção do volume de evidências."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class InputLimits:
    json_bytes: int = 1024 * 1024
    file_bytes: int = 64 * 1024 * 1024
    total_bytes: int = 256 * 1024 * 1024
    files: int = 1000

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"RETAIL_MAX_{field.name.upper()} deve ser inteiro positivo.")

    @classmethod
    def from_environment(cls) -> InputLimits:
        configured = {}
        for field in fields(cls):
            name = f"RETAIL_MAX_{field.name.upper()}"
            if name in os.environ:
                try:
                    configured[field.name] = int(os.environ[name])
                except ValueError as error:
                    raise ValueError(f"{name} deve ser inteiro positivo.") from error
        return cls(**configured)

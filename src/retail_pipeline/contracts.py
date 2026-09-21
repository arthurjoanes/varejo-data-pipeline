"""Contrato de eventos; validação pura, sem Spark ou acesso a arquivos."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

BUSINESS_FIELDS = (
    "source_system",
    "store_id",
    "sale_id",
    "line_id",
    "revision",
    "operation",
    "product_id",
    "sold_at",
    "quantity",
    "unit_price_brl",
    "line_discount_brl",
    "source_updated_at",
)
KEY_FIELDS = ("source_system", "store_id", "sale_id", "line_id")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
INTEGER = re.compile(r"[0-9]+\Z")
MONEY = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?\Z")
TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)
MAX_QUANTITY = 1_000_000
MAX_PRICE = Decimal("999999999.99")
MAX_DISCOUNT = Decimal("9999999999999999.99")
BUSINESS_ZONE = ZoneInfo("America/Sao_Paulo")


def stable_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def logical_hash(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def valid_identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def validate_row(
    raw: Mapping[str, object],
    *,
    source_system: str,
    store_id: str,
    stores: set[str],
    products: set[str],
) -> tuple[dict[str, str], list[str]]:
    """Canonicaliza apenas valores válidos; inválidos continuam diagnosticáveis."""
    row = {
        field: str(raw[field]) if raw.get(field) is not None else "" for field in BUSINESS_FIELDS
    }
    errors: list[str] = []
    for field in (*KEY_FIELDS, "product_id"):
        if not valid_identifier(row[field]):
            errors.append(f"INVALID_{field.upper()}")
    if row["source_system"] != source_system:
        errors.append("SOURCE_MISMATCH")
    if row["store_id"] != store_id:
        errors.append("FILE_STORE_MISMATCH")
    if row["store_id"] not in stores:
        errors.append("UNKNOWN_STORE")
    if row["product_id"] not in products:
        errors.append("UNKNOWN_PRODUCT")
    for field, maximum in (("revision", 2_147_483_647), ("quantity", MAX_QUANTITY)):
        value = row[field]
        if not INTEGER.fullmatch(value) or len(value) > 12 or not 1 <= int(value) <= maximum:
            errors.append(f"INVALID_{field.upper()}")
        else:
            row[field] = str(int(value))
    if row["operation"] not in ("UPSERT", "CANCEL"):
        errors.append("INVALID_OPERATION")
    decimals: dict[str, Decimal] = {}
    for field, money_maximum in (
        ("unit_price_brl", MAX_PRICE),
        ("line_discount_brl", MAX_DISCOUNT),
    ):
        value = row[field]
        try:
            amount = Decimal(value)
            if (
                not MONEY.fullmatch(value)
                or len(value) > 32
                or not amount.is_finite()
                or amount > money_maximum
            ):
                raise InvalidOperation
            decimals[field] = amount
            row[field] = format(amount, ".2f")
        except InvalidOperation:
            errors.append(f"INVALID_{field.upper()}")
    if len(decimals) == 2 and "INVALID_QUANTITY" not in errors:
        gross = decimals["unit_price_brl"] * int(row["quantity"])
        if decimals["line_discount_brl"] > gross:
            errors.append("DISCOUNT_EXCEEDS_GROSS")
    for field in ("sold_at", "source_updated_at"):
        value = row[field]
        try:
            if not TIMESTAMP.fullmatch(value):
                raise ValueError
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if field == "sold_at":
                # O dia comercial também precisa caber no intervalo de datas
                # que os leitores Python conseguem representar.
                stamp.astimezone(BUSINESS_ZONE).date()
            row[field] = stamp.astimezone(UTC).isoformat(timespec="microseconds")
        except (ValueError, OverflowError):
            errors.append(f"INVALID_{field.upper()}")
    return row, errors

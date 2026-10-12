"""Perfis locais imutáveis e comparação de recortes de Silver versionados.

Totais e numeradores monetários permanecem Decimal. Quantis são somente um resumo
aproximado de apresentação; as regras usam razões de agregações completas.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

    from retail_pipeline.publication import Publication

PROFILE_CONTRACT_VERSION = 1
CALCULATION_VERSION = "silver-profile-v1"
MAX_PROFILE_BYTES = 1_048_576
MONEY_PATTERN = re.compile(r"[0-9]+\.[0-9]{2}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
SALE_FIELDS = ("source_system", "store_id", "sale_id")
KEY_FIELDS = (*SALE_FIELDS, "line_id")


class ProfileReference(TypedDict):
    contract_version: int
    path: str
    sha256: str


class ProfileRead(TypedDict):
    status: str
    profile: dict[str, Any] | None
    reason: str | None


@dataclass(frozen=True)
class ProfileParameters:
    group_limit: int = 20
    date_display_limit: int = 31
    scope_limit: int = 1000
    max_json_bytes: int = 262_144
    quantile_probabilities: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
    quantile_accuracy: int = 10_000
    min_active_lines: int = 3
    quantity_mean_relative_threshold: str = "0.25"
    unit_price_mean_relative_threshold: str = "0.25"

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("group_limit", 1, 100),
            ("date_display_limit", 1, 366),
            ("scope_limit", 1, 1000),
            ("max_json_bytes", 1024, MAX_PROFILE_BYTES),
            ("quantile_accuracy", 1, 1_000_000),
            ("min_active_lines", 1, 1_000_000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"Parâmetro de perfil inválido: {name}.")
        probabilities = self.quantile_probabilities
        if (
            not 1 <= len(probabilities) <= 9
            or any(
                isinstance(p, bool) or not math.isfinite(p) or not 0 <= p <= 1
                for p in probabilities
            )
            or tuple(sorted(set(probabilities))) != tuple(probabilities)
        ):
            raise ValueError("Quantis exigem de 1 a 9 probabilidades únicas em ordem, entre 0 e 1.")
        for threshold in (
            self.quantity_mean_relative_threshold,
            self.unit_price_mean_relative_threshold,
        ):
            try:
                numeric = Decimal(threshold)
            except (InvalidOperation, TypeError) as exc:
                raise ValueError("Limiar demonstrativo inválido.") from exc
            if not numeric.is_finite() or not 0 <= numeric <= 100:
                raise ValueError("Limiar demonstrativo deve estar entre 0 e 100.")

    def document(self) -> dict[str, Any]:
        result = asdict(self)
        result["quantile_probabilities"] = list(self.quantile_probabilities)
        result.update(
            quantile_algorithm="pyspark.sql.functions.percentile_approx",
            max_quantiles=9,
            mean_decimal_places=6,
            mean_rounding="ROUND_HALF_EVEN",
            thresholds_are_demonstrative=True,
        )
        return result


DEFAULT_PARAMETERS = ProfileParameters()


def _decimal_text(value: Decimal, places: int = 6) -> str:
    with localcontext() as context:
        context.prec = 60
        return format(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN), "f")


def _ratio(numerator: object, denominator: object) -> Decimal | None:
    divisor = Decimal(str(denominator))
    if not divisor:
        return None
    with localcontext() as context:
        context.prec = 60
        return Decimal(str(numerator)) / divisor


def compare_metrics(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    parameters: ProfileParameters = DEFAULT_PARAMETERS,
) -> dict[str, Any]:
    """Avalia regras sem Spark; nenhuma WARNING altera o bloqueio da publicação."""
    previous_lines, current_lines = previous["active_lines"], current["active_lines"]
    if previous_lines == 0 and current_lines == 0:
        status, reason = "EMPTY", "As duas versões têm zero linhas ativas no recorte."
    elif previous_lines == 0 or current_lines == 0:
        status, reason = "NOT_COMPARABLE", "Uma das versões não tem linhas ativas no recorte."
    elif min(previous_lines, current_lines) < parameters.min_active_lines:
        status, reason = (
            "INSUFFICIENT_SAMPLE",
            "Amostra menor que o mínimo demonstrativo de linhas.",
        )
    else:
        status, reason = "COMPARABLE", "Métricas recalculadas nas mesmas datas e lojas."
    rules: list[dict[str, Any]] = []
    for metric, numerator, denominator, threshold in (
        (
            "quantity_mean",
            "units",
            "active_lines",
            parameters.quantity_mean_relative_threshold,
        ),
        (
            "unit_price_mean_brl",
            "gross_revenue_brl",
            "units",
            parameters.unit_price_mean_relative_threshold,
        ),
    ):
        before = _ratio(previous[numerator], previous[denominator])
        after = _ratio(current[numerator], current[denominator])
        with localcontext() as context:
            context.prec = 60
            difference = after - before if before is not None and after is not None else None
            relative = difference / abs(before) if difference is not None and before else None
        rule_status, rule_reason = status, reason
        severity = "INFO"
        if status == "COMPARABLE":
            if before == 0:
                rule_status, rule_reason = (
                    "ZERO_BASELINE",
                    "Valor anterior zero; variação relativa indefinida.",
                )
            elif relative is not None and abs(relative) > Decimal(threshold):
                rule_status, severity = "WARNING", "WARNING"
                rule_reason = "Variação excede o limiar demonstrativo configurado."
            else:
                rule_status, rule_reason = "STABLE", "Variação dentro do limiar demonstrativo."
        rules.append(
            {
                "metric": metric,
                "status": rule_status,
                "severity": severity,
                "previous": _decimal_text(before) if before is not None else None,
                "current": _decimal_text(after) if after is not None else None,
                "difference": _decimal_text(difference) if difference is not None else None,
                "relative_change": _decimal_text(relative) if relative is not None else None,
                "threshold": threshold,
                "reason": rule_reason,
                "previous_numerator": str(previous[numerator]),
                "current_numerator": str(current[numerator]),
                "previous_denominator": previous[denominator],
                "current_denominator": current[denominator],
            }
        )
    return {
        "status": status,
        "reason": reason,
        "rules": rules,
        "warnings": sum(rule["severity"] == "WARNING" for rule in rules),
    }


def _date_summary(dates: DataFrame, parameters: ProfileParameters) -> dict[str, Any]:
    from pyspark.sql import functions as F

    row = dates.agg(
        F.min("business_date").alias("start"),
        F.max("business_date").alias("end"),
        F.count("*").alias("date_count"),
    ).first()
    if row is None:
        raise ValueError("Agregação de datas do perfil não retornou resultado.")
    values = dates.orderBy("business_date").limit(parameters.date_display_limit).collect()
    return {
        "start": row["start"].isoformat() if row["start"] is not None else None,
        "end": row["end"].isoformat() if row["end"] is not None else None,
        "date_count": int(row["date_count"]),
        "dates": [value["business_date"].isoformat() for value in values],
        "dates_truncated": int(row["date_count"]) > parameters.date_display_limit,
    }


def _aggregate(
    active: DataFrame, parameters: ProfileParameters, *, distributions: bool = False
) -> dict[str, Any]:
    from pyspark.sql import functions as F

    expressions = [
        F.count("*").alias("active_lines"),
        F.countDistinct(F.struct(*SALE_FIELDS)).alias("sales"),
        F.sum("quantity").alias("units"),
        F.sum("line_net_brl").alias("net_revenue_brl"),
        F.sum(F.col("quantity") * F.col("unit_price_brl")).alias("gross_revenue_brl"),
        F.sum("line_discount_brl").alias("discount_brl"),
    ]
    columns = ("quantity", "unit_price_brl", "line_discount_brl")
    if distributions:
        for column in columns:
            expressions.extend(
                [
                    F.min(column).alias(f"{column}_min"),
                    F.max(column).alias(f"{column}_max"),
                    F.sum(column).alias(f"{column}_sum"),
                    F.percentile_approx(
                        column,
                        list(parameters.quantile_probabilities),
                        parameters.quantile_accuracy,
                    ).alias(f"{column}_quantiles"),
                ]
            )
    row = active.agg(*expressions).first()
    if row is None:
        raise ValueError("Agregação comercial do perfil não retornou resultado.")
    totals = {name: int(row[name] or 0) for name in ("active_lines", "sales", "units")}
    result: dict[str, Any] = {
        "totals": {
            **totals,
            **{
                name: _decimal_text(Decimal(row[name] or 0), 2)
                for name in ("net_revenue_brl", "gross_revenue_brl", "discount_brl")
            },
        }
    }
    if distributions:
        result["distributions"] = {}
        for column in columns:
            mean = _ratio(row[f"{column}_sum"] or 0, totals["active_lines"])
            result["distributions"][column] = {
                "min": str(row[f"{column}_min"]) if row[f"{column}_min"] is not None else None,
                "max": str(row[f"{column}_max"]) if row[f"{column}_max"] is not None else None,
                "mean": _decimal_text(mean) if mean is not None else None,
                "quantiles": [
                    {"probability": probability, "value": str(value)}
                    for probability, value in zip(
                        parameters.quantile_probabilities,
                        row[f"{column}_quantiles"] or [],
                        strict=False,
                    )
                ],
            }
    return result


def _groups(active: DataFrame, key: str, parameters: ProfileParameters) -> dict[str, Any]:
    from pyspark.sql import functions as F

    grouped = active.groupBy(key).agg(
        F.count("*").alias("active_lines"),
        F.countDistinct(F.struct(*SALE_FIELDS)).alias("sales"),
        F.sum("quantity").alias("units"),
        F.sum("line_net_brl").alias("net_revenue_brl"),
    )
    count = grouped.count()
    rows = (
        grouped.orderBy(F.col("net_revenue_brl").desc(), key)
        .limit(parameters.group_limit)
        .collect()
    )
    return {
        "values": [
            {
                key: row[key],
                "active_lines": int(row["active_lines"]),
                "sales": int(row["sales"]),
                "units": int(row["units"]),
                "net_revenue_brl": _decimal_text(row["net_revenue_brl"], 2),
            }
            for row in rows
        ],
        "group_count": count,
        "truncated": count > parameters.group_limit,
    }


def _state_changes(current: DataFrame, previous: DataFrame | None) -> dict[str, Any]:
    from pyspark.sql import functions as F

    if previous is None:
        count = current.count()
        return {
            "origin": "initial_silver_state",
            "new_keys": count,
            "revised_keys": 0,
            "cancelled_keys": 0,
            "reactivated_keys": 0,
            "effective_changes": count,
        }
    joined = current.alias("current").join(previous.alias("previous"), list(KEY_FIELDS), "left")
    is_new = F.col("previous.revision").isNull()
    changed = is_new | (F.col("current.payload_hash") != F.col("previous.payload_hash"))
    row = joined.agg(
        F.count(F.when(is_new, 1)).alias("new_keys"),
        F.count(F.when(F.col("current.revision") > F.col("previous.revision"), 1)).alias(
            "revised_keys"
        ),
        F.count(
            F.when(
                (F.col("current.operation") == "CANCEL")
                & (F.col("previous.operation") == "UPSERT"),
                1,
            )
        ).alias("cancelled_keys"),
        F.count(
            F.when(
                (F.col("current.operation") == "UPSERT")
                & (F.col("previous.operation") == "CANCEL"),
                1,
            )
        ).alias("reactivated_keys"),
        F.count(F.when(changed, 1)).alias("effective_changes"),
    ).first()
    if row is None:
        raise ValueError("Agregação de mudanças do estado não retornou resultado.")
    return {"origin": "compared_silver_versions", **row.asDict()}


def _received_operations(spark: SparkSession, candidate: Publication) -> dict[str, int] | None:
    from pyspark.sql import functions as F

    from retail_pipeline.publication import read_table

    if "bronze" not in candidate["tables"]:
        return None
    received = read_table(spark, candidate, "bronze").filter(F.size("errors") == 0)
    row = received.agg(
        F.count(F.when(F.col("operation") == "CANCEL", 1)).alias("valid_cancel_events"),
        F.count(F.when(F.col("revision").cast("long") > 1, 1)).alias("valid_revision_gt1_events"),
    ).first()
    if row is None:
        raise ValueError("Agregação das operações recebidas não retornou resultado.")
    return {name: int(value) for name, value in row.asDict().items()}


def _catalog_context(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    before, after = previous["reference_hashes"], current["reference_hashes"]
    approved = bool(before.get("operator_catalog_hash") and after.get("operator_catalog_hash"))
    key = "operator_catalog_hash" if approved else "catalog.json"
    known = before.get(key) is not None and after.get(key) is not None
    return {
        "catalog_changed": before.get(key) != after.get(key) if known else None,
        "catalog_reference_origin": "approved_operator_catalog"
        if approved
        else "received_catalog_bytes",
        "catalog_identity_available": known,
    }


def _comparison(
    spark: SparkSession,
    current_frame: DataFrame,
    previous_frame: DataFrame | None,
    current_profile: dict[str, Any],
    previous: Publication | None,
    parameters: ProfileParameters,
) -> dict[str, Any]:
    from pyspark.sql import functions as F

    result: dict[str, Any] = {
        "baseline_publication_id": previous["publication_id"] if previous else None,
        "baseline_delta_versions": previous["tables"] if previous else None,
        "status": "NO_BASELINE",
        "reason": "Primeira publicação; não existe publicação anterior.",
        "context": {"current_date_range": current_profile["date_range"]},
        "scope": None,
        "original_totals": {"previous": None, "current": current_profile["active_state"]["totals"]},
        "equivalent_totals": None,
        "rules": [],
        "warnings": 0,
    }
    if previous is None or previous_frame is None:
        return result
    baseline = load_profile(previous)
    before = baseline["profile"]
    if before is None:
        result.update(
            status="BASELINE_PROFILE_UNAVAILABLE",
            reason=f"Perfil da publicação anterior: {baseline['status']}. {baseline['reason']}",
        )
        return result
    current_stores = set(current_profile["coverage"]["received"])
    previous_stores = set(before["coverage"]["received"])
    stores = sorted(current_stores & previous_stores)
    previous_dates = previous_frame.select("business_date").distinct()
    current_dates = current_frame.select("business_date").distinct()
    common_dates = current_dates.join(previous_dates, ["business_date"], "inner")
    date_scope = _date_summary(common_dates, parameters)
    dates_changed = bool(
        current_dates.join(previous_dates, ["business_date"], "left_anti").limit(1).count()
        or previous_dates.join(current_dates, ["business_date"], "left_anti").limit(1).count()
    )
    result["context"] = {
        "dates_changed": dates_changed,
        "previous_date_range": before["date_range"],
        "current_date_range": current_profile["date_range"],
        "previous_stores": sorted(previous_stores),
        "current_stores": sorted(current_stores),
        "stores_added": sorted(current_stores - previous_stores),
        "stores_removed": sorted(previous_stores - current_stores),
        **_catalog_context(before, current_profile),
        "previous_reference_hashes": before["reference_hashes"],
        "current_reference_hashes": current_profile["reference_hashes"],
        "previous_scope_complete": before["coverage"].get("scope_complete", False),
        "current_scope_complete": current_profile["coverage"]["scope_complete"],
    }
    result["scope"] = {
        "dates": date_scope,
        "stores": stores,
        "definition": "intersection_of_silver_business_dates_and_confirmed_coverage_stores",
        "date_intersection_complete": True,
        "silver_versions": {
            "previous": previous["tables"]["silver"],
            "current": current_profile["delta_versions"]["silver"],
        },
    }
    result["original_totals"]["previous"] = before["active_state"]["totals"]
    if not stores or not date_scope["date_count"]:
        both_empty = (
            before["active_state"]["totals"]["active_lines"] == 0
            and current_profile["active_state"]["totals"]["active_lines"] == 0
        )
        result.update(
            status="EMPTY" if both_empty else "NOT_COMPARABLE",
            reason="As duas publicações são vazias." if both_empty else "Sem datas/lojas em comum.",
        )
        return result
    # Top-K e a lista truncada de datas nunca fundamentam este recorte.
    equivalent = {}
    for name, frame in (("previous", previous_frame), ("current", current_frame)):
        recut = frame.join(common_dates, ["business_date"], "left_semi").filter(
            F.col("store_id").isin(stores) & (F.col("operation") == "UPSERT")
        )
        equivalent[name] = _aggregate(recut, parameters)["totals"]
    result["equivalent_totals"] = equivalent
    result.update(compare_metrics(equivalent["previous"], equivalent["current"], parameters))
    return result


def build_profile(
    spark: SparkSession,
    candidate: Publication,
    previous: Publication | None,
    *,
    batch_stats: Mapping[str, int],
    coverage: Mapping[str, Sequence[str]],
    reference_hashes: Mapping[str, str | None],
    parameters: ProfileParameters = DEFAULT_PARAMETERS,
) -> dict[str, Any]:
    """Lê somente versões Delta fixadas; deve ocorrer antes do commit do manifesto."""
    from pyspark.sql import functions as F

    from retail_pipeline.publication import read_table

    batch_coverage = {
        name: sorted(set(coverage.get(name, ())))
        for name in ("expected", "received", "missing", "zero_movement")
    }
    previous_profile = load_profile(previous)["profile"] if previous else None
    covered: dict[str, Any] = dict(batch_coverage)
    if previous_profile is not None:
        for name in ("expected", "received"):
            covered[name] = sorted(set(covered[name]) | set(previous_profile["coverage"][name]))
    covered["scope_complete"] = previous is None or (
        previous_profile is not None and previous_profile["coverage"].get("scope_complete") is True
    )
    covered["origin"] = "cumulative_confirmed_stores_with_latest_batch_zero_movement"
    if any(
        len(covered[name]) > parameters.scope_limit
        for name in ("expected", "received", "missing", "zero_movement")
    ):
        raise ValueError("Cobertura excede o limite de cardinalidade do perfil.")
    current = read_table(spark, candidate, "silver")
    previous_frame = read_table(spark, previous, "silver") if previous else None
    active = current.filter(F.col("operation") == "UPSERT")
    commercial = _aggregate(active, parameters, distributions=True)
    commercial["groups"] = {
        "stores": _groups(active, "store_id", parameters),
        "products": _groups(active, "product_id", parameters),
    }
    commercial["cancelled_keys"] = current.filter(F.col("operation") == "CANCEL").count()
    profile: dict[str, Any] = {
        "contract_version": PROFILE_CONTRACT_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "publication_id": candidate["publication_id"],
        "run_id": candidate["run_id"],
        "delta_versions": candidate["tables"],
        "parameters": parameters.document(),
        "coverage": covered,
        "reference_hashes": dict(reference_hashes),
        "date_range": _date_summary(current.select("business_date").distinct(), parameters),
        "batch": {
            "stats": dict(batch_stats),
            "coverage": batch_coverage,
            "received_operations": _received_operations(spark, candidate),
            "received_operations_include_duplicates_and_stale": True,
        },
        "active_state": commercial,
        "state_changes": _state_changes(current, previous_frame),
    }
    profile["comparison"] = _comparison(
        spark, current, previous_frame, profile, previous, parameters
    )
    validate_profile(profile)
    _profile_bytes(profile)
    return profile


def _integer(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"Perfil inválido: {label} exige inteiro não negativo.")


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Perfil inválido: {label} exige objeto.")
    return value


def _totals_contract(value: object) -> None:
    totals = _mapping(value, "totals")
    for name in ("active_lines", "sales", "units"):
        _integer(totals.get(name), name)
    if totals["sales"] > totals["active_lines"] or totals["units"] < totals["active_lines"]:
        raise ValueError("Perfil inválido: unidades/vendas incompatíveis com linhas ativas.")
    for name in ("net_revenue_brl", "gross_revenue_brl", "discount_brl"):
        amount = totals.get(name)
        if not isinstance(amount, str) or not MONEY_PATTERN.fullmatch(amount):
            raise ValueError(f"Perfil inválido: {name} exige Decimal exato como texto com 2 casas.")
    with localcontext() as context:
        context.prec = 60
        if Decimal(totals["gross_revenue_brl"]) - Decimal(totals["discount_brl"]) != Decimal(
            totals["net_revenue_brl"]
        ):
            raise ValueError("Perfil inválido: bruto - desconto difere do líquido.")
    if totals["active_lines"] == 0 and any(
        Decimal(str(totals[name]))
        for name in ("sales", "units", "net_revenue_brl", "gross_revenue_brl", "discount_brl")
    ):
        raise ValueError("Perfil vazio exige totais zero.")


def _date_contract(value: object, limit: int) -> None:
    interval = _mapping(value, "date_range")
    _integer(interval.get("date_count"), "date_count")
    dates = interval.get("dates")
    if (
        not isinstance(dates, list)
        or any(not isinstance(item, str) for item in dates)
        or len(dates) > limit
        or dates != sorted(set(dates))
        or len(dates) > interval["date_count"]
    ):
        raise ValueError("Perfil inválido: lista de datas excede limite ou não é única/ordenada.")
    for item in [interval.get("start"), interval.get("end"), *dates]:
        if item is not None:
            if not isinstance(item, str) or date.fromisoformat(item).isoformat() != item:
                raise ValueError("Perfil inválido: data deve ser ISO-8601.")
    if type(interval.get("dates_truncated")) is not bool or interval["dates_truncated"] != (
        interval["date_count"] > len(dates)
    ):
        raise ValueError("Perfil inválido: truncamento de datas incoerente.")
    if interval["date_count"] == 0:
        if interval.get("start") is not None or interval.get("end") is not None or dates:
            raise ValueError("Perfil sem datas exige intervalo ausente.")
    elif (
        not interval.get("start")
        or not interval.get("end")
        or interval["start"] > interval["end"]
        or not dates
        or dates[0] != interval["start"]
        or dates[-1] > interval["end"]
    ):
        raise ValueError("Perfil inválido: intervalo de datas incoerente.")


def _table_references_contract(value: object) -> None:
    tables = _mapping(value, "delta_versions")
    if "silver" not in tables:
        raise ValueError("Perfil exige versão Silver.")
    for reference in tables.values():
        table = _mapping(reference, "delta_reference")
        if not isinstance(table.get("path"), str) or not table["path"]:
            raise ValueError("Perfil exige caminho de tabela.")
        _integer(table.get("version"), "version")


def validate_profile(value: object) -> dict[str, Any]:
    """Validação local da versão 1, incluindo limites de saída e números exatos."""
    profile = _mapping(value, "profile")
    if (
        type(profile.get("contract_version")) is not int
        or profile["contract_version"] != PROFILE_CONTRACT_VERSION
    ):
        raise ValueError("Versão de contrato de perfil não suportada.")
    if profile.get("calculation_version") != CALCULATION_VERSION:
        raise ValueError("Versão de cálculo de perfil não suportada.")
    for name in ("publication_id", "run_id"):
        identity = profile.get(name)
        if not isinstance(identity, str) or not ID_PATTERN.fullmatch(identity):
            raise ValueError(f"Perfil inválido: {name}.")
    params = _mapping(profile.get("parameters"), "parameters")
    arguments = {
        name: params[name] for name in ProfileParameters.__dataclass_fields__ if name in params
    }
    if "quantile_probabilities" in arguments:
        arguments["quantile_probabilities"] = tuple(arguments["quantile_probabilities"])
    expected_params = ProfileParameters(**arguments).document()
    if params != expected_params:
        raise ValueError("Perfil inválido: parâmetros/algoritmo incompletos ou desconhecidos.")
    _table_references_contract(profile.get("delta_versions"))
    coverage = _mapping(profile.get("coverage"), "coverage")
    if type(coverage.get("scope_complete")) is not bool or coverage.get("origin") != (
        "cumulative_confirmed_stores_with_latest_batch_zero_movement"
    ):
        raise ValueError("Perfil inválido: origem/completude da cobertura.")
    for name in ("expected", "received", "missing", "zero_movement"):
        stores = coverage.get(name)
        if (
            not isinstance(stores, list)
            or any(
                not isinstance(store, str) or not ID_PATTERN.fullmatch(store) for store in stores
            )
            or stores != sorted(set(stores))
            or len(stores) > params["scope_limit"]
        ):
            raise ValueError("Perfil inválido: cobertura não ordenada ou fora do limite.")
    references = _mapping(profile.get("reference_hashes"), "reference_hashes")
    if any(
        value is not None and not HASH_PATTERN.fullmatch(str(value))
        for value in references.values()
    ):
        raise ValueError("Perfil inválido: hash de referência.")
    _date_contract(profile.get("date_range"), params["date_display_limit"])
    batch = _mapping(profile.get("batch"), "batch")
    batch_coverage = _mapping(batch.get("coverage"), "batch.coverage")
    for name in ("expected", "received", "missing", "zero_movement"):
        stores = batch_coverage.get(name)
        if (
            not isinstance(stores, list)
            or any(
                not isinstance(store, str) or not ID_PATTERN.fullmatch(store) for store in stores
            )
            or stores != sorted(set(stores))
            or len(stores) > params["scope_limit"]
        ):
            raise ValueError("Perfil inválido: cobertura do lote fora do contrato.")
    for number in _mapping(batch.get("stats"), "batch.stats").values():
        _integer(number, "batch.stats")
    operations = batch.get("received_operations")
    if operations is not None:
        for number in _mapping(operations, "received_operations").values():
            _integer(number, "received_operations")
    active = _mapping(profile.get("active_state"), "active_state")
    _totals_contract(active.get("totals"))
    _integer(active.get("cancelled_keys"), "cancelled_keys")
    distributions = _mapping(active.get("distributions"), "distributions")
    for name in ("quantity", "unit_price_brl", "line_discount_brl"):
        distribution = _mapping(distributions.get(name), "distribution")
        quantiles = distribution.get("quantiles")
        if not isinstance(quantiles, list) or len(quantiles) > params["max_quantiles"]:
            raise ValueError("Perfil inválido: quantis fora do limite.")
        for number in (distribution.get("min"), distribution.get("max"), distribution.get("mean")):
            if number is not None and (
                not isinstance(number, str)
                or not Decimal(number).is_finite()
                or Decimal(number) < 0
            ):
                raise ValueError("Perfil inválido: distribuição exige Decimal não negativo.")
        for quantile in quantiles:
            quantile = _mapping(quantile, "quantile")
            if quantile.get("probability") not in params["quantile_probabilities"]:
                raise ValueError("Perfil inválido: probabilidade do quantil desconhecida.")
            if (
                not isinstance(quantile.get("value"), str)
                or not Decimal(quantile["value"]).is_finite()
            ):
                raise ValueError("Perfil inválido: valor do quantil.")
    groups = _mapping(active.get("groups"), "groups")
    for name, key in (("stores", "store_id"), ("products", "product_id")):
        group = _mapping(groups.get(name), "groups")
        values = group.get("values")
        if not isinstance(values, list) or len(values) > params["group_limit"]:
            raise ValueError("Perfil inválido: grupos fora do limite.")
        _integer(group.get("group_count"), "group_count")
        if (
            len(values) > group["group_count"]
            or type(group.get("truncated")) is not bool
            or group.get("truncated") != (group["group_count"] > len(values))
        ):
            raise ValueError("Perfil inválido: truncamento de grupos incoerente.")
        for item in values:
            entry = _mapping(item, "group")
            if not isinstance(entry.get(key), str) or not ID_PATTERN.fullmatch(entry[key]):
                raise ValueError("Perfil inválido: identificador do grupo.")
            for field in ("active_lines", "sales", "units"):
                _integer(entry.get(field), field)
            if not isinstance(entry.get("net_revenue_brl"), str) or not MONEY_PATTERN.fullmatch(
                entry["net_revenue_brl"]
            ):
                raise ValueError("Perfil inválido: receita do grupo.")
    changes = _mapping(profile.get("state_changes"), "state_changes")
    if changes.get("origin") not in {"initial_silver_state", "compared_silver_versions"}:
        raise ValueError("Perfil inválido: origem das mudanças.")
    for name in (
        "new_keys",
        "revised_keys",
        "cancelled_keys",
        "reactivated_keys",
        "effective_changes",
    ):
        _integer(changes.get(name), name)
    comparison = _mapping(profile.get("comparison"), "comparison")
    if comparison.get("status") not in {
        "NO_BASELINE",
        "BASELINE_PROFILE_UNAVAILABLE",
        "NOT_COMPARABLE",
        "EMPTY",
        "INSUFFICIENT_SAMPLE",
        "COMPARABLE",
    }:
        raise ValueError("Perfil inválido: estado da comparação.")
    baseline_tables = comparison.get("baseline_delta_versions")
    if baseline_tables is not None:
        _table_references_contract(baseline_tables)
    context = _mapping(comparison.get("context"), "context")
    _date_contract(context.get("current_date_range"), params["date_display_limit"])
    if context["current_date_range"] != profile["date_range"]:
        raise ValueError("Perfil inválido: período atual da comparação difere do perfil.")
    if "previous_date_range" in context:
        # A baseline pode ter sido produzida com outro limite de apresentação.
        _date_contract(context["previous_date_range"], 366)
    for field in ("previous_stores", "current_stores", "stores_added", "stores_removed"):
        if field in context:
            stores = context[field]
            if (
                not isinstance(stores, list)
                or any(
                    not isinstance(store, str) or not ID_PATTERN.fullmatch(store)
                    for store in stores
                )
                or stores != sorted(set(stores))
                or len(stores) > params["scope_limit"]
            ):
                raise ValueError("Perfil inválido: lojas do contexto fora do contrato.")
    rules = comparison.get("rules")
    if not isinstance(rules, list) or len(rules) > 2:
        raise ValueError("Perfil inválido: regras fora do contrato.")
    for rule in rules:
        rule = _mapping(rule, "rule")
        if rule.get("metric") not in {"quantity_mean", "unit_price_mean_brl"}:
            raise ValueError("Perfil inválido: métrica da regra desconhecida.")
        if rule.get("status") not in {
            "STABLE",
            "WARNING",
            "ZERO_BASELINE",
            "NOT_COMPARABLE",
            "EMPTY",
            "INSUFFICIENT_SAMPLE",
        }:
            raise ValueError("Perfil inválido: estado da regra desconhecido.")
        if rule.get("severity") not in {"INFO", "WARNING"}:
            raise ValueError("Alertas de perfil só admitem INFO ou WARNING.")
        for name in ("previous", "current", "difference", "relative_change", "threshold"):
            number = rule.get(name)
            if number is not None and (
                not isinstance(number, str) or not Decimal(number).is_finite()
            ):
                raise ValueError("Perfil inválido: valor da regra exige Decimal finito como texto.")
    _integer(comparison.get("warnings"), "warnings")
    if comparison["warnings"] != sum(rule["severity"] == "WARNING" for rule in rules):
        raise ValueError("Perfil inválido: contagem de alertas difere das regras.")
    original = _mapping(comparison.get("original_totals"), "original_totals")
    _totals_contract(original.get("current"))
    if original["current"] != active["totals"]:
        raise ValueError("Perfil inválido: total original atual difere do estado ativo.")
    if original.get("previous") is not None:
        _totals_contract(original["previous"])
    equivalent = comparison.get("equivalent_totals")
    if equivalent is not None:
        equivalent = _mapping(equivalent, "equivalent_totals")
        _totals_contract(equivalent.get("previous"))
        _totals_contract(equivalent.get("current"))
        evaluated = compare_metrics(
            equivalent["previous"], equivalent["current"], ProfileParameters(**arguments)
        )
        if any(comparison.get(name) != evaluated[name] for name in evaluated):
            raise ValueError("Perfil inválido: regras divergem dos totais equivalentes/parâmetros.")
    elif comparison["status"] in {"COMPARABLE", "INSUFFICIENT_SAMPLE"}:
        raise ValueError("Comparação avaliável exige totais equivalentes.")
    scope = comparison.get("scope")
    if scope is not None:
        scope = _mapping(scope, "scope")
        _date_contract(scope.get("dates"), params["date_display_limit"])
        stores = scope.get("stores")
        if (
            not isinstance(stores, list)
            or any(
                not isinstance(store, str) or not ID_PATTERN.fullmatch(store) for store in stores
            )
            or stores != sorted(set(stores))
            or len(stores) > params["scope_limit"]
        ):
            raise ValueError("Perfil inválido: lojas do recorte fora do contrato.")
        if not set(stores).issubset(coverage["received"]):
            raise ValueError("Recorte exige lojas com cobertura confirmada.")
        scope_versions = _mapping(scope.get("silver_versions"), "silver_versions")
        for reference in scope_versions.values():
            _table_references_contract({"silver": reference})
    elif equivalent is not None:
        raise ValueError("Comparação com métricas exige recorte explícito.")
    return profile


def _profile_bytes(profile: dict[str, Any]) -> bytes:
    payload = (
        json.dumps(profile, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    if len(payload) > profile["parameters"]["max_json_bytes"]:
        raise ValueError("Perfil excede o limite configurado de bytes JSON.")
    return payload


def persist_profile(root: Path, profile: dict[str, Any]) -> ProfileReference:
    """Prepara arquivo imutável; requer o lock do escritor antes de trocar o manifesto."""
    validate_profile(profile)
    payload = _profile_bytes(profile)
    path = root.resolve() / "profiles" / f"{profile['publication_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != payload:
            raise ValueError("Perfil já existente não pode ser substituído por bytes diferentes.")
    else:
        descriptor, temporary = tempfile.mkstemp(prefix=".pending-profile-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            if hasattr(os, "O_DIRECTORY"):
                directory = os.open(path.parent, os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {
        "contract_version": PROFILE_CONTRACT_VERSION,
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("Perfil contém chave JSON duplicada.")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Constante JSON não finita: {value}.")


def load_profile(snapshot: Mapping[str, Any] | None) -> ProfileRead:
    """Reader sem Spark, compatível com publicação legada e explícito sobre corrupção."""
    if snapshot is None:
        return {
            "status": "NO_PUBLICATION",
            "profile": None,
            "reason": "Nenhuma publicação disponível.",
        }
    if "profile" not in snapshot:
        return {
            "status": "LEGACY",
            "profile": None,
            "reason": "Snapshot anterior ao contrato de perfil.",
        }
    try:
        reference = _mapping(snapshot["profile"], "profile_reference")
        if (
            type(reference.get("contract_version")) is not int
            or reference["contract_version"] != PROFILE_CONTRACT_VERSION
        ):
            raise ValueError("Versão de referência de perfil não suportada.")
        checksum = reference.get("sha256")
        if not isinstance(checksum, str) or not HASH_PATTERN.fullmatch(checksum):
            raise ValueError("SHA-256 do perfil inválido.")
        filename = reference.get("path")
        if not isinstance(filename, str) or not filename:
            raise ValueError("Caminho de perfil inválido.")
        path = Path(filename)
        if not path.is_absolute() or path.is_symlink():
            raise ValueError("Perfil exige arquivo absoluto regular sem symlink.")
        if not path.exists():
            return {
                "status": "MISSING",
                "profile": None,
                "reason": "Arquivo de perfil referenciado ausente.",
            }
        if not path.is_file() or path.stat().st_size > MAX_PROFILE_BYTES:
            raise ValueError("Arquivo de perfil inválido ou fora do limite máximo de bytes.")
        with path.open("rb") as handle:
            payload = handle.read(MAX_PROFILE_BYTES + 1)
        if len(payload) > MAX_PROFILE_BYTES or hashlib.sha256(payload).hexdigest() != checksum:
            raise ValueError("SHA-256 do perfil não corresponde ao manifesto.")
        profile = validate_profile(
            json.loads(
                payload, object_pairs_hook=_json_object, parse_constant=_reject_json_constant
            )
        )
        if len(payload) > profile["parameters"]["max_json_bytes"]:
            raise ValueError("Perfil excede o limite declarado de bytes.")
        if (
            profile["publication_id"] != snapshot.get("publication_id")
            or profile["run_id"] != snapshot.get("run_id")
            or profile["delta_versions"] != snapshot.get("tables")
        ):
            raise ValueError("Identidade/versões do perfil divergem do snapshot.")
        return {"status": "AVAILABLE", "profile": profile, "reason": None}
    except OSError:
        return {
            "status": "MISSING",
            "profile": None,
            "reason": "Arquivo de perfil indisponível para leitura.",
        }
    except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError, RecursionError):
        return {
            "status": "INVALID",
            "profile": None,
            "reason": "Contrato, hash ou vínculo do perfil inválido.",
        }

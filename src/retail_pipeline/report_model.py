from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

TABLE_LIMIT = 500
CHART_LIMIT = 366
PRODUCT_LIMIT = 20


@dataclass(frozen=True)
class ReportPayload:
    synthetic_data: bool = False
    snapshot: Mapping[str, object] | None = None
    latest_attempt: Mapping[str, object] | None = None
    last_failed_attempt: Mapping[str, object] | None = None
    summary: Mapping[str, object] = field(default_factory=dict)
    daily: Sequence[Mapping[str, object]] = ()
    stores: Sequence[Mapping[str, object]] = ()
    products: Sequence[Mapping[str, object]] = ()
    daily_truncated: bool = False
    stores_truncated: bool = False
    products_truncated: bool = False

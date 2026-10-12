"""Visuais de leitura do recorte publicado, sem consultas ou cálculos com float."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
    localcontext,
)
from html import escape


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def _precision(values: Sequence[Decimal]) -> int:
    return max(
        38,
        max((value.adjusted() for value in values), default=0)
        + max((max(0, -int(value.as_tuple().exponent)) for value in values), default=0)
        + len(str(len(values)))
        + 8,
    )


def _sum(values: Sequence[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = _precision(values)
        return sum(values, Decimal(0))


def _raw(value: Decimal) -> str:
    return format(value, "f")


def _numeric(value: Decimal) -> str:
    return format(value, ",f").translate(str.maketrans(",.", ".,"))


def _money(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = _precision([value])
        rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return "R$ " + format(rounded, ",.2f").translate(str.maketrans(",.", ".,"))


def _percentage(value: Decimal, total: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = _precision([value, total])
        return (value / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _position(value: Decimal, total: Decimal) -> str:
    with localcontext() as context:
        context.prec = _precision([value, total])
        return format(value / total * 100, ".6f") if total else "0.000000"


def _axis_money(value: Decimal) -> str:
    for divisor, suffix in (
        (Decimal("1000000000000"), "tri"),
        (Decimal("1000000000"), "bi"),
        (Decimal("1000000"), "mi"),
        (Decimal("1000"), "mil"),
    ):
        if abs(value) >= divisor:
            with localcontext() as context:
                context.prec = _precision([value])
                scaled = (value / divisor).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            label = format(scaled, "f").rstrip("0").rstrip(".").replace(".", ",")
            return f"R$ {label} {suffix}"
    return _money(value)


def _empty(message: str, chart: str) -> str:
    return f'<p class="chart-empty" data-chart="{chart}">{_text(message)}</p>'


def _aggregate(
    rows: Sequence[Mapping[str, object]], identifier: str, metric: str
) -> tuple[dict[str, Decimal | None], int]:
    grouped: dict[str, list[Decimal | None]] = {}
    omitted = 0
    for row in rows:
        label = str(row[identifier]) if row.get(identifier) is not None else ""
        if not label.strip():
            omitted += 1
            continue
        grouped.setdefault(label, []).append(_number(row.get(metric)))
    totals = {
        label: None
        if any(value is None for value in values)
        else _sum([value for value in values if value is not None])
        for label, values in grouped.items()
    }
    return totals, omitted


def sales_trend(rows: Sequence[Mapping[str, object]]) -> str:
    """Colunas por dia; distância temporal real e zero distinto de ausência."""
    if not rows:
        return _empty("Sem receita publicada para desenhar.", "sales-trend")
    grouped: dict[date, list[Decimal | None]] = {}
    invalid_dates = 0
    for row in rows:
        try:
            day = date.fromisoformat(str(row.get("business_date")))
        except ValueError:
            invalid_dates += 1
            continue
        grouped.setdefault(day, []).append(_number(row.get("net_revenue_brl")))
    values = sorted(
        (day, items[0])
        for day, items in grouped.items()
        if len(items) == 1 and items[0] is not None
    )
    if not values:
        return _empty(
            "Receita não informada ou datas inválidas/duplicadas neste recorte.", "sales-trend"
        )
    valid = [(day, value) for day, value in values if value is not None]
    numbers = [value for _, value in valid]
    with localcontext() as context:
        context.prec = _precision(numbers)
        low, high = min(Decimal(0), min(numbers)), max(Decimal(0), max(numbers))
        target = (high - low) / 4 if high != low else Decimal("0.25")
        magnitude = Decimal(10) ** target.adjusted()
        step = max(
            Decimal("0.01"),
            next(Decimal(n) * magnitude for n in (1, 2, 5, 10) if Decimal(n) * magnitude >= target),
        )
        floor = (low / step).to_integral_value(rounding=ROUND_FLOOR) * step
        ceiling = (high / step).to_integral_value(rounding=ROUND_CEILING) * step
        if ceiling == floor:
            ceiling = floor + step
        scale = ceiling - floor
        zero_y = Decimal(198) - (-floor / scale * 196)
        intervals = int(scale / step)
        first, last = min(grouped), max(grouped)
        span = (last - first).days + 1
        column_width = min(Decimal(64), Decimal(560) / span * Decimal("0.7"))
        grid, axes, bars = [], [], []
        for index in range(intervals + 1):
            value = ceiling - step * index
            y = Decimal(2) + Decimal(196) * index / intervals
            grid.append(
                f'<line class="sales-trend-grid" x1="0" x2="600" y1="{y:.4f}" '
                f'y2="{y:.4f}" vector-effect="non-scaling-stroke"/>'
            )
            axes.append(f'<li style="--tick-top:{y / 2:.4f}%">{_text(_axis_money(value))}</li>')
        for day, value in valid:
            x = Decimal(20) + Decimal(560) * (Decimal((day - first).days) + Decimal("0.5")) / span
            y = Decimal(198) - (value - floor) / scale * 196
            attributes = (
                f'data-chart-date="{day.isoformat()}" data-value-raw="{_raw(value)}" '
                f'data-sign="{"negative" if value < 0 else "zero" if value == 0 else "positive"}"'
            )
            title = _text(f"{day:%d/%m/%Y}: {_money(value)}")
            if value == 0:
                bars.append(
                    f'<line class="sales-trend-zero-value" {attributes} x1="{x - 4:.4f}" '
                    f'x2="{x + 4:.4f}" y1="{zero_y:.4f}" y2="{zero_y:.4f}" '
                    f'vector-effect="non-scaling-stroke"><title>{title}</title></line>'
                )
            else:
                bars.append(
                    f'<rect class="sales-trend-bar" {attributes} x="{x - column_width / 2:.4f}" '
                    f'y="{min(y, zero_y):.4f}" width="{column_width:.4f}" '
                    f'height="{abs(y - zero_y):.4f}"><title>{title}</title></rect>'
                )
        tick_days = sorted({first, valid[len(valid) // 2][0], last})
        dates = "".join(
            f'<span style="--tick-left:{(Decimal((day - first).days) + Decimal("0.5")) / span * 100:.4f}%">'
            f"{day:%d/%m/%Y}</span>"
            for day in tick_days
        )
    description = "; ".join(f"{day:%d/%m/%Y}: {_money(value)}" for day, value in valid)
    missing = len(valid) < len(grouped) or (last - first).days + 1 > len(grouped)
    note = " Datas sem observação não representam receita zero." if missing else ""
    if invalid_dates:
        note += " Datas inválidas foram omitidas."
    peak_day, peak_value = max(valid, key=lambda item: item[1])
    caption = (
        f"Maior receita do recorte: {_money(peak_value)} em {peak_day:%d/%m/%Y}."
        if len(valid) > 1
        else "Um dia registrado no recorte."
    ) + note
    return (
        '<figure class="sales-trend" data-chart="sales-trend"><div class="sales-trend-frame">'
        f'<ol class="sales-trend-axis" aria-hidden="true">{"".join(axes)}</ol>'
        '<div class="sales-trend-visual"><svg class="sales-trend-svg" viewBox="0 0 600 200" '
        'width="100%" height="240" preserveAspectRatio="none" role="img" '
        'aria-label="Receita líquida por dia comercial, em BRL">'
        '<title>Receita líquida por dia comercial</title>'
        f'<desc>{_text(description)}. Eixo inclui receita zero.</desc>{"".join(grid)}'
        f'<line class="sales-trend-zero-line" x1="0" x2="600" y1="{zero_y:.4f}" '
        f'y2="{zero_y:.4f}" vector-effect="non-scaling-stroke"/>{"".join(bars)}</svg>'
        f'<div class="sales-trend-dates" aria-hidden="true">{dates}</div></div></div>'
        f'<figcaption class="chart-caption">{_text(caption)}</figcaption></figure>'
    )


def store_ranking(rows: Sequence[Mapping[str, object]], truncated: bool = False) -> str:
    """Até seis lojas, agregadas somente nas linhas exibidas; nenhuma receita inventada."""
    totals, omitted = _aggregate(rows, "store_id", "net_revenue_brl")
    complete = sorted(
        ((label, amount) for label, amount in totals.items() if amount is not None),
        key=lambda item: (-item[1], item[0]),
    )
    ranked = complete[:6]
    if not ranked:
        return _empty("Sem receita completa por loja neste recorte.", "store-ranking")
    amounts = [amount for _, amount in ranked]
    total = _sum([amount for _, amount in complete])
    shares = all(amount >= 0 for _, amount in complete) and total > 0
    with localcontext() as context:
        context.prec = _precision(amounts)
        low, high = min(Decimal(0), min(amounts)), max(Decimal(0), max(amounts))
        span = high - low
        zero = -low
        items = []
        for label, amount in ranked:
            left = zero if amount >= 0 else zero + amount
            percent = _percentage(amount, total) if shares else None
            percentage = (
                f'<span class="chart-percentage" data-share-percent-raw="{_raw(percent)}">'
                f"{_numeric(percent)}%</span>"
                if percent is not None
                else ""
            )
            items.append(
                f'<li class="store-ranking-row" data-chart-store="{_text(label)}" '
                f'data-value-raw="{_raw(amount)}" data-sign="{"negative" if amount < 0 else "positive"}">'
                f'<span class="store-ranking-label">{_text(label)}</span>'
                '<span class="store-ranking-track" aria-hidden="true">'
                f'<span class="store-ranking-zero" style="left:{_position(zero, span)}%"></span>'
                f'<span class="store-ranking-bar" style="left:{_position(left, span)}%;'
                f'width:{_position(abs(amount), span)}%"></span></span>'
                f'<strong class="store-ranking-value numeric">{_text(_money(amount))}</strong>'
                f"{percentage}</li>"
            )
    scope = f"{len(ranked)} de {len(complete)} lojas. "
    scope += (
        "Participação na receita deste recorte." if shares else "Receita por loja neste recorte."
    )
    if truncated:
        scope += " Recorte parcial de linhas exibidas."
    if any(amount is None for amount in totals.values()) or omitted:
        scope += " Lojas sem identificação ou receita completa não entram no ranking."
    denominator = f' data-share-denominator-raw="{_raw(total)}"' if shares else ""
    return (
        f'<figure class="store-ranking" data-chart="store-ranking"{denominator}>'
        f'<ol class="store-ranking-list">{"".join(items)}</ol>'
        f'<figcaption class="chart-caption">{_text(scope)}</figcaption></figure>'
    )


def product_mix(rows: Sequence[Mapping[str, object]], truncated: bool = False) -> str:
    """Cinco produtos e demais; participação no recorte, nunca no total global."""
    totals, omitted = _aggregate(rows, "product_id", "units")
    if not totals:
        return _empty("Sem produtos identificados neste recorte.", "product-mix")
    ordered = sorted(totals.items(), key=lambda item: (item[1] is None, -(item[1] or 0), item[0]))
    units = [amount for _, amount in ordered if amount is not None]
    total = _sum(units)
    negative = any(amount < 0 for amount in units)
    shares = total > 0 and not negative
    displayed: list[tuple[str, Decimal | None, int]] = [
        (label, amount, 0) for label, amount in ordered[:5]
    ]
    if len(ordered) > 5:
        remaining = [amount for _, amount in ordered[5:] if amount is not None]
        displayed.append(
            ("Demais produtos exibidos", _sum(remaining) if remaining else None, len(ordered) - 5)
        )
    segments, legend = [], []
    for index, (label, amount, grouped_count) in enumerate(displayed):
        identity = (
            f'data-chart-product-group="remaining" data-product-count="{grouped_count}"'
            if grouped_count
            else f'data-chart-product="{_text(label)}"'
        )
        raw = f' data-units-raw="{_raw(amount)}"' if amount is not None else ""
        percent = _percentage(amount, total) if shares and amount is not None else None
        share = (
            f'<span class="chart-percentage" data-share-percent-raw="{_raw(percent)}">'
            f"{_numeric(percent)}%</span>"
            if percent is not None
            else ""
        )
        if shares and amount is not None and amount > 0:
            segments.append(
                f'<span class="product-mix-segment" {identity}{raw} '
                f'data-mix-index="{index % 6}" style="width:{_position(amount, total)}%"></span>'
            )
        legend.append(
            f'<li class="product-mix-item" {identity}{raw}>'
            f'<span class="product-mix-swatch" data-mix-index="{index % 6}" aria-hidden="true"></span>'
            f'<span class="product-mix-name">{_text(label)}</span>'
            f'<strong class="product-mix-value numeric">{_numeric(amount) if amount is not None else "—"}</strong>'
            f"{share}</li>"
        )
    scope = (
        "Unidades nos produtos exibidos."
        if not truncated
        else "Unidades no recorte de produtos exibidos."
    )
    if any(amount is None for amount in totals.values()) or omitted:
        scope += " Valores ausentes não entram na participação."
    if negative:
        scope += " Participação não calculada: há unidades negativas."
    elif not units:
        scope += " Unidades não informadas."
    elif total == 0:
        scope += " Zero unidades registradas."
    denominator = f' data-share-denominator-raw="{_raw(total)}"' if shares else ""
    track = (
        f'<div class="product-mix-track" aria-hidden="true">{"".join(segments)}</div>'
        if segments
        else ""
    )
    return (
        f'<figure class="product-mix" data-chart="product-mix"{denominator}>{track}'
        f'<ol class="product-mix-legend">{"".join(legend)}</ol>'
        f'<figcaption class="chart-caption">{_text(scope)}</figcaption></figure>'
    )

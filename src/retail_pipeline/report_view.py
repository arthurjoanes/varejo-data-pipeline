from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from html import escape
from importlib.resources import files

from retail_pipeline.report_assets import BRAND_MARK, FAVICON, FONT_CSS, FONT_NOTICE
from retail_pipeline.report_model import (
    CHART_LIMIT,
    PRODUCT_LIMIT,
    PROFILE_GROUP_LIMIT,
    PROFILE_QUANTILE_LIMIT,
    TABLE_LIMIT,
    ReportPayload,
)

CSS = FONT_CSS + files("retail_pipeline").joinpath("report.css").read_text(encoding="utf-8")
SCRIPT = files("retail_pipeline").joinpath("report.js").read_text(encoding="utf-8")

STATE_LABELS = {
    "RUNNING": "Sem resultado final",
    "PUBLISHED": "Publicado",
    "NO_CHANGE": "Sem mudança",
    "BLOCKED": "Bloqueado",
    "TECHNICAL_FAILURE": "Falha técnica",
    "VALIDATED": "Validado",
}
STAGE_LABELS = {
    "ingestion": "Ingestão",
    "quality": "Qualidade",
    "silver": "Estado dos itens",
    "gold": "Indicadores",
    "reconciliation": "Reconciliação",
    "publication": "Publicação",
    "complete": "Conclusão",
}
SEVERITY_LABELS = {"ERROR": "Erro", "BLOCKER": "Bloqueio", "WARNING": "Aviso", "INFO": "Informação"}
SEVERITY_PRIORITY = {"ERROR": 3, "BLOCKER": 3, "WARNING": 2, "INFO": 1}
TABLE_GRAINS = {
    "bronze": "Registros recebidos",
    "history": "Revisões de itens aceitas",
    "silver": "Estado atual por item",
    "gold_store_day": "Loja e dia comercial",
    "gold_product_day": "Produto e dia comercial",
}
ISSUE_MESSAGES = {
    "MISSING_STORE": "Loja sem entrega ou confirmação de zero movimento.",
    "MISSING_FILE": "Arquivo do manifesto não recebido.",
    "UNEXPECTED_FILE": "Arquivo fora do manifesto.",
    "UNEXPECTED_STORE": "Loja fora da lista esperada para a janela.",
    "HASH_MISMATCH": "Hash do arquivo diferente do manifesto.",
    "SCHEMA_MISMATCH": "Cabeçalho do CSV com colunas ou ordem inválidas.",
    "ROW_WIDTH_MISMATCH": "Linha com quantidade de campos diferente do cabeçalho.",
    "ROW_COUNT_MISMATCH": "Quantidade de registros diferente do manifesto.",
    "COVERAGE_MISMATCH": "Cobertura diferente das lojas nos arquivos e confirmações.",
    "EMPTY_FILE": "Arquivo vazio, sem cabeçalho.",
    "EMPTY_WITHOUT_ZERO_CONFIRMATION": "Entrega vazia, sem confirmação de zero movimento.",
    "INVALID_ZERO_CONFIRMATION": "Confirmação de zero movimento inválida ou incompatível com os registros.",
    "UNKNOWN_STORE": "Loja fora do cadastro de lojas ativas.",
    "UNKNOWN_PRODUCT": "Produto não cadastrado.",
    "SOURCE_MISMATCH": "Origem diferente do manifesto.",
    "FILE_STORE_MISMATCH": "Loja diferente da indicada para o arquivo.",
    "INVALID_SOURCE_SYSTEM": "ID da origem inválido.",
    "INVALID_STORE_ID": "ID da loja inválido.",
    "INVALID_SALE_ID": "ID da venda inválido.",
    "INVALID_LINE_ID": "ID do item inválido.",
    "INVALID_PRODUCT_ID": "ID do produto inválido.",
    "INVALID_REVISION": "Revisão deve ser um inteiro positivo dentro do limite.",
    "INVALID_QUANTITY": "Quantidade deve ser um inteiro positivo dentro do limite.",
    "INVALID_OPERATION": "A operação deve ser UPSERT ou CANCEL.",
    "INVALID_UNIT_PRICE_BRL": "O preço deve ser um decimal não negativo, com até duas casas e dentro do limite.",
    "INVALID_LINE_DISCOUNT_BRL": "O desconto deve ser um decimal não negativo, com até duas casas e dentro do limite.",
    "DISCOUNT_EXCEEDS_GROSS": "Desconto maior que o valor bruto do item.",
    "INVALID_SOLD_AT": "Data da venda inválida. Use o formato do contrato, com fuso.",
    "INVALID_SOURCE_UPDATED_AT": "Data de atualização inválida. Informe o fuso.",
    "INPUT_NOT_DIRECTORY": "A entrada deve ser uma pasta existente, sem symlink.",
    "UNSAFE_SYMLINK": "Symlink recusado na entrada.",
    "UNSAFE_FILE_TYPE": "Tipo de arquivo não permitido na entrada.",
    "UNSAFE_PATH": "Caminho inválido. Use um caminho relativo dentro da entrada.",
    "FILE_COPY_FAILED": "Falha ao copiar o arquivo recebido.",
    "CSV_DECODE_ERROR": "Falha ao ler CSV UTF-8.",
    "INVALID_MANIFEST": "Manifesto inválido. Use um objeto JSON.",
    "UNSUPPORTED_SCHEMA_VERSION": "Versão do manifesto não suportada.",
    "INVALID_MANIFEST_FIELD": "Campo inválido no manifesto.",
    "UNKNOWN_MANIFEST_FIELDS": "Campos desconhecidos no manifesto.",
    "INVALID_MANIFEST_FILES": "Lista de arquivos inválida no manifesto.",
    "INVALID_MANIFEST_FILE": "Dados de arquivo inválidos no manifesto.",
    "DUPLICATE_MANIFEST_FILE": "Caminho de arquivo repetido no manifesto.",
    "INVALID_CATALOG": "Cadastro de lojas e produtos inválido.",
    "CATALOG_SCHEMA_VERSION": "Versão do cadastro não suportada.",
    "DUPLICATE_REFERENCE": "ID repetido no cadastro.",
    "INVALID_SCHEDULE": "Calendário de entregas inválido.",
    "SCHEDULE_SCHEMA_VERSION": "Versão do calendário não suportada.",
    "INVALID_SCHEDULE_WINDOW": "ID de janela inválido no calendário.",
    "DUPLICATE_SCHEDULE_WINDOW": "Origem e janela repetidas no calendário.",
    "INVALID_SCHEDULE_STORES": "Lista de lojas da janela inválida.",
    "INVALID_DELIVERY_INTERVAL": "Intervalo de entrega inválido. O início deve vir antes do fim.",
    "UNKNOWN_OR_DUPLICATE_WINDOW": "Origem e janela sem correspondência única no calendário.",
}


def _text(value: object) -> str:
    return escape(str(value) if value is not None else "—", quote=True)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, list | tuple):
        return value
    return ()


def _decimal(value: object) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal(0)


def _money(value: object) -> str:
    if value is None:
        return "—"
    amount = _decimal(value)
    with localcontext() as context:
        context.prec = max(38, amount.adjusted() + 4)
        rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    numeric = f"{rounded:,.2f}"
    return "R$ " + numeric.translate(str.maketrans(",.", ".,"))


def _integer(value: object) -> str:
    return "—" if value is None else f"{int(str(value)):,}".replace(",", ".")


def _exact_decimal(value: object) -> str:
    """Preserva as casas do contrato, inclusive médias e diferenças sem float."""
    if value is None:
        return "—"
    amount = _decimal(value)
    if not amount.is_finite():
        return "—"
    return format(amount, ",f").translate(str.maketrans(",.", ".,"))


def _date(value: object) -> str:
    if value is None:
        return "—"
    try:
        parsed = date.fromisoformat(str(value)[:10])
        return f"{parsed.day:02d}/{parsed.month:02d}/{parsed.year:04d}"
    except ValueError:
        return str(value)


def _timestamp(value: object) -> str:
    if value is None:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y · %H:%M:%S %Z")
    except ValueError:
        return str(value)


def _state_badge(state: object) -> str:
    code = str(state)
    css = (
        "danger"
        if code in {"BLOCKED", "TECHNICAL_FAILURE"}
        else "success"
        if code in {"PUBLISHED", "NO_CHANGE"}
        else "neutral"
    )
    return f'<span class="badge {css}">{_text(STATE_LABELS.get(code, code))}</span>'


def _issue_message(issue: Mapping[str, object]) -> object:
    if issue.get("code") == "TECHNICAL_FAILURE":
        return "Falha técnica. Consulte os detalhes da tentativa."
    if issue.get("code") == "EXACT_DUPLICATE":
        return "Revisão idêntica já recebida. Não altera o estado do item."
    if issue.get("code") == "STALE_REVISION":
        return "Revisão antiga preservada no histórico. O estado atual do item não mudou."
    if issue.get("message"):
        return issue["message"]
    message = ISSUE_MESSAGES.get(
        str(issue.get("code")),
        "Consulte os detalhes da tentativa.",
    )
    context = "; ".join(
        f"{label}: {issue[key]}"
        for key, label in (
            ("store_id", "loja"),
            ("file", "arquivo"),
            ("line", "linha"),
            ("count", "ocorrências"),
        )
        if issue.get(key) is not None
    )
    return f"{message} {context}." if context else message


def _chips(values: object, limit: int = 40) -> str:
    items = _sequence(values)
    result = "".join(f'<span class="chip">{_text(item)}</span>' for item in items[:limit])
    if len(items) > limit:
        result += f'<span class="chip">+{len(items) - limit}</span>'
    return result or '<span class="muted">Nenhuma</span>'


def _card(label: str, value: str, note: str, *, metric: str, accent: bool = False) -> str:
    css = "metric accent" if accent else "metric"
    if len(value) > 18:
        css += " metric-wide"
    overflow = (
        f' tabindex="0" role="region" aria-label="{_text(label)}: valor completo"'
        if len(value) > 18
        else ""
    )
    return (
        f'<article class="{css}"><p class="metric-label">{_text(label)}</p>'
        f'<strong{overflow} data-metric="{metric}">{_text(value)}</strong><p>{_text(note)}</p></article>'
    )


def _duration(value: object, *, exact: bool = False) -> str:
    if value is None:
        return "—"
    amount = _decimal(value)
    numeric = (
        format(amount, "f")
        if exact
        else format(amount.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), ".1f")
    )
    return numeric.replace(".", ",") + " s"


def _copy_field(value: object, label: str, field_id: str, *, status_id: str = "copy-status") -> str:
    if value is None:
        return f'<p class="meta">{_text(label)}: indisponível.</p>'
    return (
        f'<div class="copy-field"><label for="{field_id}">{_text(label)}</label>'
        f'<div><input id="{field_id}" value="{_text(value)}" readonly spellcheck="false" autocomplete="off" name="{field_id}" translate="no">'
        f'<button type="button" hidden data-copy-target="{field_id}" data-copy-status="{_text(status_id)}" aria-label="Copiar {_text(label)}">Copiar</button></div></div>'
    )


def _short_id_link(
    value: object,
    label: str,
    field_id: str = "proveniencia",
    *,
    section_label: str = "Arquivos e versões",
) -> str:
    if value is None:
        return "—"
    full = str(value)
    short = full if len(full) <= 16 else full[:8] + "…" + full[-4:]
    return f'<a class="id-link" href="#{_text(field_id)}" aria-label="Ver ID completo {_text(label)} em {_text(section_label)}">{_text(short)}</a>'


def _axis_scale(maximum: Decimal) -> tuple[Decimal, int]:
    """Intervalos 1/2/5 em potência de dez, sem converter dinheiro para float."""
    target = maximum / 4 if maximum > 0 else Decimal("0.25")
    magnitude = Decimal(10) ** target.adjusted()
    step = next(Decimal(n) * magnitude for n in (1, 2, 5, 10) if Decimal(n) * magnitude >= target)
    step = max(step, Decimal("0.01"))
    intervals = max(1, int((maximum / step).to_integral_value(rounding=ROUND_CEILING)))
    return step, intervals


def _axis_money(value: Decimal) -> str:
    for divisor, suffix in (
        (Decimal("1000000000"), "bi"),
        (Decimal("1000000"), "mi"),
        (Decimal("1000"), "mil"),
    ):
        if value >= divisor:
            numeric = format(value / divisor, ".1f").rstrip("0").rstrip(".").replace(".", ",")
            return f"R$ {numeric} {suffix}"
    return _money(value)


def _revenue_chart(rows: Sequence[Mapping[str, object]]) -> str:
    if not rows:
        return '<p class="empty">Sem receita publicada.</p>'
    missing_values = any(row.get("net_revenue_brl") is None for row in rows)
    rows = [row for row in rows if row.get("net_revenue_brl") is not None]
    if not rows:
        return '<p class="empty">Receita não informada neste recorte. Consulte a tabela de valores.</p>'
    width, left, right, top, bottom = 900, 110, 20, 20, 210
    plot_width = width - left - right
    try:
        dates = [date.fromisoformat(str(row.get("business_date"))) for row in rows]
    except ValueError:
        dates = []
    date_span = (max(dates) - min(dates)).days if dates else 0
    values = [_decimal(row.get("net_revenue_brl")) for row in rows]
    minimum = min(Decimal(0), min(values))
    step, intervals = _axis_scale(max(values) - minimum)
    floor = (minimum / step).to_integral_value(rounding=ROUND_FLOOR) * step
    ceiling = max(Decimal(0), (max(values) / step).to_integral_value(rounding=ROUND_CEILING) * step)
    if ceiling == floor:
        ceiling = floor + step
    intervals = int((ceiling - floor) / step)
    zero_y = bottom - int(-floor / (ceiling - floor) * (bottom - top))
    points: list[str] = []
    grid: list[str] = []
    for index in range(intervals + 1):
        y = top + (bottom - top) * index // intervals
        label = _axis_money(ceiling - step * index)
        grid.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y}" y2="{y}" '
            f'stroke="#dae2ec"/><text x="{left - 12}" y="{y + 4}" '
            f'text-anchor="end" class="chart-label">{_text(label)}</text>'
        )
    for index, value in enumerate(values):
        if dates:
            x = left + (plot_width * (dates[index] - min(dates)).days // max(1, date_span))
        else:
            x = left + plot_width * index // max(1, len(values) - 1)
        y = bottom - int((value - floor) / (ceiling - floor) * (bottom - top))
        points.append(f"{x},{y}")
    ticks = sorted({0, len(rows) // 2, len(rows) - 1})
    labels = "".join(
        f'<text x="{points[index].split(",")[0]}" '
        f'y="240" text-anchor="{"end" if index == len(rows) - 1 else "middle"}" class="chart-label">'
        f"{_text(_date(rows[index].get('business_date')))}</text>"
        for index in ticks
    )
    segments: list[list[str]] = []
    for index, point in enumerate(points):
        if index and dates and (dates[index] - dates[index - 1]).days == 1:
            segments[-1].append(point)
        else:
            segments.append([point])
    paths = []
    for segment in segments:
        if len(segment) < 2:
            continue
        area = (
            f"{segment[0].split(',')[0]},{zero_y} "
            + " ".join(segment)
            + f" {segment[-1].split(',')[0]},{zero_y}"
        )
        paths.append(
            f'<polygon points="{area}" fill="#e4eef8"/>'
            f'<polyline points="{" ".join(segment)}" fill="none" '
            'stroke="#245b64" stroke-width="3" stroke-linejoin="round"/>'
        )
    dots = "".join(
        f'<circle cx="{point.split(",")[0]}" cy="{point.split(",")[1]}" '
        f'r="4" fill="#245b64"><title>{_text(_date(row.get("business_date")))}: '
        f"{_text(_money(row.get('net_revenue_brl')))}</title></circle>"
        for point, row in zip(points, rows, strict=True)
    )
    return (
        '<svg viewBox="0 0 900 260" role="img" '
        'aria-label="Receita líquida por dia comercial, em reais">'
        "<title>Receita líquida por dia comercial</title>"
        + "".join(grid)
        + "".join(paths)
        + dots
        + labels
        + "</svg>"
        + (
            '<p class="footnote">Receitas não informadas não foram desenhadas como zero; consulte a tabela.</p>'
            if missing_values
            else ""
        )
        + (
            '<p class="footnote">Trechos separados indicam datas sem observação contínua. '
            "Dias sem observação não representam receita zero.</p>"
            if len(segments) > 1
            else ""
        )
    )


def _table(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[tuple[str, str, str]],
    *,
    label: str = "Tabela de indicadores publicados",
    row_prefix: str = "",
    row_header: bool = False,
) -> str:
    if not rows:
        return '<p class="empty">Sem registros neste recorte.</p>'
    head = "".join(f'<th scope="col">{_text(label)}</th>' for _, label, _ in columns)
    body: list[str] = []
    for row_index, row in enumerate(rows):
        cells = []
        for column_index, (key, _, kind) in enumerate(columns):
            value = row.get(key)
            if kind == "money":
                display = _money(value)
            elif kind == "integer":
                display = _integer(value)
            elif kind == "date":
                display = _date(value)
            elif kind == "decimal":
                display = _exact_decimal(value)
            else:
                display = str(value) if value is not None else "—"
            css = (
                ' class="numeric"'
                if kind in {"money", "integer", "decimal", "formatted_numeric"}
                else ""
            )
            tag = "th" if row_header and column_index == 0 else "td"
            scope = ' scope="row"' if tag == "th" else ""
            cells.append(f"<{tag}{scope}{css}>{_text(display)}</{tag}>")
        row_id = f' id="{row_prefix}-{row_index}" tabindex="-1"' if row_prefix else ""
        body.append(f"<tr{row_id}>" + "".join(cells) + "</tr>")
    return (
        f'<div class="table-scroll" tabindex="0" role="region" aria-label="{_text(label)}"><table><caption class="sr-only">{_text(label)}</caption><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _product_ranking(rows: Sequence[Mapping[str, object]]) -> str:
    """Compara unidades do recorte já ordenado; não recalcula o ranking no navegador."""
    if not rows:
        return '<p class="empty">Sem produtos neste recorte.</p>'
    maximum = max((_decimal(row.get("units")) for row in rows), default=Decimal(0))
    items = []
    for row in rows:
        value = row.get("units")
        units = _decimal(value)
        width = max(Decimal(0), units) / maximum * 100 if maximum > 0 else Decimal(0)
        label = _integer(value)
        items.append(
            '<li class="ranking-row">'
            f'<span class="ranking-name">{_text(row.get("product_id"))}</span>'
            f'<span class="ranking-track" aria-hidden="true"><span style="width:{width:.3f}%"></span></span>'
            f'<strong class="numeric">{_text(label)}</strong></li>'
        )
    return (
        '<p class="ranking-scale">Unidades · escala a partir de zero</p>'
        f'<ol class="product-ranking" aria-label="Unidades por produto, na ordem do ranking publicado">{"".join(items)}</ol>'
    )


def _store_matrix(rows: Sequence[Mapping[str, object]]) -> str:
    """Escala de receita por célula existente. Ausência nunca vira receita zero."""
    if not rows:
        return '<p class="empty">Sem observações de loja e dia neste recorte.</p>'
    try:
        observed_dates = sorted({date.fromisoformat(str(row.get("business_date"))) for row in rows})
    except ValueError:
        return '<p class="empty">Datas não interpretáveis na matriz. Consulte os registros exatos na tabela.</p>'
    stores = sorted({str(row.get("store_id")) for row in rows})
    span = (observed_dates[-1] - observed_dates[0]).days + 1
    # Protege períodos extremos antes de criar a grade; a tabela continua completa.
    if span > 366 or span * len(stores) > 1200:
        return '<p class="empty">Recorte amplo ou disperso para uma matriz legível. Os valores completos deste recorte estão na tabela por loja e dia.</p>'
    dates = [observed_dates[0] + timedelta(days=index) for index in range(span)]
    indexed: dict[tuple[str, str], tuple[int, Mapping[str, object]]] = {}
    duplicates: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        key = str(row.get("store_id")), str(row.get("business_date"))
        if key in indexed:
            duplicates.add(key)
        indexed[key] = index, row
    values = [
        _decimal(row[1]["net_revenue_brl"])
        for key, row in indexed.items()
        if key not in duplicates and row[1].get("net_revenue_brl") is not None
    ]
    maximum = max(values, default=Decimal(0))
    minimum = min(Decimal(0), min(values, default=Decimal(0)))
    scale = maximum - minimum
    colors = ("#e6f1f2", "#c3dce0", "#96bdc4", "#6695a0", "#3d7380", "#245b64")
    header = "".join(
        f'<th scope="col" aria-label="{_text(_date(day.isoformat()))}">{day.day:02d}</th>'
        for day in dates
    )
    months: list[tuple[str, int]] = []
    for day in dates:
        month = f"{day.month:02d}/{day.year:04d}"
        if months and months[-1][0] == month:
            months[-1] = month, months[-1][1] + 1
        else:
            months.append((month, 1))
    month_header = "".join(
        f'<th scope="colgroup" colspan="{count}">{month}</th>' for month, count in months
    )
    body: list[str] = []
    first_cell = True
    for store in stores:
        cells = []
        for column, day in enumerate(dates):
            key = store, day.isoformat()
            entry = indexed.get(key)
            value = entry[1].get("net_revenue_brl") if entry else None
            if key in duplicates:
                content = (
                    '<span class="heat-unavailable"><span aria-hidden="true">!</span>'
                    '<span class="sr-only">Mais de um registro; consulte a tabela</span></span>'
                )
            elif entry is None or value is None:
                reason = "Sem observação" if entry is None else "Receita não informada"
                content = (
                    '<span class="heat-missing"><span aria-hidden="true">—</span>'
                    f'<span class="sr-only">{reason}</span></span>'
                )
            else:
                amount = _decimal(value)
                level = min(5, max(0, int((amount - minimum) / scale * 5))) if scale else 0
                exact = f"{store} · {_date(day.isoformat())} · {_money(value)}"
                css = "heat-cell heat-zero" if amount == 0 else "heat-cell"
                content = (
                    f'<a class="{css}" href="#store-row-{entry[0]}" '
                    f'data-heat-cell data-column="{column}" data-value="{_text(exact)}" '
                    f'data-row="{len(body)}" style="--cell-color:{colors[level]}" '
                    f'aria-label="{_text(exact)}" tabindex="{0 if first_cell else -1}">'
                    f'<span class="sr-only">{_text(_money(value))}</span>{"0" if amount == 0 else ""}</a>'
                )
                first_cell = False
            cells.append(f"<td>{content}</td>")
        body.append(f'<tr><th scope="row">{_text(store)}</th>{"".join(cells)}</tr>')
    swatches = "".join(f'<i style="background:{color}"></i>' for color in colors)
    return (
        '<div class="matrix-heading"><p class="meta">Receita líquida em BRL · cada célula é uma loja em um dia comercial.</p>'
        + (
            f'<div class="heat-legend"><span>{_text(_money(minimum))}</span><span class="heat-scale" aria-hidden="true">{swatches}</span><span>{_text(_money(maximum))}</span></div>'
            if values
            else '<p class="meta">Sem receita informada para definir a escala.</p>'
        )
        + '</div>'
        '<p class="matrix-help" hidden>Selecione uma célula para consultar o valor. Use as setas para percorrer a matriz.</p>'
        '<div class="matrix-scroll" tabindex="0" role="region" aria-label="Matriz de receita por loja e dia, com rolagem horizontal">'
        f'<table class="store-matrix" style="width:{83 + 39 * span}px"><colgroup><col style="width:80px"><col span="{span}" style="width:36px"></colgroup><thead><tr class="matrix-months"><th scope="col">Mês</th>{month_header}</tr><tr><th scope="col">Loja / dia</th>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        '<div class="matrix-reading"><output id="matrix-value" aria-live="polite">Valores exatos também disponíveis na tabela abaixo.</output>'
        '<a id="matrix-record" href="#store-values">Consultar tabela</a></div>'
        '<p class="matrix-key"><span><b class="zero-key">0</b> Receita zero registrada</span><span><b class="missing-key">—</b> Sem observação ou receita não informada</span></p>'
        + (
            '<p class="footnote">Células com ! têm mais de um registro. Nenhum valor foi somado: consulte as linhas na tabela.</p>'
            if duplicates
            else ""
        )
    )


def _coverage_panel(coverage: Mapping[str, object]) -> str:
    expected_known = isinstance(coverage.get("expected"), list | tuple)
    received_known = isinstance(coverage.get("received"), list | tuple)
    expected = set(map(str, _sequence(coverage.get("expected"))))
    received = set(map(str, _sequence(coverage.get("received"))))
    zero = set(map(str, _sequence(coverage.get("zero_movement"))))
    summary = (
        f"{len(expected & received)} de {len(expected)} lojas com entrega confirmada"
        if expected_known and received_known
        else "Cobertura não informada neste snapshot"
    )
    stores = []
    for store in sorted(expected | received | zero):
        if not expected_known or not received_known:
            label, css = "Conferência indisponível", "unknown"
        elif store not in expected:
            label, css = "Não esperada", "pending"
        elif store not in received:
            label, css = "Pendente", "pending"
        elif store in zero:
            label, css = "Zero movimento confirmado", "confirmed"
        else:
            label, css = "Entrega confirmada", "confirmed"
        stores.append(
            f'<li><span class="store-name">{_text(store)}</span>'
            f'<span class="delivery-state {css}">{label}</span></li>'
        )
    recorded = "".join(
        f"<div><dt>{label}</dt><dd>{_chips(coverage[key], len(_sequence(coverage[key]))) if key in coverage else 'Não informado'}</dd></div>"
        for key, label in (
            ("expected", "Esperadas"),
            ("received", "Recebidas"),
            ("zero_movement", "Zero movimento confirmado"),
        )
    )
    return (
        '<section class="coverage-summary" aria-labelledby="coverage-title">'
        '<div class="group-heading"><h3 id="coverage-title">Cobertura da entrega</h3>'
        f'<p class="coverage-total">{summary}</p></div>'
        f'<ul class="store-ledger">{"".join(stores)}</ul>'
        '<details class="record-disclosure"><summary>Listas registradas da cobertura</summary>'
        f'<dl class="coverage">{recorded}</dl></details></section>'
    )


def _duration_panel(attempt: Mapping[str, object]) -> str:
    stages = _mapping(attempt.get("stages"))
    measured = {name: value for name, value in stages.items() if name != "complete"}
    duration = (
        None
        if attempt.get("state") == "RUNNING" or attempt.get("audit_incomplete")
        else attempt.get("duration_seconds")
    )
    order = {name: index for index, name in enumerate(STAGE_LABELS)}
    notes = {
        "ingestion": "Leitura e conferência dos arquivos recebidos.",
        "quality": "Validação das regras de dados e das revisões. O diagnóstico explica o resultado da tentativa.",
        "silver": "Cálculo do estado dos itens a partir das revisões aceitas.",
        "gold": "Cálculo dos indicadores de loja, produto e dia comercial.",
        "reconciliation": "Conferência dos resultados antes da decisão de publicação.",
        "publication": "Etapa de publicação medida. O manifesto identifica a versão efetivamente publicada.",
    }
    steps = []
    for index, name in enumerate(
        sorted(measured, key=lambda key: (order.get(key, len(order)), key))
    ):
        steps.append(
            '<details class="stage" name="measured-stage">'
            f'<summary><span class="stage-number">{index + 1:02d}</span>'
            f'<span class="stage-name">{_text(STAGE_LABELS.get(name, name))}</span>'
            f'<span class="stage-time">{_text(_duration(measured[name]))}</span></summary>'
            f'<div class="stage-note"><p>{_text(notes.get(name, "Tempo informado pelo registro da tentativa."))}</p>'
            f"<p>Tempo exato: <b>{_text(_duration(measured[name], exact=True))}</b></p></div></details>"
        )
    rows = (
        "".join(
            f'<tr><td>{_text(STAGE_LABELS.get(name, name))}</td><td class="numeric">{_text(_duration(stages[name], exact=True))}</td></tr>'
            for name in sorted(stages, key=lambda name: (order.get(name, len(order)), name))
        )
        or '<tr><td colspan="2">Nenhuma etapa registrada.</td></tr>'
    )
    return (
        '<section class="stage-rail" aria-label="Etapas medidas da última tentativa">'
        '<div class="rail-heading"><h3>Etapas medidas</h3><span>Tempo registrado</span></div>'
        f"{''.join(steps) if steps else '<p class=empty>Nenhuma etapa medida.</p>'}"
        '<p class="footnote">Uma medição não confirma, por si só, o sucesso da etapa.</p>'
        '<details class="exact-durations"><summary>Registro completo de tempos</summary>'
        '<div class="table-scroll" tabindex="0" role="region" aria-label="Duração por etapa">'
        '<table><thead><tr><th scope="col">Etapa</th><th scope="col">Valor exato</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div><p class="footnote">Duração total registrada: {_text(_duration(duration, exact=True))}.</p></details></section>'
    )


def _quality_diagnostics(attempt: Mapping[str, object]) -> str:
    stats = _mapping(attempt.get("stats"))
    unchecked = stats.get("revision_checks_executed") == 0
    rows = []
    for key, label in (
        ("received", "Recebidos"),
        ("valid", "Válidos"),
        ("rejected", "Rejeitados"),
        ("violations", "Violações"),
        ("duplicates", "Duplicatas exatas"),
        ("conflicts", "Conflitos"),
        ("stale", "Revisões antigas"),
    ):
        value = (
            '<span class="not-assessed">Não avaliado</span>'
            if unchecked and key in {"duplicates", "conflicts", "stale"}
            else _integer(stats[key])
            if key in stats
            else "—"
        )
        rows.append(f"<div><dt>{label}</dt><dd>{value}</dd></div>")
    received = _decimal(stats.get("received"))
    ratio = (
        "indisponível"
        if "received" not in stats or "rejected" not in stats
        else f"{_decimal(stats.get('rejected')) * 100 / received:.2f}%".replace(".", ",")
        if received
        else "não aplicável"
    )
    reason = "bloqueio anterior" if attempt.get("state") == "BLOCKED" else "interrupção anterior"
    note = (
        f'<p class="footnote">Validação de revisões não executada por {reason}.</p>'
        if unchecked
        else ""
    )
    return (
        '<section class="quality-diagnostics"><h3>Contadores da tentativa</h3>'
        f'<dl class="counters">{"".join(rows)}</dl><p class="footnote">Rejeição: {ratio}. '
        "Cada linha rejeitada conta uma vez; uma linha pode gerar várias violações. "
        f"Duplicatas e revisões antigas são diagnósticos e podem se sobrepor.</p>{note}</section>"
    )


def _issue_table(attempt: Mapping[str, object]) -> str:
    issue_list = _sequence(attempt.get("issues"))
    ordered = sorted(
        issue_list,
        key=lambda value: -SEVERITY_PRIORITY.get(str(_mapping(value).get("severity")), 0),
    )
    rows: list[str] = []
    related: list[str] = []
    missing_file_stores = {
        str(_mapping(value).get("store_id"))
        for value in ordered[:50]
        if _mapping(value).get("code") == "MISSING_FILE"
        and _mapping(value).get("store_id") is not None
    }
    for value in ordered[:50]:
        issue = _mapping(value)
        severity = str(issue.get("severity", "ERROR"))
        css = (
            "error"
            if severity in {"ERROR", "BLOCKER"}
            else "warning"
            if severity == "WARNING"
            else "info"
        )
        context = "".join(
            f"<div><dt>{label}</dt><dd>{_text(issue[key])}</dd></div>"
            for key, label in (("store_id", "Loja"), ("file", "Arquivo"), ("line", "Linha"))
            if issue.get(key) is not None
        )
        count = (
            f'<span class="issue-count">{_text(issue["count"])} {"ocorrência" if issue["count"] == 1 else "ocorrências"}</span>'
            if issue.get("count") is not None
            else ""
        )
        titles = {
            "MISSING_FILE": "Arquivo não recebido",
            "MISSING_STORE": "Loja sem entrega confirmada",
            "HASH_MISMATCH": "Arquivo diferente do contratado",
            "SALE_DATE_CONFLICT": "Venda dividida entre dias",
            "REVISION_CONFLICT": "Revisões com conteúdo conflitante",
            "EXACT_DUPLICATE": "Reenvio sem efeito adicional",
            "STALE_REVISION": "Revisão anterior preservada",
            "TECHNICAL_FAILURE": "Falha durante o processamento",
        }
        code = str(issue.get("code", ""))
        title = titles.get(code, ISSUE_MESSAGES.get(code, "Ocorrência na entrega").rstrip("."))
        key_data = " · ".join(
            str(issue[key]) for key in ("store_id", "file") if issue.get(key) is not None
        )
        target_rows = (
            related
            if code == "MISSING_STORE" and str(issue.get("store_id")) in missing_file_stores
            else rows
        )
        body = (
            "O manifesto prevê este arquivo. Reponha os bytes originais para reexecutar o mesmo lote. Se o conteúdo mudar, use novo batch_id e correction_of."
            if code == "MISSING_FILE"
            else _issue_message(issue)
        )
        technical = (
            f'<details class="issue-record"><summary>Registro técnico</summary><p>{_text(_issue_message(issue))}</p>'
            if code == "MISSING_FILE"
            else '<details class="issue-record"><summary>Contexto técnico</summary>'
        )
        target_rows.append(
            f'<details class="issue {css}"{" open" if target_rows is rows and not rows else ""}>'
            f'<summary><span class="issue-title">{_text(title)}'
            f"{f'<span class=issue-key>{_text(key_data)}</span>' if key_data else ''}{count}</span></summary>"
            f'<div class="issue-body"><p>{_text(body)}</p>{technical}'
            f"{f'<dl class=issue-context>{context}</dl>' if context else ''}"
            f'<p class="issue-code"><span class="severity">{_text(SEVERITY_LABELS.get(severity, severity))}</span> · <code>{_text(code)}</code></p></details></div></details>'
        )
    if not rows:
        return '<p class="clean"><span aria-hidden="true">✓</span> Nenhuma ocorrência registrada nesta tentativa.</p>'
    note = (
        f'<p class="footnote">Exibindo 50 de {len(issue_list)} ocorrências. Consulte a quarentena.</p>'
        if len(issue_list) > 50
        else ""
    )
    return (
        '<div class="issues" role="group" aria-label="Motivos da decisão, severidade e ocorrências">'
        f"{''.join(rows)}{f'<details class=related-issues><summary>Ocorrências relacionadas ({len(related)})</summary>{chr(10).join(related)}</details>' if related else ''}</div>{note}"
    )


def _attempt_details(attempt: Mapping[str, object] | None) -> str:
    if attempt is None:
        return '<div class="empty-state"><h3>Nenhuma tentativa registrada.</h3><p>O relatório mostrará a entrega, as etapas medidas e o diagnóstico quando houver um registro.</p></div>'
    stats = _mapping(attempt.get("stats"))
    rejected = _integer(stats["rejected"]) if "rejected" in stats else "—"
    violations = _integer(stats["violations"]) if "violations" in stats else "—"
    received = _integer(stats["received"]) if "received" in stats else "—"
    problem = _decimal(stats.get("rejected")) > 0
    issue_html = _issue_table(attempt)
    if attempt.get("state") == "RUNNING":
        issue_html = (
            '<p class="empty">Execução sem resultado final. Consulte os logs e o manifesto.</p>'
        )
    if attempt.get("audit_incomplete"):
        issue_html = (
            '<p class="audit-note">Publicado, mas o registro final da tentativa falhou. Métricas ausentes aparecem como indisponíveis.</p>'
            + issue_html
        )
    return f"""
    <div class="execution-workspace">
    {_coverage_panel(_mapping(attempt.get("coverage")))}
    <section class="diagnostic-section" id="pendencias" tabindex="-1"><h3>Ocorrências da entrega</h3>{issue_html}</section>
    <div class="technical-register">
      <details class="quality-measurements record-disclosure"><summary>Contadores e validações técnicas</summary>
      <div class="quality-outcome {"has-rejections" if problem else ""}">
        <p><strong>{rejected} {"rejeitado" if stats.get("rejected") == 1 else "rejeitados"}</strong> de {received} {"registro recebido" if stats.get("received") == 1 else "registros recebidos"}</p><p>{violations} violações de registros</p>
      </div>{_quality_diagnostics(attempt)}</details>
      <details class="timing-disclosure record-disclosure"><summary>Tempos medidos desta tentativa</summary>{_duration_panel(attempt)}</details>
      <a class="run-record" href="#attempt-identity">Ver registro da tentativa</a>
    </div></div>
    """


def _publication_context(payload: ReportPayload) -> str:
    """Explica a relação observada entre tentativa e manifesto, sem inferir progresso."""
    attempt = payload.latest_attempt or {}
    snapshot = payload.snapshot or {}
    same_run = bool(attempt.get("run_id")) and attempt.get("run_id") == snapshot.get("run_id")
    state = attempt.get("state")
    if attempt.get("audit_incomplete") or (same_run and state == "TECHNICAL_FAILURE"):
        return "Publicação disponível, com registro final da tentativa incompleto. As métricas ausentes estão indicadas como indisponíveis."
    if state == "BLOCKED":
        coverage = _mapping(attempt.get("coverage"))
        missing = set(map(str, _sequence(coverage.get("expected")))) - set(
            map(str, _sequence(coverage.get("received")))
        )
        reason = (
            "Fechamento bloqueado por cobertura."
            if missing
            else "Fechamento bloqueado pelas regras de qualidade."
        )
        return reason + (
            " Os indicadores exibidos pertencem à publicação anterior."
            if payload.snapshot is not None
            else " Ainda não há indicadores publicados."
        )
    if state == "TECHNICAL_FAILURE":
        return "A tentativa falhou antes de publicar. " + (
            "Os indicadores da publicação anterior continuam disponíveis."
            if payload.snapshot is not None
            else "Ainda não há indicadores publicados."
        )
    if state == "RUNNING":
        return "Execução sem resultado final no registro consultado. Esta página não acompanha a execução em tempo real."
    if state == "NO_CHANGE":
        return "A tentativa não alterou o fechamento. Os indicadores continuam vinculados à publicação vigente."
    return (
        "Confira a entrega das lojas, as revisões aceitas e os indicadores do fechamento publicado."
        if payload.snapshot is not None
        else "Nenhum fechamento publicado. Consulte a tentativa para entender o resultado da entrega."
    )


def _failure_notice(payload: ReportPayload) -> str:
    failed = payload.last_failed_attempt
    if failed is None:
        return ""
    current = payload.latest_attempt or {}
    latest = failed.get("run_id") == current.get("run_id")
    heading = "Tentativa sem publicação" if latest else "Última falha ou bloqueio"
    if (
        failed.get("state") == "TECHNICAL_FAILURE"
        and payload.snapshot
        and payload.snapshot.get("run_id") == failed.get("run_id")
    ):
        heading = "Publicado, com falha técnica na tentativa"
    issues = _sequence(failed.get("issues"))
    primary_issue = max(
        (_mapping(issue) for issue in issues),
        key=lambda issue: SEVERITY_PRIORITY.get(str(issue.get("severity")), 0),
        default={},
    )
    reason = _issue_message(primary_issue) if primary_issue else "Consulte os detalhes da execução."
    notice = (
        '<aside class="failure-notice"><div>'
        f"<strong>{heading}</strong><p>{_text(reason)}</p>"
        f'<p class="meta">Lote {_short_id_link(failed.get("batch_id"), "do lote com falha", "failed-batch-id")} · '
        f"{_text(_timestamp(failed.get('started_at')))} · "
        f"execução {_short_id_link(failed.get('run_id'), 'da execução com falha', 'failed-run-id')}</p>"
        "</div>" + _state_badge(failed.get("state")) + "</aside>"
    )
    heading = (
        "Registro do bloqueio ou falha desta tentativa"
        if latest
        else "Ver última falha ou bloqueio"
    )
    return (
        '<details class="previous-failure"><summary>'
        + heading
        + "</summary>"
        + notice
        + "</details>"
    )


def _decision(payload: ReportPayload) -> tuple[str, str, str]:
    """A decisão atual é o assunto; a publicação anterior é contexto de leitura."""
    attempt = payload.latest_attempt or {}
    state = attempt.get("state")
    same_run = bool(attempt.get("run_id")) and attempt.get("run_id") == (
        payload.snapshot or {}
    ).get("run_id")
    if attempt.get("audit_incomplete") or (same_run and state == "TECHNICAL_FAILURE"):
        return (
            "Publicado, com auditoria incompleta",
            "Os indicadores estão disponíveis. Confira o registro final da tentativa.",
            '<a class="decision-action" href="#attempt-identity">Conferir registro</a>',
        )
    if state == "BLOCKED":
        issues = [_mapping(item) for item in _sequence(attempt.get("issues"))]
        missing = next((item for item in issues if item.get("code") == "MISSING_FILE"), None)
        reason = (
            f"Falta receber {missing.get('file', 'o arquivo previsto')} da loja {missing.get('store_id', 'indicada no manifesto')}."
            if missing
            else "A entrega tem pendências que impedem publicar o fechamento."
        )
        guide = (
            "Confira o arquivo e a loja no manifesto da entrega. Reponha os bytes originais que faltam e reexecute o mesmo lote."
            if missing
            else "Confira a ocorrência e corrija os campos ou as revisões indicadas. Não reutilize o manifesto original para conteúdo diferente."
        )
        return (
            "Publicação bloqueada",
            reason,
            f'<a class="decision-action" href="#pendencias">Conferir pendência</a><details class="resume-guide"><summary>Como retomar</summary><p>{guide} Se o conteúdo contratado mudar, use novo batch_id e correction_of. O relatório não executa essa operação.</p></details>',
        )
    if state == "TECHNICAL_FAILURE":
        return (
            "Falha antes da publicação",
            "A tentativa foi interrompida. Confira o registro antes de reexecutar a entrada.",
            '<a class="decision-action" href="#attempt-identity">Conferir registro</a>',
        )
    if state == "RUNNING":
        return (
            "Execução sem resultado final",
            "O snapshot não informa a conclusão desta tentativa.",
            '<a class="decision-action" href="#attempt-identity">Conferir registro</a>',
        )
    if state == "NO_CHANGE":
        return (
            "Publicação mantida",
            "A entrada já foi aceita; os indicadores não mudaram.",
            '<a class="decision-action" href="#indicadores">Consultar indicadores</a>',
        )
    if state == "VALIDATED":
        return (
            "Entrega validada, sem publicação",
            "O registro informa validação, sem confirmar uma nova publicação.",
            '<a class="decision-action" href="#attempt-identity">Conferir registro</a>',
        )
    if state and state != "PUBLISHED":
        return (
            "Resultado da tentativa não reconhecido",
            "Consulte o estado original no registro da tentativa.",
            '<a class="decision-action" href="#attempt-identity">Conferir registro</a>',
        )
    if payload.snapshot is not None:
        return (
            "Fechamento publicado",
            "Confira os valores e a identidade da publicação em Indicadores.",
            '<a class="decision-action" href="#indicadores">Consultar indicadores</a>',
        )
    return (
        "Sem fechamento publicado",
        "Nenhuma tentativa foi capturada neste snapshot."
        if not payload.latest_attempt
        else "Consulte o registro para entender o resultado da entrega.",
        '<a class="decision-action" href="#attempt-identity">Conferir registro</a>'
        if payload.latest_attempt
        else "",
    )


PROFILE_STATES = {
    "NO_PUBLICATION": "Sem publicação para perfilar",
    "LEGACY": "Publicação legada sem perfil",
    "MISSING": "Perfil referenciado ausente",
    "INVALID": "Perfil inválido ou adulterado",
}
COMPARISON_STATES = {
    "NO_BASELINE": "Sem publicação anterior para comparação",
    "BASELINE_PROFILE_UNAVAILABLE": "Perfil da publicação anterior indisponível",
    "NOT_COMPARABLE": "Publicações sem recorte comparável",
    "EMPTY": "Recorte equivalente vazio",
    "INSUFFICIENT_SAMPLE": "Sem amostra suficiente",
    "COMPARABLE": "Comparação no mesmo recorte",
}
PROFILE_TOTALS = (
    ("active_lines", "Linhas ativas", "integer"),
    ("sales", "Vendas", "integer"),
    ("units", "Unidades", "integer"),
    ("net_revenue_brl", "Receita líquida", "money"),
    ("gross_revenue_brl", "Receita bruta", "money"),
    ("discount_brl", "Descontos", "money"),
)
PROFILE_DISTRIBUTIONS = {
    "quantity": "Quantidade por linha · unidades",
    "unit_price_brl": "Preço unitário · BRL",
    "line_discount_brl": "Desconto por linha · BRL",
}
PROFILE_RULES = {
    "quantity_mean": "Quantidade média por linha · unidades",
    "unit_price_mean_brl": "Preço médio por unidade antes dos descontos · BRL",
}
PROFILE_RULE_STATES = {
    "STABLE": "Dentro do limiar",
    "ZERO_BASELINE": "Valor anterior zero",
    "NOT_COMPARABLE": "Não comparável",
    "EMPTY": "Recorte vazio",
    "INSUFFICIENT_SAMPLE": "Sem amostra suficiente",
}


def _profile_totals(
    previous: Mapping[str, object], current: Mapping[str, object], *, label: str
) -> str:
    rows = []
    for key, name, kind in PROFILE_TOTALS:
        formatter = _money if kind == "money" else _integer
        rows.append(
            {
                "metric": name,
                "previous": formatter(previous.get(key)),
                "current": formatter(current.get(key)),
            }
        )
    return _table(
        rows,
        (
            ("metric", "Métrica", "text"),
            ("previous", "Anterior", "formatted_numeric"),
            ("current", "Atual", "formatted_numeric"),
        ),
        label=label,
        row_header=True,
    )


def _profile_date_range(value: object) -> str:
    dates = _mapping(value)
    if not dates or (dates.get("start") is None and dates.get("date_count") != 0):
        return "Período não informado"
    if dates.get("start") is None:
        return "Sem datas registradas"
    return (
        f"{_date(dates.get('start'))} a {_date(dates.get('end'))}"
        f" · {_integer(dates.get('date_count'))} {'dia registrado' if dates.get('date_count') == 1 else 'dias registrados'}"
    )


def _profile_context_change(value: object, *, unchanged: str, changed: str) -> str:
    return changed if value is True else unchanged if value is False else "Não informado"


def _profile_percentage(value: object) -> str:
    if value is None:
        return "—"
    amount = _decimal(value)
    if not amount.is_finite():
        return "—"
    with localcontext() as context:
        context.prec = max(60, len(amount.as_tuple().digits) + 4)
        percentage = amount * Decimal(100)
    return _exact_decimal(percentage) + "%"


def _profile_rule_cards(rules: Sequence[object]) -> str:
    ordered = sorted(
        (_mapping(item) for item in rules), key=lambda rule: rule.get("severity") != "WARNING"
    )
    parts = ['<ol class="profile-rule-list">']
    for index, rule in enumerate(ordered):
        metric = str(rule.get("metric"))
        state = (
            "Aviso de perfil (WARNING)"
            if rule.get("severity") == "WARNING"
            else PROFILE_RULE_STATES.get(str(rule.get("status")), str(rule.get("status")))
        )
        parts.append(
            f'<li class="profile-rule" data-profile-rule data-profile-metric="{_text(metric)}" data-severity="{_text(rule.get("severity"))}" aria-labelledby="profile-rule-{index}"><div class="profile-rule-heading"><h5 id="profile-rule-{index}">{_text(PROFILE_RULES.get(metric, metric))}</h5><p class="profile-rule-state">{_text(state)}</p></div><p class="profile-rule-reason">{_text(rule.get("reason"))}</p><dl class="profile-rule-values">'
        )
        for key, label in (
            ("previous", "Anterior"),
            ("current", "Atual"),
            ("difference", "Diferença"),
            ("relative_change", "Variação relativa"),
            ("threshold", "Limiar demonstrativo"),
        ):
            raw = rule.get(key)
            display = (
                _profile_percentage(raw)
                if key in {"relative_change", "threshold"}
                else _exact_decimal(raw)
            )
            raw_attribute = f' data-value-raw="{_text(raw)}"' if raw is not None else ""
            focus = (
                f' tabindex="0" role="region" aria-label="{_text(label)} completo"'
                if len(display) > 18
                else ""
            )
            parts.append(
                f'<div><dt>{label}</dt><dd class="numeric" data-profile-value="{key}"{raw_attribute}{focus}>{_text(display)}</dd></div>'
            )
        parts.append("</dl></li>")
    return "".join(parts) + "</ol>"


def _profile_comparison(
    comparison: Mapping[str, object], *, publication_id: object = None, date_range: object = None
) -> str:
    status = str(comparison.get("status", "NOT_COMPARABLE"))
    context = _mapping(comparison.get("context"))
    scope = _mapping(comparison.get("scope"))
    baseline = comparison.get("baseline_publication_id")
    count = comparison.get("warnings")
    count_known = type(count) is int and count >= 0
    count_attribute = f' data-profile-warning-count="{count}"' if count_known else ""
    state = COMPARISON_STATES.get(status, status)
    verdict = state
    if status == "COMPARABLE":
        verdict = (
            f"{count} {'aviso de perfil' if count == 1 else 'avisos de perfil'}"
            if count_known and count
            else "Sem avisos de perfil"
            if count_known
            else "Avisos de perfil não informados"
        )
    warning = status == "COMPARABLE" and count_known and bool(count)
    catalog_label = {
        "approved_operator_catalog": "Catálogo aprovado",
        "received_catalog_bytes": "Catálogo recebido",
    }.get(str(context.get("catalog_reference_origin")), "Catálogo de referência")
    parts = [
        '<div class="profile-comparison" id="profile-comparison" tabindex="-1">',
        f'<header class="profile-decision {"warning" if warning else "neutral"}" data-profile-comparison-state="{_text(status)}"{count_attribute}><h4 class="profile-verdict">{_text(verdict)}</h4>',
        f'<p class="profile-comparison-state">{_text(state)}</p>' if verdict != state else "",
        f'<p>{_text(comparison.get("reason"))}</p>' if comparison.get("reason") else "",
    ]
    if warning:
        parts.append(
            '<p class="profile-warning-note">Aviso para conferência. O fechamento continua publicado.</p>'
        )
    parts.append("</header>")
    if publication_id is not None:
        parts.append(
            '<p class="profile-publication">Publicação do perfil: '
            + _short_id_link(publication_id, "da publicação do perfil", "publication-id")
            + ".</p>"
        )
    if baseline is not None:
        parts.append(
            '<p class="profile-baseline">Comparada com a publicação '
            + _short_id_link(
                baseline,
                "da publicação comparada",
                "profile-baseline-id",
                section_label="Perfil e comparação",
            )
            + ".</p>"
        )
    previous_dates = context.get("previous_date_range")
    current_dates = context.get("current_date_range", date_range)
    fields = (
        [("Período anterior", _text(_profile_date_range(previous_dates)))]
        if baseline is not None
        else []
    )
    fields.append(("Período atual", _text(_profile_date_range(current_dates))))
    if baseline is not None:
        fields.extend(
            [
                (
                    "Datas registradas",
                    _text(
                        _profile_context_change(
                            context.get("dates_changed"),
                            unchanged="Mesmas datas",
                            changed="Mudaram",
                        )
                    ),
                ),
                (
                    catalog_label,
                    _text(
                        _profile_context_change(
                            context.get("catalog_changed"),
                            unchanged="Mesmo catálogo",
                            changed="Mudou",
                        )
                    ),
                ),
                (
                    "Cobertura histórica",
                    "Anterior: "
                    + _text(
                        _profile_context_change(
                            context.get("previous_scope_complete"),
                            unchanged="Parcialmente conhecida",
                            changed="Conhecida",
                        )
                    )
                    + "; atual: "
                    + _text(
                        _profile_context_change(
                            context.get("current_scope_complete"),
                            unchanged="Parcialmente conhecida",
                            changed="Conhecida",
                        )
                    ),
                ),
                (
                    "Lojas acrescentadas",
                    _chips(context.get("stores_added"), PROFILE_GROUP_LIMIT)
                    if isinstance(context.get("stores_added"), list | tuple)
                    else "Não informado",
                ),
                (
                    "Lojas removidas",
                    _chips(context.get("stores_removed"), PROFILE_GROUP_LIMIT)
                    if isinstance(context.get("stores_removed"), list | tuple)
                    else "Não informado",
                ),
            ]
        )
    parts.append(
        '<dl class="profile-context">'
        + "".join(f"<div><dt>{_text(label)}</dt><dd>{value}</dd></div>" for label, value in fields)
        + "</dl>"
    )
    if scope:
        parts.append(
            '<div class="profile-scope"><h4>Recorte equivalente</h4><p>'
            + _text(_profile_date_range(scope.get("dates")))
            + '</p><p class="meta">Interseção explícita das datas e lojas das duas publicações.</p><div class="chips" role="group" aria-label="Lojas do recorte equivalente">'
            + _chips(scope.get("stores"), PROFILE_GROUP_LIMIT)
            + "</div></div>"
        )
        dates = _mapping(scope.get("dates"))
        visible_dates = _sequence(dates.get("dates"))
        if isinstance(dates.get("dates"), list | tuple):
            parts.append(
                '<details class="data-detail"><summary>Datas do recorte equivalente</summary><div class="chips">'
                + _chips([_date(day) for day in visible_dates], PROFILE_GROUP_LIMIT)
                + '</div><p class="meta">'
                + (
                    "Lista de apresentação truncada; a comparação usa todas as datas da interseção."
                    if dates.get("dates_truncated") or len(visible_dates) > PROFILE_GROUP_LIMIT
                    else "Datas presentes nas duas versões Silver."
                )
                + "</p></details>"
            )
    rules = _sequence(comparison.get("rules"))[:PROFILE_QUANTILE_LIMIT]
    if rules:
        parts.append(
            '<h4>Regras explicáveis de comparação</h4><p class="meta">Limiares demonstrativos, configurados nesta publicação. A tabela completa conserva as razões decimais.</p>'
            + _profile_rule_cards(rules)
        )
        rule_rows = []
        for item in rules:
            rule = _mapping(item)
            rule_rows.append(
                {
                    "metric": PROFILE_RULES.get(str(rule.get("metric")), str(rule.get("metric"))),
                    "state": "Aviso (WARNING)"
                    if rule.get("severity") == "WARNING"
                    else PROFILE_RULE_STATES.get(str(rule.get("status")), str(rule.get("status"))),
                    **{
                        key: rule.get(key)
                        for key in (
                            "previous",
                            "current",
                            "difference",
                            "relative_change",
                            "threshold",
                            "reason",
                        )
                    },
                }
            )
        parts.append(
            '<details class="data-detail profile-rules-table"><summary>Tabela completa das regras</summary><p class="meta">Variação e limiar são razões: 0,20 corresponde a 20%.</p>'
            + _table(
                rule_rows,
                (
                    ("metric", "Métrica e unidade", "text"),
                    ("state", "Resultado", "text"),
                    ("previous", "Anterior", "decimal"),
                    ("current", "Atual", "decimal"),
                    ("difference", "Diferença", "decimal"),
                    ("relative_change", "Variação relativa (razão)", "decimal"),
                    ("threshold", "Limiar (razão)", "decimal"),
                    ("reason", "Motivo", "text"),
                ),
                label="Valores e motivos das regras no recorte equivalente",
                row_header=True,
            )
            + "</details>"
        )
    equivalent = _mapping(comparison.get("equivalent_totals"))
    if equivalent:
        parts.append(
            '<details class="data-detail"><summary>Totais no recorte equivalente</summary>'
            + _profile_totals(
                _mapping(equivalent.get("previous")),
                _mapping(equivalent.get("current")),
                label="Totais equivalentes nas versões Delta das duas publicações",
            )
            + "</details>"
        )
    original = _mapping(comparison.get("original_totals"))
    if original:
        parts.append(
            '<details class="data-detail"><summary>Totais originais dos dois históricos</summary><p class="meta">Cada histórico conserva seu período e composição. Estes totais não definem os avisos de variação.</p>'
            + _profile_totals(
                _mapping(original.get("previous")),
                _mapping(original.get("current")),
                label="Totais originais das publicações anterior e atual",
            )
            + "</details>"
        )
    if baseline is not None:
        parts.append(
            '<details class="data-detail profile-baseline-data"><summary>ID e versões da publicação comparada</summary>'
            + _copy_field(
                baseline,
                "Publicação anterior comparada",
                "profile-baseline-id",
                status_id="profile-copy-status",
            )
            + '<p id="profile-copy-status" class="copy-status" role="status" aria-live="polite"></p>'
            + _profile_versions(_mapping(comparison.get("baseline_delta_versions")))
            + "</details>"
        )
    return "".join(parts) + "</div>"


def _profile_versions(versions: Mapping[str, object]) -> str:
    return _table(
        [
            {
                "table": name,
                "version": _mapping(reference).get("version"),
                "path": _mapping(reference).get("path"),
            }
            for name, reference in list(versions.items())[:10]
        ],
        (
            ("table", "Tabela", "text"),
            ("version", "Versão Delta", "integer"),
            ("path", "Caminho registrado", "text"),
        ),
        label="Versões Delta fixadas no perfil",
        row_header=True,
    )


def _profile_details(profile: Mapping[str, object]) -> str:
    active = _mapping(profile.get("active_state"))
    totals = _mapping(active.get("totals"))
    rows = [
        {"metric": label, "value": (_money if kind == "money" else _integer)(totals.get(key))}
        for key, label, kind in PROFILE_TOTALS
    ]
    parts = [
        '<details class="data-detail"><summary>Perfil do estado ativo publicado</summary>',
        '<p class="meta">Silver ativa: maior revisão válida por item, operação UPSERT.</p>',
        _table(
            rows,
            (("metric", "Métrica", "text"), ("value", "Valor", "formatted_numeric")),
            label="Totais exatos do perfil ativo publicado",
            row_header=True,
        ),
    ]
    if active.get("cancelled_keys") is not None:
        parts.append(
            '<p class="meta">Itens com estado CANCEL na Silver: '
            + _text(_integer(active.get("cancelled_keys")))
            + ".</p>"
        )
    distributions = _mapping(active.get("distributions"))
    distribution_rows = []
    quantile_rows = []
    for key, label in PROFILE_DISTRIBUTIONS.items():
        values = _mapping(distributions.get(key))
        distribution_rows.append(
            {"metric": label, **{name: values.get(name) for name in ("min", "max", "mean")}}
        )
        for item in _sequence(values.get("quantiles"))[:PROFILE_QUANTILE_LIMIT]:
            quantile = _mapping(item)
            quantile_rows.append(
                {
                    "metric": label,
                    "probability": quantile.get("probability"),
                    "value": quantile.get("value"),
                }
            )
    parts.append(
        '<details class="data-detail profile-distributions"><summary>Distribuição das linhas ativas</summary>'
        + _table(
            distribution_rows,
            (
                ("metric", "Campo e unidade", "text"),
                ("min", "Mínimo", "decimal"),
                ("max", "Máximo", "decimal"),
                ("mean", "Média", "decimal"),
            ),
            label="Mínimos, máximos e médias das linhas ativas",
            row_header=True,
        )
        + "</details>"
    )
    parameters = _mapping(profile.get("parameters"))
    if quantile_rows:
        parts.append(
            '<details class="data-detail profile-quantiles"><summary>Quantis aproximados e precisão</summary><p class="meta">Quantis aproximados. Algoritmo: '
            + _text(parameters.get("quantile_algorithm"))
            + "; precisão configurada: "
            + _text(parameters.get("quantile_accuracy"))
            + ". A receita e os totais monetários são exatos.</p>"
            + _table(
                quantile_rows,
                (
                    ("metric", "Campo e unidade", "text"),
                    ("probability", "Probabilidade", "decimal"),
                    ("value", "Quantil aproximado", "decimal"),
                ),
                label="Quantis aproximados persistidos no perfil",
                row_header=True,
            )
            + "</details>"
        )
    groups = _mapping(active.get("groups"))
    for key, id_key, label in (
        ("stores", "store_id", "loja"),
        ("products", "product_id", "produto"),
    ):
        group = _mapping(groups.get(key))
        group_rows = [
            _mapping(item) for item in _sequence(group.get("values"))[:PROFILE_GROUP_LIMIT]
        ]
        parts.append(f"<h4>Contribuição por {label}</h4>")
        if group.get("truncated") or len(_sequence(group.get("values"))) > PROFILE_GROUP_LIMIT:
            parts.append(
                f'<p class="footnote">Exibindo {len(group_rows)} de {_text(_integer(group.get("group_count")))} grupos, com limite de apresentação de {PROFILE_GROUP_LIMIT}. Os totais e a comparação usam o conjunto completo.</p>'
            )
        parts.append(
            _table(
                group_rows,
                (
                    (id_key, label.capitalize(), "text"),
                    ("active_lines", "Linhas ativas", "integer"),
                    ("sales", "Vendas", "integer"),
                    ("units", "Unidades", "integer"),
                    ("net_revenue_brl", "Receita líquida", "money"),
                ),
                label=f"Contribuição publicada por {label}; grupos limitados",
                row_header=True,
            )
        )
    changes = _mapping(profile.get("state_changes"))
    if changes:
        parts.append(
            '<h4>Alterações do estado</h4><p class="meta">Origem: '
            + _text(
                {
                    "initial_silver_state": "Estado Silver da primeira publicação",
                    "compared_silver_versions": "Comparação das duas versões Silver",
                }.get(str(changes.get("origin")), str(changes.get("origin")))
            )
            + "</p>"
            + _table(
                [
                    {"metric": label, "value": changes.get(key)}
                    for key, label in (
                        ("new_keys", "Itens novos"),
                        ("revised_keys", "Itens revisados"),
                        ("cancelled_keys", "Itens cancelados"),
                        ("reactivated_keys", "Itens reativados"),
                        ("effective_changes", "Alterações efetivas"),
                    )
                ],
                (("metric", "Alteração", "text"), ("value", "Quantidade", "integer")),
                label="Alterações definidas pelo perfil",
                row_header=True,
            )
        )
    batch = _mapping(profile.get("batch"))
    if batch:
        stats = _mapping(batch.get("stats"))
        operations = _mapping(batch.get("received_operations"))
        parts.append(
            "<h4>Lote recebido nesta execução</h4>"
            + _table(
                [
                    {"metric": label, "value": source.get(key)}
                    for source, key, label in (
                        (stats, "received", "Registros recebidos"),
                        (stats, "valid", "Registros válidos"),
                        (stats, "rejected", "Registros rejeitados"),
                        (operations, "valid_cancel_events", "Eventos CANCEL válidos recebidos"),
                        (
                            operations,
                            "valid_revision_gt1_events",
                            "Eventos válidos com revisão maior que 1",
                        ),
                    )
                ],
                (("metric", "Métrica do lote", "text"), ("value", "Quantidade", "integer")),
                label="Contagens do lote recebido; separadas do estado ativo",
                row_header=True,
            )
        )
        if batch.get("received_operations_include_duplicates_and_stale"):
            parts.append(
                '<p class="meta">Contagem de operações sobre eventos recebidos, incluindo duplicatas e revisões antigas.</p>'
            )
        coverage = _mapping(batch.get("coverage"))
        if coverage:
            parts.append(
                '<dl class="profile-context">'
                + "".join(
                    "<div><dt>"
                    + label
                    + "</dt><dd>"
                    + _chips(coverage.get(key), PROFILE_GROUP_LIMIT)
                    + "</dd></div>"
                    for key, label in (
                        ("expected", "Lojas esperadas na entrega"),
                        ("received", "Lojas confirmadas na entrega"),
                        ("missing", "Lojas pendentes na entrega"),
                        ("zero_movement", "Zero confirmado na entrega"),
                    )
                )
                + "</dl>"
            )
    parts.append(
        '<p class="meta">Contrato '
        + _text(profile.get("contract_version"))
        + " · cálculo "
        + _text(profile.get("calculation_version"))
        + " · casas decimais das médias: "
        + _text(parameters.get("mean_decimal_places"))
        + ".</p>"
    )
    versions = _mapping(profile.get("delta_versions"))
    if versions:
        parts.append(
            '<details class="data-detail"><summary>Versões do perfil publicado</summary>'
            + _profile_versions(versions)
            + "</details>"
        )
    return "".join(parts) + "</details>"


def _profile_section(payload: ReportPayload) -> str:
    result = payload.profile_result or {}
    status = str(
        result.get("status", "MISSING" if (payload.snapshot or {}).get("profile") else "LEGACY")
    )
    profile = _mapping(result.get("profile"))
    if payload.snapshot is None:
        status = "NO_PUBLICATION"
    elif status == "AVAILABLE" and (
        profile.get("publication_id") != payload.snapshot.get("publication_id")
        or (
            payload.snapshot.get("run_id") is not None
            and profile.get("run_id") != payload.snapshot.get("run_id")
        )
    ):
        status = "INVALID"
    parts = [
        '<section class="data-section profile-section" id="perfil" tabindex="-1" aria-labelledby="profile-title"><h3 id="profile-title">Perfil e comparação de publicações</h3>'
    ]
    if status != "AVAILABLE":
        parts.append(
            '<p class="profile-state">' + _text(PROFILE_STATES.get(status, status)) + ".</p>"
        )
        if result.get("reason"):
            parts.append("<p>" + _text(result.get("reason")) + "</p>")
        guidance = {
            "LEGACY": "Este fechamento foi publicado antes do contrato de perfil. Seus valores e versões continuam disponíveis.",
            "MISSING": "Confira a referência do perfil e a cópia do estado com o responsável pelo fechamento. Os indicadores da publicação continuam disponíveis.",
            "INVALID": "O perfil não passou na conferência de contrato, hash ou vínculo. Confira a referência com o responsável pelo fechamento. Os indicadores da publicação continuam disponíveis.",
        }.get(status)
        if guidance:
            parts.append(
                '<p class="profile-guidance">'
                + _text(guidance)
                + ' <a href="#proveniencia">Conferir publicação e versões</a>.</p>'
            )
        return "".join(parts) + "</section>"
    coverage = _mapping(profile.get("coverage"))
    if coverage.get("scope_complete") is False:
        parts.append('<p class="audit-note">Cobertura histórica parcialmente conhecida.</p>')
    parts.append(
        _profile_comparison(
            _mapping(profile.get("comparison")),
            publication_id=profile.get("publication_id"),
            date_range=profile.get("date_range"),
        )
    )
    parts.append(_profile_details(profile))
    return "".join(parts) + "</section>"


def build_report_html(payload: ReportPayload) -> str:
    """Renderiza dados já capturados; nunca consulta armazenamento ou relógio."""
    snapshot = payload.snapshot or {}
    published = payload.snapshot is not None
    decision_title, decision_reason, decision_actions = _decision(payload)
    attempt = payload.latest_attempt or {}
    previous = (
        attempt.get("state") in {"BLOCKED", "TECHNICAL_FAILURE"}
        and attempt.get("run_id") != snapshot.get("run_id")
        and not attempt.get("audit_incomplete")
    )
    publication_label = (
        "Publicação anterior preservada"
        if previous and published
        else "Publicação disponível"
        if published
        else "Nenhuma publicação disponível"
    )
    summary = payload.summary
    window = (
        f"{_date(summary.get('first_date'))} a {_date(summary.get('last_date'))}"
        if published and summary.get("first_date") is not None
        else "Sem movimento publicado"
        if published and summary.get("sales_count") == 0
        else "Período não informado"
        if published
        else "Sem publicação disponível"
    )
    tables = _mapping(snapshot.get("tables"))
    versions = "".join(
        f'<tr><td><code>{_text(name)}</code><small>{_text(TABLE_GRAINS.get(name, ""))}</small></td><td class="numeric">'
        f"{_text(_mapping(ref).get('version'))}</td><td><code>"
        f"{_text(_mapping(ref).get('path'))}</code></td></tr>"
        for name, ref in tables.items()
    )
    cards = "".join(
        (
            _card(
                "Receita líquida",
                _money(summary.get("net_revenue_brl")) if published else "—",
                "BRL · descontos aplicados · cancelados excluídos",
                metric="net_revenue",
                accent=True,
            ),
            _card(
                "Unidades vendidas",
                _integer(summary.get("units")) if published else "—",
                f"{_integer(summary.get('item_lines'))} itens de venda ativos"
                if published and summary.get("item_lines") is not None
                else "Itens ativos não informados"
                if published
                else "Aguardando publicação",
                metric="units",
            ),
            _card(
                "Vendas",
                _integer(summary.get("sales_count")) if published else "—",
                "Distintas por loja e dia comercial",
                metric="sales_count",
            ),
            _card(
                "Ticket médio",
                _money(summary.get("average_ticket_brl"))
                if published and summary.get("average_ticket_brl") is not None
                else "—",
                "Sem vendas no período"
                if published and summary.get("sales_count") == 0
                else "Receita ÷ vendas no período",
                metric="average_ticket_brl",
            ),
        )
    )
    products = _table(
        payload.products,
        (
            ("product_id", "Produto", "text"),
            ("units", "Unidades", "integer"),
            ("net_revenue_brl", "Receita líquida", "money"),
        ),
        label="Produtos mais vendidos, unidades e receita líquida",
        row_header=True,
    )
    stores = _table(
        payload.stores,
        (
            ("business_date", "Dia comercial", "date"),
            ("store_id", "Loja", "text"),
            ("net_revenue_brl", "Receita líquida", "money"),
            ("units", "Unidades", "integer"),
            ("sales_count", "Vendas", "integer"),
            ("average_ticket_brl", "Ticket médio", "money"),
        ),
        label="Receita, unidades, vendas e ticket por loja e dia comercial",
        row_prefix="store-row",
    )
    daily_values = _table(
        payload.daily,
        (
            ("business_date", "Dia comercial", "date"),
            ("net_revenue_brl", "Receita líquida", "money"),
        ),
        label="Valores equivalentes ao gráfico de receita diária",
        row_header=True,
    )
    source_count = len(_sequence(snapshot.get("sources")))
    source_label = "fonte bronze" if source_count == 1 else "fontes bronze"
    publication_note = (
        f"Publicação {_short_id_link(snapshot.get('publication_id'), 'da publicação', 'publication-id')} · "
        f"{_text(_timestamp(snapshot.get('published_at')))}"
        if published
        else "Sem publicação."
    )
    daily_note = (
        f"Exibindo os primeiros {CHART_LIMIT} dias; totais dos cartões incluem todo o período."
        if payload.daily_truncated
        else "Dia comercial em America/Sao_Paulo."
    )
    product_note = (
        f"Primeiros {PRODUCT_LIMIT} produtos de um ranking maior."
        if payload.products_truncated
        else ""
    )
    store_note = (
        f"Exibindo os primeiros {TABLE_LIMIT} registros por dia e loja; os totais incluem todo o período."
        if payload.stores_truncated
        else ""
    )
    sources = "".join(
        '<details class="source-record"><summary>Fonte · '
        + _text(_mapping(source).get("batch_id"))
        + '</summary><dl class="source-fields"><dt>Execução</dt><dd><code>'
        + _text(_mapping(source).get("run_id"))
        + "</code></dd><dt>Caminho bronze</dt><dd><code>"
        + _text(_mapping(source).get("bronze_path"))
        + "</code></dd><dt>Versão bronze</dt><dd>"
        + _text(_mapping(source).get("bronze_version"))
        + '</dd></dl><div class="reference-hashes">'
        + "".join(
            f"<p><span>{_text(name)} · SHA-256</span><code>{_text(value)}</code></p>"
            for name, value in _mapping(_mapping(source).get("reference_hashes")).items()
        )
        + "</div></details>"
        for source in _sequence(snapshot.get("sources"))
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Entrega das lojas, diagnóstico da tentativa e indicadores do fechamento publicado.">
<title>Fechamento de vendas · Varejo Data Pipeline</title><link rel="icon" type="image/svg+xml" href="{FAVICON}"><style>{CSS}</style></head><body>
<a class="skip-link" href="#content">Ir para o fechamento</a>
<div class="app-shell"><header class="app-bar">
<a class="brand" href="#qualidade">{BRAND_MARK}<span>Varejo <span>Data Pipeline</span></span></a>
<nav class="report-nav" aria-label="Seções do relatório"><a href="#qualidade" data-view-link="qualidade">Execução</a><a href="#indicadores" data-view-link="indicadores">Indicadores</a><a href="#proveniencia" data-view-link="proveniencia">Arquivos</a></nav>
<span class="snapshot-label">Snapshot · somente leitura</span></header>
<main id="content" tabindex="-1">
<div class="report-caption"><h1>Conferência de fechamento</h1><p class="mobile-snapshot">Snapshot · somente leitura</p>{'<p class="demo-label">Demonstração com dados sintéticos.</p>' if payload.synthetic_data else ""}</div>
<section class="panel" id="qualidade" data-report-view tabindex="-1" aria-labelledby="execution-title">
<div class="closing-sheet">
<header class="decision-record" data-state="{_text(attempt.get("state", "UNKNOWN"))}"><div class="decision-copy"><h2 id="execution-title">{_text(decision_title)}</h2><p class="decision-reason">{_text(decision_reason)}</p><div class="decision-actions">{decision_actions}</div></div>
<div class="attempt-identity"><div><p class="record-label">Lote da tentativa</p><p class="batch-name">{_short_id_link(attempt.get("batch_id"), "do lote da tentativa", "attempt-batch-id")}</p></div><dl class="attempt-clock"><div><dt>Início registrado</dt><dd>{_text(_timestamp(attempt.get("started_at")))}</dd></div><div><dt>Período da entrega</dt><dd>Não informado no snapshot</dd></div></dl></div></header>
{_attempt_details(payload.latest_attempt)}
</div>
<div class="publication-bridge"><p><strong>{publication_label}.</strong> {_text(_publication_context(payload))}</p>{'<a href="#indicadores">Ver a publicação disponível</a>' if published else ''}</div>
{_failure_notice(payload)}</section>
<section class="panel" id="indicadores" data-report-view tabindex="-1" aria-labelledby="indicators-title">
<div class="publication-band"><header class="publication-heading"><h2 id="indicators-title">Indicadores de vendas</h2><p class="publication-window">{_text(window)}</p><p class="publication-note">{publication_note}</p></header>
<section class="metrics" aria-label="Indicadores da publicação">{cards}</section></div>
<p class="publication-context"><strong>{publication_label}.</strong> {_text(_publication_context(payload))}</p>
<nav class="subnav" aria-label="Recortes dos indicadores"><a href="#perfil">Perfil e comparação</a><a href="#lojas">Loja / dia</a><a href="#receita">Receita por dia</a><a href="#produtos">Produtos</a></nav>
{_profile_section(payload)}
<section class="data-section matrix-section" id="lojas" tabindex="-1"><h3>Receita por loja e dia</h3>{f'<p class="footnote">{store_note}</p>' if store_note else ""}{_store_matrix(payload.stores)}
<details class="data-detail" id="store-values" tabindex="-1"><summary>Valores por loja e dia ({len(payload.stores)} {"linha exibida" if len(payload.stores) == 1 else "linhas exibidas"})</summary>{stores}</details></section>
<div class="analytics-grid"><section id="receita" class="data-section" tabindex="-1"><div class="diagnostic-heading"><h3>Receita por dia</h3><span class="meta">BRL · dia comercial</span></div><div class="chart" tabindex="0" role="region" aria-label="Gráfico de receita por dia; rolagem horizontal disponível em telas estreitas">{_revenue_chart(payload.daily)}</div><p class="footnote">{daily_note}</p>
<details class="data-detail"><summary>Valores por dia ({len(payload.daily)} {"dia exibido" if len(payload.daily) == 1 else "dias exibidos"})</summary>{daily_values}</details></section>
<section class="data-section" id="produtos" tabindex="-1"><h3>Produtos mais vendidos</h3>
<p class="meta">Ordem: unidades, receita e ID. Cancelados excluídos.</p>{_product_ranking(payload.products)}{f'<p class="footnote">{product_note}</p>' if product_note else ""}<details class="data-detail"><summary>Valores por produto ({len(payload.products)})</summary>{products}</details></section></div></section>
<section class="panel" id="proveniencia" data-report-view tabindex="-1" aria-labelledby="files-title"><div class="section-head"><div><h2 id="files-title">Arquivos e versões</h2><p class="meta">{source_count} {source_label}. Referências capturadas no manifesto da publicação.</p><p class="meta">Publicada em {_text(_timestamp(snapshot.get("published_at")))}.</p></div></div>
<div class="provenance-workspace"><aside class="identity-register"><h3>Publicação identificada</h3>{_copy_field(snapshot.get("publication_id"), "ID da publicação", "publication-id")}{_copy_field(snapshot.get("run_id"), "Execução que publicou", "publication-run-id")}
<p id="copy-status" class="copy-status" role="status" aria-live="polite"></p>
<details class="identity-detail" id="attempt-identity" tabindex="-1"><summary>IDs da última tentativa</summary>
<p class=meta>Estado registrado: {_text((payload.latest_attempt or {}).get("state"))}</p>{_copy_field((payload.latest_attempt or {}).get("run_id"), "Execução da tentativa", "attempt-run-id")}
{_copy_field((payload.latest_attempt or {}).get("batch_id"), "Lote da tentativa", "attempt-batch-id")}</details>
<details class="identity-detail"><summary>IDs da última falha ou bloqueio</summary>
{_copy_field((payload.last_failed_attempt or {}).get("run_id"), "Execução com falha", "failed-run-id")}
{_copy_field((payload.last_failed_attempt or {}).get("batch_id"), "Lote com falha", "failed-batch-id")}</details>
</aside><div class="source-register"><h3 class="data-heading">Tabelas da publicação</h3><div class="table-scroll" tabindex="0" role="region" aria-label="Tabelas, versões e caminhos Delta"><table class="provenance"><thead><tr><th scope="col">Tabela e grão</th><th scope="col">Versão</th><th scope="col">Caminho Delta</th></tr></thead><tbody>{versions or '<tr><td colspan="3">Nenhuma versão publicada.</td></tr>'}</tbody></table></div>
<h3>Lotes publicados ({len(_sequence(snapshot.get("accepted_batches")))})</h3>
<div class="chips">{_chips(snapshot.get("accepted_batches"), len(_sequence(snapshot.get("accepted_batches"))))}</div>
<h3>Fontes e referências aprovadas</h3>{sources or '<p class="empty">Nenhuma fonte publicada.</p>'}
<p class="footnote">Use <code>explain</code> para consultar chaves, revisões e arquivos de uma amostra.</p></div></div></section>
<footer class="report-footer"><span>Varejo Data Pipeline · relatório local, sem atualização automática</span><details class="font-notice"><summary>Licença da fonte</summary><pre>{FONT_NOTICE}</pre></details></footer>
</main></div><script>{SCRIPT}</script></body></html>"""

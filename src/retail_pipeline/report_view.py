from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext
from html import escape
from importlib.resources import files

from retail_pipeline.report_model import CHART_LIMIT, PRODUCT_LIMIT, TABLE_LIMIT, ReportPayload

CSS = files("retail_pipeline").joinpath("report.css").read_text(encoding="utf-8")
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
    amount = _decimal(value)
    with localcontext() as context:
        context.prec = max(38, amount.adjusted() + 4)
        rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    numeric = f"{rounded:,.2f}"
    return "R$ " + numeric.translate(str.maketrans(",.", ".,"))


def _integer(value: object) -> str:
    return f"{int(str(value or 0)):,}".replace(",", ".")


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


def _card(label: str, value: str, note: str, *, accent: bool = False) -> str:
    css = "metric accent" if accent else "metric"
    return (
        f'<article class="{css}"><p class="eyebrow">{_text(label)}</p>'
        f"<strong>{_text(value)}</strong><p>{_text(note)}</p></article>"
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


def _copy_field(value: object, label: str, field_id: str) -> str:
    if value is None:
        return f'<p class="meta">{_text(label)}: indisponível.</p>'
    return (
        f'<div class="copy-field"><label for="{field_id}">{_text(label)}</label>'
        f'<div><input id="{field_id}" value="{_text(value)}" readonly spellcheck="false">'
        f'<button type="button" hidden data-copy-target="{field_id}" aria-label="Copiar {_text(label)}">Copiar</button></div></div>'
    )


def _short_id_link(value: object, label: str, field_id: str = "proveniencia") -> str:
    if value is None:
        return "—"
    full = str(value)
    short = full if len(full) <= 16 else full[:8] + "…" + full[-4:]
    return f'<a class="id-link" href="#{_text(field_id)}" aria-label="Ver ID completo {_text(label)} em Arquivos e versões">{_text(short)}</a>'


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
    width, left, right, top, bottom = 900, 110, 20, 20, 210
    plot_width = width - left - right
    values = [_decimal(row.get("net_revenue_brl")) for row in rows]
    step, intervals = _axis_scale(max(values))
    ceiling = step * intervals
    points: list[str] = []
    grid: list[str] = []
    for index in range(intervals + 1):
        y = top + (bottom - top) * index // intervals
        label = _axis_money(step * (intervals - index))
        grid.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y}" y2="{y}" '
            f'stroke="#dae2ec"/><text x="{left - 12}" y="{y + 4}" '
            f'text-anchor="end" class="chart-label">{_text(label)}</text>'
        )
    for index, value in enumerate(values):
        x = left + (
            plot_width // 2 if len(values) == 1 else plot_width * index // (len(values) - 1)
        )
        y = bottom - int(value / ceiling * (bottom - top))
        points.append(f"{x},{y}")
    ticks = sorted({0, len(rows) // 2, len(rows) - 1})
    labels = "".join(
        f'<text x="{points[index].split(",")[0]}" '
        f'y="240" text-anchor="{"end" if index == len(rows) - 1 else "middle"}" class="chart-label">'
        f"{_text(_date(rows[index].get('business_date')))}</text>"
        for index in ticks
    )
    area = f"{left},{bottom} " + " ".join(points) + f" {points[-1].split(',')[0]},{bottom}"
    dots = "".join(
        f'<circle cx="{point.split(",")[0]}" cy="{point.split(",")[1]}" '
        f'r="4" fill="#185c91"><title>{_text(_date(row.get("business_date")))}: '
        f"{_text(_money(row.get('net_revenue_brl')))}</title></circle>"
        for point, row in zip(points, rows, strict=True)
    )
    return (
        '<svg viewBox="0 0 900 260" role="img" '
        'aria-label="Receita líquida por dia comercial, em reais">'
        "<title>Receita líquida por dia comercial</title>"
        + "".join(grid)
        + (f'<polygon points="{area}" fill="#e4eef8"/>' if len(rows) > 1 else "")
        + f'<polyline points="{" ".join(points)}" fill="none" '
        'stroke="#185c91" stroke-width="3" stroke-linejoin="round"/>' + dots + labels + "</svg>"
    )


def _table(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[tuple[str, str, str]],
    *,
    label: str = "Tabela de indicadores publicados",
) -> str:
    if not rows:
        return '<p class="empty">Sem registros neste recorte.</p>'
    head = "".join(f'<th scope="col">{_text(label)}</th>' for _, label, _ in columns)
    body: list[str] = []
    for row in rows:
        cells = []
        for key, _, kind in columns:
            value = row.get(key)
            if kind == "money":
                display = _money(value)
            elif kind == "integer":
                display = _integer(value)
            elif kind == "date":
                display = _date(value)
            else:
                display = str(value) if value is not None else "—"
            css = ' class="numeric"' if kind in {"money", "integer"} else ""
            cells.append(f"<td{css}>{_text(display)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<div class="table-scroll" tabindex="0" role="region" aria-label="{_text(label)}"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _coverage_panel(coverage: Mapping[str, object]) -> str:
    expected = set(map(str, _sequence(coverage.get("expected"))))
    received = set(map(str, _sequence(coverage.get("received"))))
    missing = sorted(expected - received)
    unexpected = sorted(received - expected)
    summary = (
        f"{len(expected & received)} de {len(expected)} lojas com entrega confirmada"
        if expected
        else "Expectativa de lojas indisponível"
    )
    exceptions = ""
    for values, label in ((missing, "Lojas ausentes"), (unexpected, "Lojas não esperadas")):
        if values:
            exceptions += (
                f'<p class="coverage-exception"><strong>{label}:</strong> {_chips(values)}</p>'
            )
    rows = "".join(
        f"<div><dt>{label} ({len(_sequence(coverage.get(key)))})</dt><dd>{_chips(coverage.get(key), len(_sequence(coverage.get(key))))}</dd></div>"
        for key, label in (
            ("expected", "Esperadas"),
            ("received", "Recebidas"),
            ("zero_movement", "Zero movimento confirmado"),
        )
    )
    return (
        f'<div class="coverage-summary"><h3>Cobertura da entrega</h3><p class="coverage-total">{summary}</p>{exceptions}'
        f'<details><summary>Ver lojas</summary><dl class="coverage">{rows}</dl></details></div>'
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
        '<div class="issues" aria-label="Motivos da decisão, severidade e ocorrências">'
        f"{''.join(rows)}{f'<details class=related-issues><summary>Ocorrências relacionadas ({len(related)})</summary>{chr(10).join(related)}</details>' if related else ''}</div>{note}"
    )


def _attempt_details(attempt: Mapping[str, object] | None) -> str:
    if attempt is None:
        return '<h2>Execução</h2><div class="empty-state"><h3>Nenhuma tentativa registrada.</h3><p>O relatório mostrará a entrega, as etapas medidas e o diagnóstico quando houver um registro.</p></div>'
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
    <div class="section-head run-heading"><div><p class="eyebrow">Última tentativa</p><h2>Conferência da entrega</h2>
    <p class="meta">Lote {_short_id_link(attempt.get("batch_id"), "do lote da tentativa", "attempt-batch-id")} <span aria-hidden="true">·</span> {_text(_timestamp(attempt.get("started_at")))}</p></div><a class="run-record" href="#attempt-identity">Ver registro da tentativa ↗</a></div>
    <div class="execution-workspace"><div class="attempt-diagnostics">
    <div class="diagnostic-section" id="pendencias" tabindex="-1"><h3>Ocorrências da entrega</h3>{issue_html}</div>
    <details class="delivery-coverage"><summary>Cobertura e lojas da entrega</summary>{_coverage_panel(_mapping(attempt.get("coverage")))}</details>
    <details class="quality-measurements"><summary>Contadores e validações técnicas</summary>
    <div class="quality-outcome {"has-rejections" if problem else ""}">
      <p><strong>{rejected} {"rejeitado" if stats.get("rejected") == 1 else "rejeitados"}</strong> de {received} {"registro recebido" if stats.get("received") == 1 else "registros recebidos"}</p><p>{violations} violações de registros</p>
    </div>{_quality_diagnostics(attempt)}</details>
    </div><aside class="delivery-context" aria-label="Medições da tentativa">{_duration_panel(attempt)}</aside></div>
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
            "Os indicadores pertencem à publicação identificada abaixo.",
            '<a class="decision-action" href="#indicadores">Consultar indicadores</a>',
        )
    return (
        "Sem fechamento publicado",
        "Consulte a tentativa para entender o resultado da entrega.",
        '<a class="decision-action" href="#qualidade">Consultar tentativa</a>',
    )


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
                accent=True,
            ),
            _card(
                "Unidades vendidas",
                _integer(summary.get("units")) if published else "—",
                f"{_integer(summary.get('item_lines'))} itens de venda ativos"
                if published
                else "Aguardando publicação",
            ),
            _card(
                "Vendas",
                _integer(summary.get("sales_count")) if published else "—",
                "Distintas por loja e dia comercial",
            ),
            _card(
                "Ticket médio",
                _money(summary.get("average_ticket_brl"))
                if published and summary.get("average_ticket_brl") is not None
                else "—",
                "Sem vendas no período"
                if published and not summary.get("sales_count")
                else "Receita ÷ vendas no período",
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
    )
    daily_values = _table(
        payload.daily,
        (
            ("business_date", "Dia comercial", "date"),
            ("net_revenue_brl", "Receita líquida", "money"),
        ),
        label="Valores equivalentes ao gráfico de receita diária",
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
<title>Fechamento de vendas · Varejo Data Pipeline</title><style>{CSS}</style></head><body>
<a class="skip-link" href="#content">Ir para o fechamento</a>
<div class="app-shell"><header class="app-bar">
<a class="brand" href="#qualidade"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 5h8v8H5zM19 19h8v8h-8zM19 5h8v8h-8z"/><path d="M13 9h6M23 13v6" fill="none"/></svg><span>Varejo <span>Data Pipeline</span></span></a>
<span class="app-location">Operação de dados / Vendas</span><span class="snapshot-label">Snapshot · somente leitura</span></header>
<main id="content" tabindex="-1"><header class="page-heading"><div><p class="eyebrow">FECHAMENTO DE VENDAS / ÚLTIMA TENTATIVA</p><h1>{_text(decision_title)}</h1><p class="decision-reason">{_text(decision_reason)}</p><div class="decision-actions">{decision_actions}</div></div>
{'<p class="demo-label">Demonstração com dados sintéticos.</p>' if payload.synthetic_data else ""}</header>
<section class="publication-overview" aria-label="Publicação atual"><div><p class="eyebrow">{publication_label}</p><p class="publication-id">{publication_note}</p></div>
<div class="publication-window"><p class="eyebrow">Janela comercial</p><p class="window">{_text(window)}</p></div>
</section>
<p class="publication-context">{_text(_publication_context(payload))}</p>
<nav class="report-nav" aria-label="Seções do relatório"><a href="#qualidade" data-view-link="qualidade"><span aria-hidden="true">01</span>Execução</a><a href="#indicadores" data-view-link="indicadores"><span aria-hidden="true">02</span>Indicadores</a><a href="#proveniencia" data-view-link="proveniencia"><span aria-hidden="true">03</span>Arquivos</a></nav>
<section class="panel" id="qualidade" data-report-view tabindex="-1">{_attempt_details(payload.latest_attempt)}{_failure_notice(payload)}</section>
<section class="panel" id="indicadores" data-report-view tabindex="-1"><div class="section-head"><div><p class="eyebrow">Publicação vigente</p><h2>Indicadores de vendas</h2></div>
<span class="window">{_text(window)}</span></div><nav class="subnav" aria-label="Recortes dos indicadores"><a href="#receita">Receita por dia</a><a href="#produtos">Produtos</a><a href="#lojas">Loja / dia</a></nav>
<section class="metrics" aria-label="Indicadores da publicação">{cards}</section><div class="analytics-grid"><section id="receita" class="data-section" tabindex="-1"><div class="diagnostic-heading"><h3>Receita por dia</h3><span class="meta">BRL · dia comercial</span></div><div class="chart" tabindex="0" role="region" aria-label="Gráfico de receita por dia; rolagem horizontal disponível em telas estreitas">{_revenue_chart(payload.daily)}</div><p class="footnote">{daily_note}</p>
<details class="data-detail"><summary>Valores por dia ({len(payload.daily)} {"dia exibido" if len(payload.daily) == 1 else "dias exibidos"})</summary>{daily_values}</details></section>
<section class="data-section" id="produtos" tabindex="-1"><h3>Produtos mais vendidos</h3>
<p class="meta">Ordem: unidades, receita e ID. Cancelados excluídos.</p>{products}{f'<p class="footnote">{product_note}</p>' if product_note else ""}</section></div>
<section class="data-section" id="lojas" tabindex="-1"><h3>Receita por loja e dia</h3>{f'<p class="footnote">{store_note}</p>' if store_note else ""}
<details class="data-detail"><summary>Valores por loja e dia ({len(payload.stores)} {"linha exibida" if len(payload.stores) == 1 else "linhas exibidas"})</summary>{stores}</details></section></section>
<section class="panel" id="proveniencia" data-report-view tabindex="-1"><div class="section-head"><div><p class="eyebrow">Rastreabilidade</p><h2>Arquivos e versões</h2><p class="meta">{source_count} {source_label}. Referências capturadas no manifesto da publicação.</p></div></div>
<div class="provenance-workspace"><aside class="identity-register"><h3>Identificação</h3>{_copy_field(snapshot.get("publication_id"), "ID da publicação", "publication-id")}{_copy_field(snapshot.get("run_id"), "Execução que publicou", "publication-run-id")}
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
<footer class="report-footer"><span>Varejo Data Pipeline</span><span>Relatório local · sem atualização automática</span></footer>
</main></div><script>{SCRIPT}</script></body></html>"""

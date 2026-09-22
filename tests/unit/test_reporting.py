import re
from decimal import Decimal
from pathlib import Path

import pytest

from retail_pipeline.report_model import ReportPayload
from retail_pipeline.report_view import build_report_html
from retail_pipeline.reporting import _read_published_tables


def _summary_values(page: str) -> dict[str, str]:
    return dict(re.findall(r'data-metric="([^"]+)">([^<]*)<', page))


@pytest.mark.parametrize("reverse", [False, True])
def test_missing_delivery_keeps_related_record_without_repeating_primary_incident(
    reverse: bool,
) -> None:
    attempt = {
        "state": "BLOCKED",
        "run_id": "missing-file",
        "stages": {"ingestion": 3.1185},
        "stats": {"received": 3, "rejected": 0, "violations": 0},
        "issues": [
            {"code": "MISSING_FILE", "store_id": "S02", "file": "S02.csv", "severity": "ERROR"},
            {"code": "MISSING_STORE", "store_id": "S02", "severity": "ERROR"},
        ],
    }
    if reverse:
        attempt["issues"].reverse()
    page = build_report_html(ReportPayload(snapshot={"run_id": "previous"}, latest_attempt=attempt))
    assert '<h2 id="execution-title">Publicação bloqueada</h2>' in page
    assert "Falta receber S02.csv da loja S02." in page
    assert 'href="#pendencias">Conferir pendência' in page
    assert "Publicação anterior preservada" in page
    assert "Arquivo não recebido" in page
    assert "Ocorrências relacionadas (1)" in page
    assert "MISSING_STORE" in page and "MISSING_FILE" in page
    assert "0 rejeitados</strong> de 3 registros recebidos" in page
    assert "stage-inspector" not in page and "dominant-stage" not in page
    assert "3,1185 s" in page
    assert (
        '<details class="issue error" open><summary><span class="issue-title">Arquivo não recebido'
        in page
    )


def test_missing_store_without_identity_is_not_grouped_by_missing_identity() -> None:
    page = build_report_html(
        ReportPayload(
            latest_attempt={
                "state": "BLOCKED",
                "issues": [
                    {"code": "MISSING_FILE"},
                    {"code": "MISSING_STORE"},
                ],
            }
        )
    )
    assert "Ocorrências relacionadas" not in page
    assert "Arquivo não recebido" in page and "Loja sem entrega confirmada" in page


def test_truncated_missing_file_does_not_hide_visible_store_issues() -> None:
    page = build_report_html(
        ReportPayload(
            latest_attempt={
                "state": "BLOCKED",
                "issues": [
                    *[{"code": "MISSING_STORE", "store_id": "S02"} for _ in range(50)],
                    {"code": "MISSING_FILE", "store_id": "S02"},
                ],
            }
        )
    )
    assert "Nenhuma ocorrência registrada" not in page
    assert "Exibindo 50 de 51 ocorrências" in page
    assert "Loja sem entrega confirmada" in page


@pytest.mark.parametrize(
    "state,title",
    [
        ("VALIDATED", "Entrega validada, sem publicação"),
        ("UNRECOGNIZED", "Resultado da tentativa não reconhecido"),
    ],
)
def test_inconclusive_attempt_does_not_inherit_published_success(state: str, title: str) -> None:
    page = build_report_html(
        ReportPayload(snapshot={"run_id": "previous"}, latest_attempt={"state": state})
    )
    assert f'<h2 id="execution-title">{title}</h2>' in page
    assert "<h1>Fechamento publicado</h1>" not in page
    assert f"Estado registrado: {state}" in page


def test_report_escapes_source_content_in_all_display_regions() -> None:
    hostile = '<img src=x onerror="alert(1)"> & origem'
    attempt = {
        "run_id": hostile,
        "batch_id": hostile,
        "state": "BLOCKED",
        "started_at": "2026-09-20T12:00:00+00:00",
        "duration_seconds": 2.25,
        "stats": {"received": 4, "valid": 3, "rejected": 1, "violations": 3},
        "coverage": {"expected": [hostile], "received": [], "missing": [hostile]},
        "issues": [{"code": hostile, "severity": "ERROR", "message": hostile}],
        "stages": {hostile: 1.5},
    }
    html = build_report_html(
        ReportPayload(
            snapshot={
                "publication_id": hostile,
                "run_id": hostile,
                "tables": {hostile: {"path": hostile, "version": 1}},
                "accepted_batches": [hostile],
                "sources": [],
            },
            latest_attempt=attempt,
            last_failed_attempt=attempt,
            products=[{"product_id": hostile, "units": 1, "net_revenue_brl": Decimal("12.50")}],
            stores=[{"store_id": hostile}],
        )
    )
    assert hostile not in html
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; origem" in html
    assert "25,00%" in html
    assert "Tentativa sem publicação" in html
    assert "R$ 12,50" in html


def test_report_keeps_current_publication_separate_from_failed_attempt() -> None:
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "pub-valid", "run_id": "run-good"},
            latest_attempt={"batch_id": "batch-retry", "run_id": "retry", "state": "NO_CHANGE"},
            last_failed_attempt={
                "batch_id": "batch-bad",
                "run_id": "bad",
                "state": "TECHNICAL_FAILURE",
            },
            summary={
                "net_revenue_brl": Decimal("90071992547409.91"),
                "units": 7,
                "sales_count": 3,
                "average_ticket_brl": Decimal("21.333333"),
                "first_date": "2026-01-01",
                "last_date": "2026-01-30",
            },
            daily_truncated=True,
            stores_truncated=True,
            products_truncated=True,
        )
    )
    assert "pub-valid" in html
    assert "batch-retry" in html
    assert "batch-bad" in html
    assert "Última falha ou bloqueio" in html
    assert "R$ 90.071.992.547.409,91" in html
    assert "R$ 21,33" in html
    assert "01/01/2026 a 30/01/2026" in html
    assert "primeiros 366 dias" in html
    assert "primeiros 500 registros" in html
    assert "Primeiros 20 produtos" in html


def test_report_is_self_contained_and_handles_empty_publication() -> None:
    html = build_report_html(ReportPayload())
    assert '<html lang="pt-BR">' in html
    assert "Demonstração com dados sintéticos." not in html
    assert "Demonstração com dados sintéticos." in build_report_html(
        ReportPayload(synthetic_data=True)
    )
    assert "Sem publicação" in html
    assert "Nenhuma tentativa registrada" in html
    assert list(_summary_values(html).values()).count("—") == 4
    assert "Sem publicação disponível" in html
    assert "Aguardando publicação" in html
    assert "R$ 0,00" not in html
    assert "0 itens de venda ativos" not in html
    assert html.count("<script>") == 1
    assert "<script src=" not in html
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_chart_contains_observed_dates_and_values_without_float_money() -> None:
    html = build_report_html(
        ReportPayload(
            daily=[
                {"business_date": "2026-01-01", "net_revenue_brl": Decimal("0.10")},
                {"business_date": "2026-01-02", "net_revenue_brl": Decimal("0.20")},
            ]
        )
    )
    assert "01/01/2026: R$ 0,10" in html
    assert "02/01/2026: R$ 0,20" in html
    assert '<svg viewBox="0 0 900 260"' in html


def test_reader_captures_pointer_once_even_when_it_changes_between_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from retail_pipeline import publication

    first = {"publication_id": "published-before-read"}
    second = {"publication_id": "published-during-read"}
    current = first
    pointer_reads = 0
    references = []

    def load_pointer(root):
        nonlocal pointer_reads
        pointer_reads += 1
        return current

    def read_version(spark, snapshot, name):
        nonlocal current
        references.append((name, snapshot))
        current = second
        return name

    monkeypatch.setattr(publication, "load_snapshot", load_pointer)
    monkeypatch.setattr(publication, "read_table", read_version)
    snapshot, frames = _read_published_tables(
        None, Path("/data/example"), ("gold_store_day", "gold_product_day")
    )
    assert pointer_reads == 1
    assert snapshot is first
    assert current is second
    assert all(reference is first for _, reference in references)
    assert set(frames) == {"gold_store_day", "gold_product_day"}


def test_technical_stack_trace_stays_out_of_the_reader_message() -> None:
    attempt = {
        "run_id": "run-failed",
        "state": "TECHNICAL_FAILURE",
        "issues": [
            {
                "code": "TECHNICAL_FAILURE",
                "severity": "ERROR",
                "message": "Py4JJavaError: detailed backend exception\n at org.internal.Foo.bar(Foo.java:42)",
            }
        ],
    }
    html = build_report_html(ReportPayload(latest_attempt=attempt, last_failed_attempt=attempt))
    assert "Py4JJavaError" not in html
    assert "org.internal" not in html
    assert "Consulte os detalhes da tentativa" in html


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        (["INFO", "WARNING", "ERROR"], "ERROR"),
        (["INFO", "WARNING"], "WARNING"),
        (["INFO"], "INFO"),
    ],
)
def test_failure_banner_prioritizes_the_blocking_reason_over_earlier_information(
    severities: list[str], expected: str
) -> None:
    attempt = {
        "run_id": "run-with-mixed-issues",
        "state": "BLOCKED",
        "issues": [
            {"code": f"CODE_{severity}", "severity": severity, "message": f"Motivo {severity}"}
            for severity in severities
        ],
    }
    html = build_report_html(ReportPayload(latest_attempt=attempt, last_failed_attempt=attempt))
    banner = html.split('<aside class="failure-notice">', 1)[1].split("</aside>", 1)[0]
    assert f"<p>Motivo {expected}</p>" in banner
    for severity in set(severities) - {expected}:
        assert f"Motivo {severity}" not in banner


def test_stage_labels_and_quality_codes_without_messages_have_portuguese_descriptions() -> None:
    attempt = {
        "state": "BLOCKED",
        "run_id": "missing-file",
        "stages": {"publication": 0.1, "reconciliation": 2.0, "ingestion": 1.0},
        "issues": [
            {"code": "MISSING_FILE", "severity": "ERROR", "file": "loja-02.csv", "store_id": "L02"},
            {"code": "INVALID_QUANTITY", "severity": "ERROR", "count": 3},
        ],
    }
    html = build_report_html(ReportPayload(latest_attempt=attempt, last_failed_attempt=attempt))
    assert "<td>Ingestão</td>" in html
    assert "<td>Reconciliação</td>" in html
    assert "<td>Publicação</td>" in html
    assert html.index("<td>Ingestão</td>") < html.index("<td>Reconciliação</td>")
    assert html.index("<td>Reconciliação</td>") < html.index("<td>Publicação</td>")
    assert "Arquivo do manifesto não recebido." in html
    assert "loja: L02; arquivo: loja-02.csv" in html
    assert "Quantidade deve ser um inteiro positivo" in html
    assert "ocorrências: 3" in html
    assert '<span class="severity">Erro</span>' in html


@pytest.mark.parametrize("revision_checks_executed", [0, 1, None])
def test_unexecuted_revision_checks_are_not_presented_as_zero_counts(
    revision_checks_executed: int | None,
) -> None:
    stats = {"received": 10, "valid": 10, "duplicates": 2, "conflicts": 3, "stale": 4}
    if revision_checks_executed is not None:
        stats["revision_checks_executed"] = revision_checks_executed
    attempt = {"state": "BLOCKED", "run_id": "blocked-before-quality", "stats": stats}
    html = build_report_html(ReportPayload(latest_attempt=attempt))
    assert "<dt>Recebidos</dt><dd>10</dd>" in html
    if revision_checks_executed == 0:
        assert html.count("Não avaliado") == 3
        assert "Validação de revisões não executada por bloqueio anterior." in html
        assert "<dt>Conflitos</dt><dd>3</dd>" not in html
    else:
        assert "Não avaliado" not in html
        assert "<dt>Duplicatas exatas</dt><dd>2</dd>" in html
        assert "<dt>Conflitos</dt><dd>3</dd>" in html
        assert "<dt>Revisões antigas</dt><dd>4</dd>" in html


def test_report_rounds_half_cent_up_to_match_spark_decimal_cast() -> None:
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "pub-rounding"},
            summary={"average_ticket_brl": Decimal("1.005")},
        )
    )
    assert "R$ 1,01" in html
    assert "R$ 1,00" not in html


def test_published_zero_movement_keeps_real_zero_indicators() -> None:
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "pub-zero"},
            summary={
                "net_revenue_brl": Decimal("0.00"),
                "units": 0,
                "item_lines": 0,
                "sales_count": 0,
                "average_ticket_brl": None,
            },
        )
    )
    assert list(_summary_values(html).values()).count("R$ 0,00") == 1
    assert "Sem vendas no período" in html
    assert list(_summary_values(html).values()).count("—") == 1
    assert list(_summary_values(html).values()).count("0") == 2
    assert "0 itens de venda ativos" in html
    assert "Sem movimento publicado" in html
    assert "Sem publicação disponível" not in html


def test_unfinished_attempt_is_not_success_or_a_zero_measurement() -> None:
    html = build_report_html(ReportPayload(latest_attempt={"state": "RUNNING", "stats": {}}))
    assert '<h2 id="execution-title">Execução sem resultado final</h2>' in html
    assert "<dt>Recebidos</dt><dd>—</dd>" in html
    assert "Execução sem resultado final" in html
    assert '<span class="badge success">' not in html


def test_chart_has_equivalent_table_and_localized_operational_metadata() -> None:
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "p", "sources": [{}]},
            latest_attempt={
                "state": "PUBLISHED",
                "duration_seconds": 50.53,
                "stages": {"ingestion": 1.234},
            },
            daily=[{"business_date": "2026-01-03", "net_revenue_brl": Decimal("21.34")}],
            stores=[{"store_id": "S01"}],
        )
    )
    assert "1 fonte bronze" in html
    assert "50,53 s" in html and "1,234 s" in html
    assert "Valores equivalentes ao gráfico de receita diária" in html
    assert '<td>03/01/2026</td><td class="numeric">R$ 21,34</td>' in html
    assert "<summary>Valores por loja e dia (1 linha exibida)</summary>" in html


@pytest.mark.parametrize(
    "amount,labels",
    [
        ("39783.51", ["R$ 0,00", "R$ 10 mil", "R$ 20 mil", "R$ 30 mil", "R$ 40 mil"]),
        ("0.01", ["R$ 0,00", "R$ 0,01"]),
        ("0.00", ["R$ 0,00", "R$ 0,50"]),
    ],
)
def test_chart_uses_readable_ticks_without_changing_exact_values(
    amount: str, labels: list[str]
) -> None:
    html = build_report_html(
        ReportPayload(daily=[{"business_date": "2026-01-01", "net_revenue_brl": Decimal(amount)}])
    )
    svg = html.split('<svg viewBox="0 0 900 260"', 1)[1].split("</svg>", 1)[0]
    for label in labels:
        assert label in svg
    assert "01/01/2026: R$ " in svg
    assert "Valores equivalentes ao gráfico" in html


def test_quality_precedes_indicators_and_coverage_keeps_exceptions_visible() -> None:
    attempt = {
        "state": "BLOCKED",
        "batch_id": "a" * 32,
        "stats": {"received": 1, "rejected": 1, "violations": 4},
        "coverage": {"expected": ["S01", "S02"], "received": ["S01", "S99"], "missing": ["S02"]},
        "stages": {"ingestion": 0.025, "quality": 3.2345},
        "duration_seconds": 3.2595,
    }
    html = build_report_html(ReportPayload(latest_attempt=attempt))
    assert html.index('id="qualidade"') < html.index('id="indicadores"')
    assert 'role="tab' not in html
    assert "Seções do relatório" in html
    assert "1 rejeitado</strong> de 1 registro recebido" in html
    assert 'class="stage-name">Qualidade</span>' in html
    assert "3,2 s" in html and "3,2345 s" in html
    coverage = html.split("Cobertura da entrega", 1)[1].split("<details>", 1)[0]
    assert "S02" in coverage and "S99" in coverage
    assert "1 de 2 lojas" in coverage
    before_provenance = html.split('<section class="panel" id="proveniencia"', 1)[0]
    assert "a" * 32 not in before_provenance
    assert "aaaaaaaa…aaaa" in before_provenance
    assert f'value="{"a" * 32}" readonly' in html


def test_zero_revenue_with_sales_still_has_a_real_zero_ticket() -> None:
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "free-sale"},
            summary={
                "net_revenue_brl": Decimal("0"),
                "sales_count": 2,
                "average_ticket_brl": Decimal("0"),
            },
        )
    )
    assert list(_summary_values(html).values()).count("R$ 0,00") == 2
    assert "Sem vendas no período" not in html


def test_report_nav_includes_products_anchor() -> None:
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "pub-1", "run_id": "run-1"},
            latest_attempt={"batch_id": "b1", "run_id": "r1", "state": "PUBLISHED"},
            products=[{"product_id": "P01", "units": 3, "net_revenue_brl": Decimal("30.00")}],
        )
    )
    # A nav aponta para a seção de produtos e o painel tem o id correspondente.
    assert 'href="#produtos"' in html
    assert ">Produtos<" in html
    assert 'id="produtos"' in html
    # A navegação local acompanha a composição: matriz, série, ranking.
    assert (
        html.index('href="#indicadores"')
        < html.index('href="#lojas"')
        < html.index('href="#produtos"')
    )


@pytest.mark.parametrize("state", ["TECHNICAL_FAILURE", "PUBLISHED"])
def test_publication_with_incomplete_audit_is_never_described_as_previous(state: str) -> None:
    attempt = {
        "run_id": "published-run",
        "state": state,
        "audit_incomplete": state == "PUBLISHED",
        "duration_seconds": 12,
    }
    html = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "current", "run_id": "published-run"},
            latest_attempt=attempt,
        )
    )
    context = html.split('<p class="publication-context">', 1)[1].split("</p>", 1)[0]
    assert "Publicação disponível, com registro final da tentativa incompleto" in context
    assert "publicação anterior" not in context
    assert "falhou antes" not in context


def test_blocked_coverage_only_claims_previous_indicators_when_a_snapshot_exists() -> None:
    attempt = {"state": "BLOCKED", "coverage": {"expected": ["S01", "S02"], "received": ["S01"]}}
    empty = build_report_html(ReportPayload(latest_attempt=attempt))
    published = build_report_html(
        ReportPayload(snapshot={"publication_id": "old"}, latest_attempt=attempt)
    )
    assert "Ainda não há indicadores publicados" in empty
    assert "indicadores exibidos pertencem à publicação anterior" not in empty
    assert "Fechamento bloqueado por cobertura" in published
    assert "indicadores exibidos pertencem à publicação anterior" in published


def test_source_provenance_escapes_paths_and_keeps_reference_hashes() -> None:
    hostile = '<script>alert("source")</script>'
    html = build_report_html(
        ReportPayload(
            snapshot={
                "sources": [
                    {
                        "batch_id": "b1",
                        "bronze_path": hostile,
                        "bronze_version": 2,
                        "reference_hashes": {hostile: "a" * 64},
                    }
                ]
            }
        )
    )
    assert hostile not in html
    assert "a" * 64 in html
    assert "Fonte · b1" in html
    assert "Caminho bronze" in html


def test_unmeasured_stages_are_not_drawn_as_successful_steps() -> None:
    html = build_report_html(
        ReportPayload(
            latest_attempt={
                "state": "BLOCKED",
                "stages": {"ingestion": 1.5},
            }
        )
    )
    rail = html.split('<section class="stage-rail"', 1)[1].split("</section>", 1)[0]
    assert "Ingestão" in rail
    assert "Indicadores" not in rail
    assert "Publicação" not in rail
    assert "Uma medição não confirma, por si só, o sucesso da etapa" in rail


@pytest.mark.parametrize("stats", [{}, {"received": 5}, {"rejected": 0}, {"received": 0}])
def test_missing_rejection_inputs_do_not_imply_zero_or_inapplicable(stats: dict[str, int]) -> None:
    html = build_report_html(ReportPayload(latest_attempt={"state": "RUNNING", "stats": stats}))
    assert "Rejeição: indisponível" in html
    assert "Rejeição: 0,00%" not in html
    assert "Rejeição: não aplicável" not in html


def test_publication_context_belongs_to_indicators_and_not_global_heading() -> None:
    page = build_report_html(
        ReportPayload(
            snapshot={
                "publication_id": "published-before",
                "published_at": "2026-01-01T10:00:00Z",
                "run_id": "old",
            },
            latest_attempt={"state": "BLOCKED", "batch_id": "new-delivery", "run_id": "new"},
            summary={
                "net_revenue_brl": "64.00",
                "first_date": "2026-01-01",
                "last_date": "2026-01-01",
            },
        )
    )
    indicators = page.split('<section class="panel" id="indicadores"', 1)[1].split(
        '<section class="panel" id="proveniencia"', 1
    )[0]
    assert "R$ 64,00" in indicators and "Publicação anterior preservada" in indicators
    assert "01/01/2026" in indicators and "published-before" in indicators
    assert "decision-action" not in indicators and "<h1>" not in indicators
    execution = page.split('<section class="panel" id="qualidade"', 1)[1].split(
        '<section class="panel" id="indicadores"', 1
    )[0]
    assert "Período da entrega</dt><dd>Não informado no snapshot" in execution
    assert "01/01/2026 a 01/01/2026" not in execution


def test_delivery_register_distinguishes_zero_confirmation_pending_and_unknown() -> None:
    page = build_report_html(
        ReportPayload(
            latest_attempt={
                "state": "BLOCKED",
                "coverage": {
                    "expected": ["S01", "S02", "S03"],
                    "received": ["S01", "S03"],
                    "zero_movement": ["S03"],
                },
            }
        )
    )
    coverage = page.split('<section class="coverage-summary"', 1)[1].split("</section>", 1)[0]
    assert "2 de 3 lojas com entrega confirmada" in coverage
    assert 'S02</span><span class="delivery-state pending">Pendente' in coverage
    assert 'S03</span><span class="delivery-state confirmed">Zero movimento confirmado' in coverage
    unknown = build_report_html(ReportPayload(latest_attempt={"coverage": {"expected": ["S01"]}}))
    assert "Cobertura não informada neste snapshot" in unknown
    assert 'class="delivery-state unknown">Conferência indisponível' in unknown
    assert "0 de 1 lojas" not in unknown


def test_missing_summary_values_never_become_published_zero() -> None:
    missing = build_report_html(ReportPayload(snapshot={"publication_id": "p"}, summary={}))
    metrics = missing.split('<section class="metrics"', 1)[1].split("</section>", 1)[0]
    assert "R$ 0,00" not in metrics and "0" not in _summary_values(metrics).values()
    assert list(_summary_values(metrics).values()).count("—") == 4
    assert "Sem vendas no período" not in metrics
    assert "Período não informado" in missing
    zero = build_report_html(
        ReportPayload(
            snapshot={"publication_id": "p"},
            summary={
                "net_revenue_brl": "0.00",
                "units": 0,
                "sales_count": 0,
                "item_lines": 0,
            },
        )
    )
    assert "R$ 0,00" in zero and "Sem vendas no período" in zero


def test_financial_formatter_preserves_sign_and_large_exact_value() -> None:
    from retail_pipeline.report_view import _money

    assert _money(Decimal("-12.34")) == "R$ -12,34"
    assert _money(Decimal("1234567890123.45")) == "R$ 1.234.567.890.123,45"
    assert _money(None) == "—"


def test_chart_preserves_calendar_gaps_without_inventing_observations() -> None:
    from retail_pipeline.report_view import _revenue_chart

    chart = _revenue_chart(
        [
            {"business_date": "2026-01-01", "net_revenue_brl": "10.00"},
            {"business_date": "2026-01-02", "net_revenue_brl": "20.00"},
            {"business_date": "2026-01-05", "net_revenue_brl": "30.00"},
        ]
    )
    assert chart.count("<polyline") == 1
    assert chart.count("<circle") == 3
    assert 'cx="110"' in chart and 'cx="302"' in chart and 'cx="880"' in chart
    assert "Dias sem observação não representam receita zero" in chart
    assert "03/01/2026" not in chart and "04/01/2026" not in chart
    single = _revenue_chart([{"business_date": "2026-01-01", "net_revenue_brl": "0.00"}])
    assert 'cx="110"' in single and "<polyline" not in single
    assert "01/01/2026: R$ 0,00" in single


def test_matrix_distinguishes_zero_missing_value_missing_day_and_negative() -> None:
    from retail_pipeline.report_view import _store_matrix

    matrix = _store_matrix(
        [
            {"business_date": "2026-01-01", "store_id": "S01", "net_revenue_brl": "0.00"},
            {"business_date": "2026-01-03", "store_id": "S01", "net_revenue_brl": None},
            {"business_date": "2026-01-03", "store_id": "S02", "net_revenue_brl": "-12.34"},
        ]
    )
    assert matrix.count("data-heat-cell ") == 2
    assert 'class="heat-cell heat-zero"' in matrix
    assert 'aria-label="Sem observação"' in matrix
    assert 'aria-label="Receita não informada"' in matrix
    assert "S02 · 03/01/2026 · R$ -12,34" in matrix
    assert matrix.count('tabindex="0"') == 2  # scroll region + one active cell
    assert 'href="#store-row-2"' in matrix


@pytest.mark.parametrize(
    "dates",
    [
        ["0001-01-01", "1800-01-01", "9999-12-31"],
        ["invalid"],
    ],
)
def test_matrix_extreme_dates_fall_back_to_exact_table(dates: list[str]) -> None:
    html = build_report_html(
        ReportPayload(
            stores=[
                {"business_date": day, "store_id": "S01", "net_revenue_brl": "10.01"}
                for day in dates
            ]
        )
    )
    assert 'class="store-matrix"' not in html
    assert html.count('id="store-row-') == len(dates)
    assert "tabela" in html


def test_matrix_does_not_sum_duplicates_or_invent_scale_for_absent_values() -> None:
    from retail_pipeline.report_view import _store_matrix

    absent = _store_matrix([{"store_id": "S01", "business_date": "2026-01-01"}])
    assert "R$ 0,00" not in absent
    assert "Sem receita informada para definir a escala" in absent
    duplicate = _store_matrix(
        [
            {"store_id": "S01", "business_date": "2026-01-01", "net_revenue_brl": "2.00"},
            {"store_id": "S01", "business_date": "2026-01-01", "net_revenue_brl": "3.00"},
        ]
    )
    assert 'class="heat-unavailable"' in duplicate
    assert "R$ 5,00" not in duplicate
    assert "Nenhum valor foi somado" in duplicate


def test_product_ranking_preserves_input_order_exact_units_and_unknowns() -> None:
    from retail_pipeline.report_view import _product_ranking

    ranking = _product_ranking(
        [
            {"product_id": "P03", "units": 10},
            {"product_id": "P01", "units": 0},
            {"product_id": "<P02>", "units": None},
        ]
    )
    assert ranking.index("P03") < ranking.index("P01") < ranking.index("&lt;P02&gt;")
    assert "width:100.000%" in ranking and ranking.count("width:0.000%") == 2
    assert ">0</strong>" in ranking and ">—</strong>" in ranking


def test_chart_excludes_unknown_without_zero_and_keeps_negative_sign() -> None:
    from retail_pipeline.report_view import _revenue_chart

    chart = _revenue_chart(
        [
            {"business_date": "2026-01-01", "net_revenue_brl": "-12.34"},
            {"business_date": "2026-01-02", "net_revenue_brl": None},
            {"business_date": "2026-01-03", "net_revenue_brl": "5.00"},
        ]
    )
    assert chart.count("<circle") == 2 and "<polyline" not in chart
    assert "01/01/2026: R$ -12,34" in chart
    assert "02/01/2026: R$ 0,00" not in chart
    assert "Receitas não informadas não foram desenhadas como zero" in chart


def test_font_and_brand_are_embedded_with_license_without_network() -> None:
    from base64 import b64decode
    from importlib.resources import files

    from retail_pipeline.report_assets import FONT_CSS

    raw = FONT_CSS.split("base64,")[1].split(")")[0]
    assert (
        b64decode(raw)
        == files("retail_pipeline").joinpath("assets/source-sans-3.woff2").read_bytes()
    )
    html = build_report_html(ReportPayload())
    assert "data:image/svg+xml;base64," in html
    assert "SIL OPEN FONT LICENSE Version 1.1" in html
    assert "Copyright 2010-2024 Adobe" in html
    assert "<script src=" not in html and 'href="https://' not in html

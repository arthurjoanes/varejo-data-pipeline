from decimal import Decimal
from pathlib import Path

import pytest

from retail_pipeline.report_model import ReportPayload
from retail_pipeline.report_view import build_report_html
from retail_pipeline.reporting import _read_published_tables


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
    assert html.count("<strong>—</strong>") == 4
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
    assert html.count("<strong>R$ 0,00</strong>") == 1
    assert "Sem vendas no período" in html
    assert html.count("<strong>—</strong>") == 1
    assert html.count("<strong>0</strong>") == 2
    assert "0 itens de venda ativos" in html
    assert "Sem movimento publicado" in html
    assert "Sem publicação disponível" not in html


def test_unfinished_attempt_is_not_success_or_a_zero_measurement() -> None:
    html = build_report_html(ReportPayload(latest_attempt={"state": "RUNNING", "stats": {}}))
    assert '<span class="badge neutral">Sem resultado final</span>' in html
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
    svg = html.split("<svg", 1)[1].split("</svg>", 1)[0]
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
    assert 'class="dominant-stage">Qualidade · 3,2 s' in html
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
    assert html.count("<strong>R$ 0,00</strong>") == 2
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
    # A ordem na nav: produtos entre indicadores e lojas.
    assert (
        html.index('href="#indicadores"')
        < html.index('href="#produtos"')
        < html.index('href="#lojas"')
    )

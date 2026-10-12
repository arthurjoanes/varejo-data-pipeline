# Fixtures do relatório

Os 22 JSONs contêm dados sintéticos para testar o renderer e a navegação offline.

- `actual-*`: três publicações de teste, com primeira publicação, comparação válida e períodos sem interseção.
- `historical-*`: snapshots das demonstrações de setembro de 2026, incluindo 30 dias de vendas. Datas e valores pertencem àqueles snapshots.
- `fixture-*`: estados de fronteira construídos para testes, como ausência de publicação, valores extensos, perfil indisponível e auditoria incompleta.

`presentation_only` identifica estados artificiais no HTML. Cada `payload` segue `ReportPayload`; gerar uma página não inicia Spark nem processa novas entregas.

```sh
PYTHONPATH=src python scripts/render_report_fixtures.py tests/fixtures/reports artifacts/report-fixtures/html
```

Use um diretório de saída novo por execução. Os testes de navegador estão descritos em [qualidade do relatório](../../../docs/frontend-quality.md).

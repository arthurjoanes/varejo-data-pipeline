# Qualidade da interface

O relatório é um snapshot somente leitura. Sua geração fixa a publicação e as versões Delta; abrir o HTML não consulta Spark, publica dados ou atualiza o fechamento. O [guia da interface](interface.md) descreve as cinco áreas de consulta.

## Contratos de apresentação

| Conteúdo | Regra |
| -------- | ----- |
| Zero e ausência | Zero confirmado aparece como zero. Campo ausente, receita não informada, ticket indefinido e ausência de publicação mantêm estados distintos. |
| Valores monetários | Cálculos usam Decimal. Moeda conserva centavos com arredondamento de apresentação; médias e diferenças preservam as casas do contrato. |
| Receita diária | Colunas usam datas comerciais e eixo que inclui zero. Lacunas não viram receita zero; negativos conservam o sinal. Um dia produz uma coluna. |
| Receita por loja | A soma agrega somente o input recebido. Até seis lojas aparecem; o denominador percentual inclui todas as lojas com receita completa do recorte, antes desse limite. |
| Produtos | Até cinco produtos e um grupo com os restantes exibidos. A participação usa as unidades conhecidas desse input. Valores negativos desabilitam a participação. |
| Comparação | Anterior e atual pertencem à baseline e à publicação identificadas, nas versões Delta fixadas e no recorte equivalente. |
| Dados e texto | IDs e conteúdo externo são escapados. Gráficos conservam tabelas exatas, rótulos e unidades. |

A comparação distingue quantidade por linha de preço ponderado por unidades antes dos descontos. A distribuição de preço calcula média por linha. Baseline zero deixa a variação relativa indefinida; falta de amostra ou de recorte comum mantém o estado registrado.

Limites de apresentação são 366 dias, 20 produtos e 500 registros de loja-dia no total. Um recorte truncado deve ser identificado; percentuais locais não representam automaticamente todo o período. Os cartões usam os totais publicados completos.

## Reproduzir a apresentação

Os JSONs em `tests/fixtures/reports/` incluem snapshots e fixtures explicitamente rotuladas. Renderizar esses dados não executa novas entregas ou leituras Spark.

A partir da raiz, com Python, Node e as ferramentas de navegador disponíveis:

```sh
PYTHONPATH=src python scripts/render_report_fixtures.py tests/fixtures/reports artifacts/report-fixtures/html
DASHBOARD_INPUTS=tests/fixtures/reports node scripts/dashboard-review.cjs after artifacts/report-fixtures/html artifacts/report-fixtures/qa
```

O primeiro comando gera HTMLs e `corpus-after.json`, com hashes dos inputs, HTMLs e recursos do renderer. O segundo grava seus resultados em um diretório novo. Para repetir, escolha outra pasta-pai de renderização e outra saída de QA.

Playwright e `@axe-core/playwright` são ferramentas de desenvolvimento. Mantenha os módulos isolados em `artifacts/browser-tools/`; eles não são dependências do HTML.

| Variável | Uso |
| -------- | --- |
| `PLAYWRIGHT_MODULE` | Caminho absoluto do módulo Playwright instalado |
| `AXE_MODULE` | Caminho absoluto de `@axe-core/playwright` |
| `PLAYWRIGHT_CHANNEL=msedge` | Seleciona Edge no motor Chromium |
| `REVIEW_BROWSER=firefox` | Seleciona Firefox instalado para o Playwright |
| `DASHBOARD_INPUTS` | Diretório dos JSONs usados para conferir os valores |

## Escopo das verificações

Os testes unitários cobrem escaping, precisão, agrupamentos, estados vazios e separação entre tentativa e publicação. O smoke do pacote confere importação e geração de HTML; o wheel conserva os recursos locais.

Os gates de código concluídos registram 402 testes unitários, Ruff e formato em 65 arquivos, mypy em 21 módulos e 35 arquivos do wheel iguais à fonte. Resultados de navegador têm seu próprio escopo de casos, motores e larguras.

O harness percorre navegação, âncoras, teclado e detalhes nativos. Confere valores dos dados fornecidos, layout, leitura offline e sem JavaScript. `scripts/profile-report-review.cjs` complementa a verificação com a seleção e cópia de IDs por fallback. Source Sans 3, marca e scripts permanecem locais.

Na validação de 12/10/2026, Edge 155 percorreu os 22 casos em 320, 390, 768, 1024 e 1440 CSS px; Firefox 155 conferiu três casos. Não houve falhas de aceite, erros JavaScript ou requisições HTTP externas. Três controles negativos confirmaram que retirar um valor conhecido, o denominador ou um percentual faz o teste falhar.

Axe verifica regras selecionadas nos estados visitados. Os quatro scans por navegador não encontraram violações automáticas; cada motor deixou um resultado `incomplete` de contraste em células parcialmente fora da região de rolagem de uma tabela. Resultados inconclusivos exigem revisão manual; zero violações automáticas não certifica conformidade WCAG.

## Limites

Reflow por largura CSS e overrides de espaçamento não comprovam zoom nativo. Zoom nativo, leitor de tela e forced-colors não foram verificados. Os resultados também não medem produtividade, capacidade do pipeline ou desempenho em hardware lento.

Os dados sintéticos e as fixtures não ampliam o contrato de vendas. Uma verificação de apresentação não substitui os testes Spark/Delta de publicação, correção, concorrência e recuperação.

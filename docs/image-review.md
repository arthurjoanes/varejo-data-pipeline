# Conferência das imagens em 22/09/2026

O layout da fonte atual continua sendo a composição v4. O replay gerou **30 capturas reais em Edge**, com os mesmos cinco payloads históricos e as fixtures declaradas pelo harness. **27 PNGs coincidiram byte a byte** com as imagens v4 já publicadas. Os outros três conservaram dimensões, conteúdo e composição; a comparação encontrou 1, 56 e 393 pixels diferentes, respectivamente, em imagens com mais de 800 mil pixels. A inspeção visual não encontrou mudança de layout. Mantive as imagens existentes para evitar cópias redundantes.

[Execução](images/interface-v4/report.png) · [Indicadores](images/interface-v4/indicators.png) · [Arquivos](images/interface-v4/files.png) · [Bloqueio](images/interface-v4/blocked.png) · [390 px](images/interface-v4/report-390.png).

Os cinco módulos de apresentação e os assets locais foram comparados com os hashes da revisão v4. Fonte Source Sans 3 efetiva, navegação, foco, estados, tabelas exatas, matriz, leitura sem JavaScript e ausência de requisições externas passaram no harness existente. Foram **15 combinações principais de vista/largura** e **14 vistas no axe, sem violações automáticas**. Esses checks não cobrem leitor de tela, zoom nativo nem paginação integral de PDF. [Manifesto da conferência](evidence/image-review-20260922.json).

A revisão de imagens de **22/09/2026** produziu o recorte focalizado de **644 × 318 px**, capturado diretamente do painel de cobertura pelo navegador. A apresentação atual também preserva a imagem de abertura `docs/readme/home.png`; a contagem daquele ensaio não é inventário de todos os embeds posteriores. Os prints completos permanecem como links, preservando o contexto e os bytes das provas. O recorte usa o snapshot histórico de entrega ausente; não substitui a prova editorial separada de calendário/remetente.

Fontes desta seção, conferidas em **22/09/2026**: [image-review-20260922.json](evidence/image-review-20260922.json).

## Origem de cada conjunto

| Conjunto                                               | Classificação e tratamento                                                                                                                                                                                                                       |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `current-20260922/coverage-focus.png`                  | Recorte nativo atual, com origem e geometria registradas. Sem edição de DOM, CSS, dados ou pixels.                                                                                                                                               |
| `editorial-20260922`                                   | Cinco capturas de uma execução sintética real, vinculadas no README e nos casos de negócio. Bytes e hashes preservados; não foram substituídas por fixtures.                                                                                     |
| `interface-v4`                                         | Composição atual sobre dados históricos. Os 14 arquivos `before/` são comparações históricas; `proposta-a`, `proposta-b` e `tipografia` são explorações de design, não telas finais. Fixtures de estados continuam explicitamente identificadas. |
| `interface-v2`, `interface-v3`                         | Provas de layouts anteriores, preservadas com seus manifestos e pares de comparação. Não representam o layout atual.                                                                                                                             |
| `state-proof`                                          | Seis capturas históricas de restauração, vinculadas por hash ao ensaio e aos HTMLs originais. Preservadas integralmente.                                                                                                                         |
| `interface/journey-*`                                  | Três capturas históricas de jornadas vinculadas por hash. Preservadas.                                                                                                                                                                           |
| `interface` sem `journey-*`, `round-2`                 | 24 exports antigos sem referências de arquivo ou vínculo de hash nos documentos/scripts. Redundantes para a apresentação atual; removidos após cópia externa e verificação de SHA-256. Registros, payloads e resultados operacionais permanecem. |
| `docs/stack/*.svg`, `src/retail_pipeline/assets/*.svg` | Quatro ícones de stack e três recursos de marca; não são screenshots. Mantidos com licenças e usos atuais.                                                                                                                                       |

O inventário externo classificou os **174 arquivos de imagem originais**, seus consumidores, hashes, tamanhos, duplicatas e decisões. As nove pranchas de inspeção incluem todas essas imagens e as 30 novas capturas. A revisão removeu 2.887.411 bytes de exports órfãos. Duplicatas que sustentam manifestos ou pares históricos permanecem para conservar esses contratos.

Fontes desta seção, conferidas em **22/09/2026**: [image-review-20260922.json](evidence/image-review-20260922.json) · [capture-doc-focus.cjs](../scripts/capture-doc-focus.cjs).

## Reproduzir a conferência

Com Python, Node, Playwright e axe disponíveis, na raiz do repositório:

```powershell
$review = Join-Path $env:TEMP 'varejo-image-review'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python scripts/render_review.py --output (Join-Path $review 'html')
$env:REVIEW_HTML_DIR = Join-Path $review 'html'
$env:REVIEW_IMAGES = Join-Path $review 'images'
$env:REVIEW_EVIDENCE = Join-Path $review 'evidence'
$env:PLAYWRIGHT_CHANNEL = 'msedge'
node scripts/visual-review.cjs
node scripts/a11y-review.cjs
node scripts/capture-doc-focus.cjs
```

`PLAYWRIGHT_MODULE` e `AXE_MODULE` podem indicar instalações externas. O replay não inicia Spark, não executa lote/benchmark e não lê nem substitui o estado operacional. Sem overrides, os scripts de navegador agora escrevem em `artifacts/interface-review`, evitando sobrescrever provas em `docs/evidence` e `docs/images`.

Fontes desta seção, conferidas em **22/09/2026**: [image-review-20260922.json](evidence/image-review-20260922.json) · [capture-doc-focus.cjs](../scripts/capture-doc-focus.cjs).

## Relatório local aberto

O servidor da porta 3103 servia um HTML antigo, com a marca e a composição anteriores, apesar de a fonte já conter v4. O export ignorado `artifacts/report.html` foi regenerado com o mesmo payload histórico de R$ 77, após backup externo verificado. O HTML anterior não tinha vínculo de hash nas provas versionadas. A comparação dos dois HTMLs confirmou igualdade de quatro métricas, seis linhas das tabelas, seis campos de identidade e cinco registros de fontes.

O servidor usa o Compose normal, com o export montado somente para leitura. Para iniciá-lo novamente:

```powershell
.\scripts\pipeline.ps1 serve
```

[Abrir relatório local](http://127.0.0.1:3103/report.html). A correção permanece no export local e não exige override externo. Uma futura demo gera um novo snapshot; abrir a página continua sendo leitura, sem nova execução do pipeline. Inventário, capturas completas novas, logs e backup desta revisão ficam fora do repositório.

Fontes desta seção, conferidas em **22/09/2026**: [image-review-20260922.json](evidence/image-review-20260922.json) · [capture-doc-focus.cjs](../scripts/capture-doc-focus.cjs).

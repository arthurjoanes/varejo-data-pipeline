# Qualidade da interface de fechamento

## Revisão de UI/UX em 12/10/2026

Quem confere o fechamento precisa reconhecer a decisão registrada, investigar uma pendência ou variação e conferir os valores e sua origem. As [quatro jornadas](interface.md#quatro-jornadas-de-consulta) atravessam Execução, Indicadores e Arquivos. O HTML continua sendo um snapshot somente leitura: navegação, consulta e cópia de IDs não publicam dados nem iniciam Spark.

### Diagnóstico e escolha de composição

A captura anterior da comparação válida mostrou o aviso de preço depois dos gráficos, numa tabela de oito colunas. Em 390 px, a entrada do perfil mostrava contexto e ID antes da regra. Isso foi observado na interface. A hipótese de design é que aproximar a comparação dos totais e mostrar os valores da regra em uma lista reduz a procura pela explicação. Não houve entrevista, teste com usuários ou medição de produtividade.

| Problema observado | Quem encontra | Evidência | Prioridade | Mudança | Teste de aceite |
| ------------------ | ------------- | --------- | ---------- | ------- | --------------- |
| Aviso de preço depois dos gráficos e oito colunas para ler a regra | Quem explica uma variação | Captura anterior da comparação válida, 390 px; [direção](evidence/uiux-20261012-a12e4a/design-plan.md) | P2 | Comparação junto dos totais e lista de regras, aviso primeiro | Contexto precede regra; anterior, atual e diferença legíveis em 320 e 390 px, com tabela exata disponível. |
| Com espaçamento de texto em 320 px, a navegação gera largura global de 326/327 px | Quem amplia o espaçamento para leitura | [Diagnóstico v1](evidence/uiux-20261012-a12e4a/iterations-v1/overflow-diagnostic-v1.json); comportamento também observado no BEFORE | P1 | Navegação pode quebrar e encolher dentro do viewport | Todas as vistas permanecem em 320 px sob os overrides de texto, sem overflow global. |
| Percentual de aviso ocupa 102 px em um campo de 99 px | Quem lê a variação de preço em tela estreita | [Registro v1](evidence/uiux-20261012-a12e4a/iterations-v1/qa-v1-index.json), com espaçamento de texto | P1 | Reorganizar a largura dos valores da regra | Percentual e valores principais ficam completos, sem rolagem interna do campo, em 320 px. |
| Nome desconhecido de métrica no novo H5 gera documento de 339 px em 320 px | Quem abre um input de apresentação com rótulo fora do contrato | [Probe do marcador](evidence/uiux-20261012-a12e4a/iterations-v1/uiux-chromium-probes-unknown-v1.json) | P2 | Quebra de texto literal escapado e colunas que podem encolher | Mesmo marcador antes/depois, com e sem JavaScript, sem alargar a página. O reader continua recusando métrica fora do contrato. |
| Rótulos de métricas nas tabelas de alterações e lote usam células comuns | Quem consulta relações entre rótulo e valor | [Registro v1](evidence/uiux-20261012-a12e4a/iterations-v1/qa-v1-index.json) | P2 | Cabeçalhos de linha para os rótulos dessas tabelas | Caption, cabeçalhos de coluna e `th scope="row"` nas métricas, mantendo valores e ordem. |

P1 indica um problema de leitura ou layout que exige correção nesta rodada; P2 indica hierarquia, conteúdo de fronteira ou semântica. A consequência das falhas está na apresentação. Os testes não encontraram uma divergência financeira nesses casos.

### Correções do oracle e falhas da interface

O [registro das correções do oracle](evidence/uiux-20261012-a12e4a/iterations-v1/oracle-corrections-v2.json) preserva as premissas corrigidas. Sem publicação, o relatório deve mostrar quatro indicadores indisponíveis; o oracle v1 esperava ausência de elementos. As verificações de período passaram a comparar datas e quantidade, permitindo a gramática singular e a descrição de um conjunto vazio. Cabeçalhos de linha são exigidos onde o primeiro campo identifica uma métrica, sem impor a mesma forma a toda tabela. A espera de fontes do Firefox recebeu prazo finito e retorno serializável; uma tentativa interrompida não foi registrada como aprovação.

Essas correções do teste não resolvem os defeitos de layout ou semântica listados acima. Os gates de overflow, leitura dos valores e cabeçalhos de métricas continuaram ativos. Os relatórios v1, inclusive falhas e tentativas incompletas, permanecem em [iterations-v1](evidence/uiux-20261012-a12e4a/iterations-v1/); o resultado da fonte final depende do QA v2.

### Duas composições

| Composição | Ordem de leitura | Decisão |
| ---------- | ---------------- | ------- |
| A: fechamento, comparação e análise | Identidade e totais; recorte e contexto; aviso e valores das regras; matriz e gráficos | Escolhida para manter a explicação de uma mudança junto dos indicadores publicados. |
| B: panorama e chamada de perfil | Identidade e totais com chamada; matriz e gráficos; perfil ao fim | Mantém a análise comercial na entrada, mas exige um salto para investigar a comparação. |

Essas duas composições pertencem à revisão atual. A comparação A/B da v4, preservada abaixo, usou outro diagnóstico e outra fonte. Os [recibos de direção e pesquisa](evidence/uiux-20261012-a12e4a/) e as [imagens da revisão](images/uiux-20261012-a12e4a/) têm registros próprios no [índice final](evidence/uiux-20261012-a12e4a/index.json).

A implementação conserva Source Sans 3 local, licença OFL e a marca existente. Valores usam algarismos tabulares. Cor acompanha o estado escrito; foco, aviso e bloqueio têm funções distintas. O contexto conhecido, parcial ou ausente aparece antes da variação. O aviso vem primeiro na lista de regras, e a tabela completa permanece num detalhe nativo. Informações de origem e distribuições continuam acessíveis sem ocupar a decisão inicial.

### Pesquisa aplicada

As referências foram consultadas em 12/10/2026. A [WCAG 2.2](https://www.w3.org/WAI/WCAG22/quickref/) orientou os critérios de contraste, foco, reflow, espaçamento de texto e alvos. As [tabelas da WAI](https://www.w3.org/WAI/tutorials/tables/two-headers/) orientaram a relação entre cabeçalhos e valores. [Details](https://design-system.service.gov.uk/components/details/) e [summary list](https://design-system.service.gov.uk/components/summary-list/) do GOV.UK apoiaram o uso de detalhes nativos para conteúdo secundário e pares de rótulo/valor para contexto. As [notificações do Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/notification/guidelines) foram referência para a posição de avisos persistentes. A [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) orientou semântica, foco e conteúdo longo.

Foram adaptados os mecanismos de apresentação; código, templates, marcas e assets dessas referências não foram copiados. Documentação de componentes não comprova usabilidade deste produto. O [guia do Playwright](https://playwright.dev/docs/accessibility-testing) também separa os testes automáticos das avaliações manuais de acessibilidade.

### Mesmo corpus antes e depois

O corpus tem 22 inputs imutáveis. Três contêm o ReportPayload real das publicações inicial, comparável e sem recorte comum, relido com `versionAsOf` em uma única sessão Spark. Os 174 arquivos duráveis da demonstração permaneceram iguais; nenhum lote foi executado nessa captura. Cinco são os payloads históricos já versionados. Os 14 restantes são fixtures de apresentação identificadas no HTML e no manifesto.

Os três HTMLs anteriores coincidem byte a byte com os hashes da captura real. O renderer anterior, CSS, JavaScript, fontes e SVGs têm uma cópia congelada. O replay posterior usa os mesmos JSONs, sem reler Delta ou gerar indicadores. Os [recibos finais](evidence/uiux-20261012-a12e4a/README.md) identificam os hashes de cada input, HTML e fonte, além do viewport e motor executados. O candidato final tem 94 fontes inventariadas antes e depois dos gates, sem alterações.

Receita conserva os centavos: R$ 64,00 na primeira publicação, R$ 104,00 na revisão comparável e R$ 64,00 no período sem interseção. As médias preservam suas casas decimais; quantis continuam aproximações com algoritmo e precisão informados. A fixture de valor extenso usa `1234567890123.45` e ticket `411522630041.15`, calculado com Decimal para três vendas. Zero aditivo confirmado, ticket indefinido, campo ausente e ausência de publicação têm apresentações distintas.

### Validação da fonte final

A paleta da marca usa azul petróleo `#245B64` para marca, links, ações e gráficos. Azul escuro, branco e cinza claro sustentam a folha de conferência; verde, ocre e vermelho conservam suas funções semânticas. A [paleta e seus usos](interface.md#paleta-e-identidade) e o README registram os códigos. Fonte e marca existentes foram reaproveitadas.

- **374 unitários passaram**, incluindo 91 do relatório, em 25,04 s no Linux. Ruff passou; formato conferiu 64 arquivos e mypy conferiu 20 módulos. O wheel final contém 34 arquivos iguais à fonte e gerou HTML num import isolado. [Gates e ambiente](evidence/uiux-20261012-a12e4a/quality-final.public.json).
- **Edge 155.0.4283.45:** 22 inputs, cinco larguras, 3.560 checks e 18 capturas; nenhuma falha de aceite. **Firefox 155.0:** três casos, 479 checks e 11 capturas, incluindo comparação, matriz e dinheiro extenso. [Edge](evidence/uiux-20261012-a12e4a/qa-final-edge-v5/uiux-review.json) · [Firefox](evidence/uiux-20261012-a12e4a/qa-final-firefox-v5/uiux-review.json).
- As jornadas passaram por teclado, Tab/Shift+Tab, âncoras, histórico, detalhes nativos, cópia/fallback e leitura sem JavaScript. Os valores capturados, IDs, tabelas e fontes foram preservados. Não houve requisição remota, falha de rede ou erro de página. Conteúdo longo, reflow, movimento reduzido e espaçamento de texto foram conferidos em 320, 390, 768, 1024 e 1440 CSS px.
- **Axe 4.13.0:** zero violações nas regras WCAG selecionadas. Edge conservou 80 resultados `incomplete` e Firefox 11, todos de contraste; SVGs, fundos e regiões de rolagem/sticky não viram aprovação automática. A [revisão dos grupos e limites](evidence/uiux-20261012-a12e4a/manual-review-v5.json) registra razões e seletores. Scanner sem violações não certifica WCAG 2.2 AA.
- As 960 amostras textuais do Edge e 138 do Firefox tiveram mínimo de **5,000:1**, sem resultado calculado abaixo do requisito. Foco branco na faixa escura: 12 alvos, mínimo **12,866:1**. Seleção/hover nas seis cores da matriz: 12 amostras numa fixture DOM separada, mínimo **3,904:1** para o anel mais visível. Esta fixture verifica apresentação, sem executar Spark. [Foco](evidence/uiux-20261012-a12e4a/focus-state-v5.json) · [Paleta](evidence/uiux-20261012-a12e4a/focus-palette-v5/probe.json).
- No Edge, 6.311 alvos satisfizeram o retângulo de 24 × 24 CSS px, 224 usaram a exceção de link em texto e 90 o espaçamento; no Firefox, 632, 33 e 15, respectivamente. São medições de retângulos/espaçamento, sem ensaio de toque físico ou hit-testing de toda forma.

As 18 [comparações de imagem](evidence/uiux-20261012-a12e4a/image-pairs.json) usam o mesmo input, estado e viewport. Capturas de perfil, bloqueio e conteúdo longo foram abertas em tamanho legível; aviso, contexto, valores e IDs continuam disponíveis. O dinheiro extenso conserva centavos, com rolagem local focável quando necessária, e a legenda pode quebrar entre valores inteiros.

Os overrides de texto usam line-height 1,5, intervalo de parágrafo 2em, letras 0,12em e palavras 0,16em. Reflow e esses overrides não comprovam zoom nativo. **Zoom nativo, leitor de tela e forced-colors permanecem NV**. Também não houve estudo com usuários, medida de produtividade, ensaio de hardware lento ou paginação integral de PDF. A suíte Spark/Delta anterior permanece vinculada à sua fonte; esta revisão não reprocessou lotes ou repetiu benchmark.

Para reproduzir os 22 payloads offline e testar outra captura sem sobrescrever os recibos, consulte [comandos e proveniência](evidence/uiux-20261012-a12e4a/README.md). A fonte final está em `source-candidate-v5.json`; os candidatos anteriores, falhas e correções do oracle continuam preservados.

## Interface funcional de perfis, 12/10/2026

Os registros desta seção descrevem a entrega funcional anterior à revisão de UI/UX acima. Seus testes, capturas e limites permanecem vinculados às fontes originais.

Em Indicadores, o link “Perfil e comparação” abre a seção da publicação capturada. O relatório identifica a publicação anterior, mostra mudanças de período, catálogo e lojas antes das regras e conserva tabelas para os totais originais e o recorte equivalente. A cobertura histórica parcialmente conhecida aparece antes das diferenças. O lote recebido tem suas próprias contagens e cobertura, separados do estado Silver ativo.

Receita, descontos e contribuições usam os valores decimais persistidos. Médias e diferenças preservam as casas do contrato; os quantis informam algoritmo e precisão e permanecem identificados como aproximações. A apresentação exibe até 20 grupos por dimensão, com aviso quando há mais grupos. A comparação usa as agregações completas nas versões Delta fixadas.

Primeira publicação, recorte vazio, falta de amostra e ausência de recorte comum têm textos próprios. Publicação legada sem perfil, referência ausente e perfil inválido também são estados explícitos. Abrir o HTML usa somente os dados capturados; cálculo de perfil e leitura Delta pertencem à geração do relatório. A composição Matriz → Série → Ranking da v4 permanece, seguida da nova seção funcional.

O [teste do renderer](../tests/unit/test_reporting.py) passou em **64 casos no Windows**, em 12/10/2026. Ele cobre escaping dos novos campos, limite de grupos, números extensos, médias sem arredondamento monetário, identificação da baseline, cobertura incompleta e separação entre tentativa bloqueada e publicação. Ruff, formato, mypy dirigido aos dois módulos de apresentação e sintaxe de JavaScript passaram. O primeiro teste completo no host encontrou a dependência Linux `fcntl`; a importação do leitor foi tornada tardia, e a execução completa seguinte passou. Esses testes do renderer não executam Spark.

O renderer também integrou a suíte Linux de **369 testes aprovados, sem skips**, em 1.536,62 s, com a fonte congelada em `0ddab5e`. Ruff e formato passaram em 62 arquivos, e mypy passou em 20 módulos. Os [recibos dessa execução](verification.md#evolução-de-perfis-e-lineage-em-12102026) identificam fonte, imagem e isolamento.

A revisão de rótulos `bc66968` passou em 69 casos dirigidos do renderer. Depois, **352 testes unitários passaram no Linux em 13,53 s**, e Ruff, formato e mypy passaram novamente. Os rótulos mostram "Datas registradas", distinguem catálogo aprovado de recebido e chamam as transições, inclusive CANCEL, de "Alterações do estado". Essa execução posterior tem [JUnit](evidence/evolucao-20261012-a12e4a/unit-labels.xml), [log](evidence/evolucao-20261012-a12e4a/unit-labels.log) e [inventário de fontes](evidence/evolucao-20261012-a12e4a/source-labels-before.json) próprios; a suíte completa de 369 testes permanece anterior a esses ajustes.

O [probe funcional](../scripts/profile-report-review.cjs) passou no Edge **155.0.4283.45**, sobre uma fixture de apresentação explicitamente sintética e fontes do renderer copiadas para um diretório próprio. Conferiu 1440, 768, 390 e 320 px, âncora e foco por teclado, abertura nativa do perfil, região de tabela focável, seleção/cópia da baseline, leitura sem JavaScript e zero requisições HTTP externas. Não houve overflow global nem erro JavaScript. Duas capturas, em 1440 e 320 px, foram inspecionadas. Os arquivos locais dessa execução estão em `artifacts/profile-functional-20261012`, com hashes das fontes, HTML/JSON da fixture e resultado do navegador. São provas de apresentação; os gates Linux e os novos lotes têm registros próprios em [verificação](verification.md).

### Relatórios gerados pela demonstração

O probe também passou sobre os três HTMLs gerados com Spark/Delta e fixtures sintéticas, na fonte `bc66968` e imagem `8165ad96042f…`. Foram **12 combinações**, com os estados `NO_BASELINE`, `COMPARABLE` e `NOT_COMPARABLE` em 1440, 768, 390 e 320 px, no mesmo Edge 155.0.4283.45. As verificações cobriram âncora e foco por teclado, abertura do perfil, região de tabela focável, seleção da baseline pelo fallback de cópia, leitura sem JavaScript e modo offline. Nenhuma combinação apresentou erro JavaScript, requisição HTTP externa ou overflow global. O navegador leu os HTMLs capturados sem iniciar Spark.

Os recibos de [primeira publicação](evidence/evolucao-20261012-a12e4a/browser-initial/profile-functional.public.json), [comparação válida](evidence/evolucao-20261012-a12e4a/browser-comparable/profile-functional.public.json) e [recorte não comparável](evidence/evolucao-20261012-a12e4a/browser-incomparable/profile-functional.public.json) têm manifestos de entrada com IDs, totais, versões Delta e hashes de fonte/HTML. Foram produzidas seis capturas. Dois recortes foram inspecionados: [comparação válida em 320 px](evidence/evolucao-20261012-a12e4a/browser-comparable/profile-320.png) e [não comparável em 1440 px](evidence/evolucao-20261012-a12e4a/browser-incomparable/profile-1440.png). O [índice](evidence/evolucao-20261012-a12e4a/browser-index.json) registra os hashes dos recibos originais e públicos; nos públicos, somente o caminho absoluto da entrada foi substituído pelo caminho relativo do artefato. Os originais continuam no diretório local de artifacts.

Essa conferência verifica a interface funcional desta entrega. Avaliação completa de UX e acessibilidade, leitor de tela, zoom nativo e outros motores permanecem fora do percurso executado. As provas sintéticas anteriores e a revisão v4 abaixo conservam seus resultados e fontes.

Para conferir um relatório novo já gerado, use as ferramentas opcionais de desenvolvimento:

```powershell
$env:PLAYWRIGHT_MODULE = 'C:\Users\arthu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
$env:PLAYWRIGHT_CHANNEL = 'msedge'
node scripts/profile-report-review.cjs artifacts/profile-functional-20261012/fixture-profile.html artifacts/profile-functional-20261012/browser-replay
```

O primeiro argumento é o HTML capturado; o segundo é um diretório novo para o JSON de resultados e as capturas. O caminho de Playwright depende da instalação local. Esta etapa verifica a interface funcional; avaliação visual posterior, leitor de tela, zoom nativo e outros motores continuam pendentes. As capturas e os resultados v4 abaixo conservam sua data original.

## Revisão visual v4

Direção visual v4, revisada em 22/09/2026. Baseline visual: `636e8408f1108ce387ddc291318d2d1ebe042dee`. Esta revisão usa os mesmos cinco payloads históricos. O [manifesto da revisão](evidence/interface-v4/review-manifest.json) registra fontes, normalização de hashes, assets e capturas; a [comparação](evidence/interface-v4/comparison.json) contém 14 pares nas mesmas dimensões e estados. As evidências v2, v3 e de restauração continuam históricas, sem substituição de seus resultados.

A [conferência posterior das imagens](image-review.md) reproduziu o renderer, CSS, JavaScript e assets v4 disponíveis naquela execução. Os resultados e comparações abaixo pertencem à revisão v4 original; seus arquivos não foram sobrescritos pela evolução de perfis.

## Produto, diagnóstico e duas composições

Quem confere o fechamento precisa separar três perguntas: **o que aconteceu com a tentativa**, **o que já está publicado** e **quais arquivos explicam a publicação**. Não há acompanhamento ao vivo, edição ou execução pela página.

O baseline já preservava essa separação e os valores, mas usava a mesma luminosidade para contexto, decisão e análise. A marca era um pequeno arranjo de blocos; a fonte efetiva era Segoe UI do sistema. Em Indicadores, a lista de produtos ocupava uma coluna alta e as 360 observações loja/dia ficavam num disclosure. A leitura exata existia, mas comparar distribuição exigia percorrer a tabela.

Antes de implementar, foram renderizadas duas propostas com **o mesmo snapshot demo30k, fonte, valores e viewport de 1440 × 1000**:

| Proposta                                                     | Composição                                                                                | Decisão                                                                                                                                           |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| [A — panorama comercial](images/interface-v4/proposta-a.png) | Publicação e métricas numa faixa; matriz loja/dia primeiro; série e ranking lado a lado   | Escolhida. Usa a largura para comparar as duas dimensões e mantém a identidade junto dos totais.                                                  |
| [B — mesa de consulta](images/interface-v4/proposta-b.png)   | Publicação e métricas numa coluna contextual; série, ranking e matriz na coluna principal | Rejeitada para este recorte. A coluna reduz a análise e empurra loja/dia para o fim. Não há uma tarefa de edição que justifique um inspetor fixo. |

As propostas são explorações da interface com dados históricos sintéticos, não provas novas do pipeline. A implementação final acrescenta limites monetários da escala, teclado, valores exatos, fontes licenciadas, estados e tabelas. O espaço abaixo de uma série curta fica livre: não se cria gráfico ou métrica para completar uma coluna.

## Pesquisa visual e o que foi aplicado

As fontes abaixo foram abertas e suas figuras/interfaces inspecionadas em navegador. Documentação, exemplo de biblioteca e portfólio conceitual não são pesquisa com usuários do nosso produto. As escolhas são inferências de design, sem alegar aprovação, exclusividade da marca ou produtividade medida.

| Fonte primária e tipo                                                                                                                                                              | Observação útil                                                                         | Adaptação e rejeição                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Linear, relato do redesign de 2024](https://linear.app/now/how-we-redesigned-the-linear-ui) — artigo com figuras reais                                                            | A moldura, a vista e os detalhes têm camadas distintas; alinhamentos reduzem competição | Navegação compacta, contexto de publicação escuro, análise branca, registro técnico neutro. Não copiamos layout, marca, ícones ou controle de tarefas.                                                  |
| [Carbon Charts: barras](https://charts.carbondesignsystem.com/bar) — exemplo executável, versão 1.27.20 observada                                                                  | Comparação horizontal com nomes legíveis e origem em zero                               | Ranking por unidades já fornecido pelo payload, valor na própria linha e tabela com receita. Sem legenda de doze cores, reordenação por receita ou barras com base truncada.                            |
| [Carbon Charts: heatmap](https://charts.carbondesignsystem.com/heatmap) e [escalas](https://carbondesignsystem.com/data-visualization/color-palettes/) — exemplo executável e guia | Duas dimensões categóricas/temporais e intensidade para magnitude                       | Loja × dia, limites em BRL, leitura selecionável e tabela equivalente. Hachura/traço para ausência; 0 explícito. Intensidade não indica sucesso, anomalia ou entrega pendente.                          |
| [Radix: composição da escala](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale) — documentação visual                                              | Fundo, superfície, borda, ação e texto têm funções diferentes                           | Tokens próprios por função; não importamos biblioteca nem tratamos um tom bonito como prova de contraste.                                                                                               |
| [Source Sans, Adobe](https://github.com/adobe-fonts/source-sans) e [IBM Plex](https://www.ibm.com/plex/) — projetos oficiais                                                       | Famílias próprias para interfaces, com numerais e acentos verificáveis                  | [Comparação renderizada](images/interface-v4/tipografia.png): Source Sans 3 escolhida para a leitura comercial. Plex foi alternativa, não asset do produto.                                             |
| [Swavee, Tobi Victor e Nifemi Adelana](https://www.behance.net/gallery/241721015/Visual-Identity-design-for-Swavee) — portfólio conceitual dos autores, abril de 2026              | Palavra, símbolo e aplicações formam um sistema coerente                                | Inspiração somente para consistência entre marca completa, compacta e mono. Nenhuma forma, cor proprietária, imagem ou código foi copiado; efeitos de vidro e argumentos promocionais foram rejeitados. |

Prefect/GX continuam explicando a proximidade entre tentativa, resultado e regra nas revisões anteriores. Nesta rodada, não foram usados como justificativa para repetir a mesma estrutura. A [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) foi relida: semântica nativa, foco, movimento reduzido, texto longo, carregamento de fonte e estados. A revisão aplicou critérios de composição, semântica, foco e interação; React não se aplica ao renderer Python.

## Identidade, fonte, superfícies e movimento

A marca original combina três linhas de registro com um V aberto, usando a mesma geometria no [símbolo compacto](../src/retail_pipeline/assets/brand-mark.svg), [monocromático](../src/retail_pipeline/assets/brand-mono.svg) e [favicon](../src/retail_pipeline/assets/favicon.svg). O nome completo é texto real ao lado do símbolo. O SVG decorativo do link é ocultado da árvore acessível; o nome continua legível. A marca não comunica o resultado da execução: somente os rótulos de estado o fazem.

A fonte **Source Sans 3 VF** é carregada de WOFF2 local e embutida como data URI em cada HTML. Não depende de Google Fonts, CDN ou rede. O arquivo original tem **170.188 bytes**; o Base64 acrescenta aproximadamente 227 KB por relatório. Esse é o custo consciente de um artefato portátil, sem declarar ganho de desempenho. O wheel inclui fonte, SVGs e licença; um render isolado diretamente do wheel confirmou os recursos. [Origem, commit e SHA](evidence/interface-v4/assets.json).

O [OFL 1.1 completo](../src/retail_pipeline/assets/source-sans-LICENSE.md), com copyright, permanece no pacote e no HTML gerado, em “Licença da fonte”. Não houve modificação da fonte. O [exame dos glifos](evidence/interface-v4/font-glyphs.json) confirma os caracteres PT-BR testados e avanços iguais dos dígitos por padrão — não se afirma que exista uma feature `tnum`. A [prova do navegador](evidence/interface-v4/visual-review.json) registra `SourceSans3VF`, `isCustomFont: true` em título, valor monetário e produto, com rede offline.

Tokens principais: texto `#263248`, apoio `#596274`, marca/foco `#49488F`, base `#F2F3F5`, contexto `#E5E8EF` e análise branca. Erro `#923B35`, confirmação `#226348` e alerta `#76550E` acompanham palavras. A escala azul da matriz representa receita; a barra índigo representa unidades. Não são estados operacionais.

Corpo de 16 px; tabelas de 14 px; metadados de 12–13 px; títulos de 28–32 px. IDs usam monoespaçada. Valores extensos continuam inteiros: tamanho mínimo de 19 px e rolagem local focável se necessária, sem cortar centavos. Conteúdo centralizado, máximo de 1376 px com margens internas de 24 px; gutters e superfícies compartilham eixos. Transições de 180 ms servem apenas a hover, foco e seleção, desativadas com `prefers-reduced-motion`. Não há números animados, spinner de execução nem movimento infinito.

## Telas e dados

| Vista       | Tarefa, composição e próximo destino                                                                                                                                                                  | Limites preservados                                                                                                                           |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Execução    | Decisão, causa, lote e início em contexto próprio; cobertura e ocorrências numa superfície de conferência. “Conferir pendência” leva o foco ao registro. No mobile, a decisão vem antes da cobertura. | S02 pendente não equivale a erro nas vendas recebidas. S03 pode confirmar zero movimento. Contadores e tempos permanecem sob demanda.         |
| Indicadores | Identidade, período e totais da publicação numa unidade; matriz primeiro, depois série e ranking. No mobile, a ordem é Matriz → Série → Ranking.                                                      | A tentativa bloqueada não troca a publicação disponível. “Publicação anterior preservada” é explícito. Nenhum CTA para abrir a própria vista. |
| Arquivos    | Registro de publicação em superfície contextual; versões, lotes e referências numa superfície documental. IDs de tentativa e última falha têm disclosures próprios.                                   | Copiar ou selecionar ID é a ação real; não há botão de download, deploy, reexecução ou atualização.                                           |

Exemplo de bloqueio: S01 e S03 recebidas, S03 com zero confirmado, S02.csv ausente → **2 de 3 lojas confirmadas**, causa visível e publicação anterior de **R$ 64,00**. O período da tentativa não está no payload e aparece como não informado; não se toma emprestada a janela da publicação.

### Pergunta, métrica, grão e representação

| Informação        | Fonte e significado                                                  | Representação e cuidado                                                                                                                                                    |
| ----------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Receita líquida   | `summary.net_revenue_brl`; descontos aplicados, cancelados excluídos | Valor exato BRL, sem cor de aprovação ou comparação inventada.                                                                                                             |
| Unidades e vendas | Campos já agregados pelo leitor; vendas distintas por loja/dia       | Numerais tabulares; itens e unidades não são a mesma contagem.                                                                                                             |
| Ticket            | `average_ticket_brl`, calculado no leitor a partir de receita/vendas | Sem vendas: indisponível, não ticket zero. Venda gratuita com vendas existentes pode ter ticket zero.                                                                      |
| Receita por dia   | `daily`, um dia comercial em America/Sao_Paulo                       | Posição por calendário; lacunas interrompem a linha. Receita não informada não ganha ponto zero. Tabela preserva todos os valores do recorte.                              |
| Produtos          | `products`, ordenado por unidades, receita e ID no leitor; até 20    | Barra horizontal por unidades, começando em zero. Não existe reclassificação global por receita sobre um recorte já limitado. Receita continua na tabela.                  |
| Loja × dia        | `stores`, até 500 linhas do grão loja/dia                            | Cor sequencial por receita daquela observação. Zero: célula com 0; sem observação ou valor ausente: hachura e traço. Não se infere loja esperada nem cobertura de entrega. |

A matriz não soma registros, interpola dias ou calcula indicador novo. A razão usada para cor/largura é apenas escala gráfica. Duplicatas de loja/dia recebem `!` e remetem à tabela, sem escolher ou somar uma receita silenciosamente. Datas não interpretáveis, mais de 366 dias entre extremos ou mais de 1.200 células possíveis usam um aviso e a tabela completa do recorte. O limite é verificado **antes** de materializar dias; datas 0001/1800/9999 não criam milhões de elementos. Totais sempre pertencem ao conjunto publicado; os avisos de truncamento do payload continuam explícitos.

A matriz usa tabela semântica e valores textuais equivalentes. Com JavaScript, somente uma célula entra no percurso Tab; setas, Home e End mudam a seleção e o valor visível. “Consultar linha na tabela” revela e foca o registro. Sem JavaScript, a âncora nativa abre o detalhe correspondente. Nenhuma informação essencial depende só de hover ou da cor.

## Estados e crítica das capturas

| Estado                                                | Captura da revisão v4                                                                                                                                                                                      |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Publicado, demo30k                                    | [Execução](images/interface-v4/report.png), [Indicadores](images/interface-v4/indicators.png), [Arquivos](images/interface-v4/files.png) — 12 lojas, 30 dias, 360 linhas loja/dia e 12 produtos históricos |
| Bloqueio de cobertura                                 | [Desktop](images/interface-v4/blocked.png), [390 px](images/interface-v4/blocked-report-qualidade-390.png), [1024 px](images/interface-v4/blocked-report-qualidade-1024.png)                               |
| Erro nos registros, sem publicação                    | [Ocorrências em 390 px](images/interface-v4/quality-mobile.png)                                                                                                                                            |
| Falha antes de publicar / retomada                    | [Falha](images/interface-v4/failure.png), [retomada](images/interface-v4/recovered.png): R$ 57 e R$ 77 preservados                                                                                         |
| Auditoria incompleta, vazio, sem conclusão            | [Auditoria](images/interface-v4/audit.png), [vazio](images/interface-v4/empty.png), [sem resultado final](images/interface-v4/running.png) — fixtures, sem nova execução                                   |
| Zero / ausência / valor extenso                       | [Zero](images/interface-v4/zero-fixture-320.png), [ausência](images/interface-v4/missing-metrics-fixture-320.png), [valor grande](images/interface-v4/large-fixture-320.png)                               |
| Matriz com ausência, zero e negativo / datas extremas | [Semântica visual](images/interface-v4/matrix-fixture-390.png), [fallback](images/interface-v4/extreme-dates-fixture-390.png) — fixtures de campos isolados, não fechamentos reconciliados                 |
| IDs longos / impressão                                | [320 px](images/interface-v4/long-files-320.png), [CSS de impressão](images/interface-v4/print-preview.png)                                                                                                |

Os arquivos `*-fixture` de [render_review.py](../scripts/render_review.py) são cenários de apresentação, explicitamente rotulados. O contrato não passou a permitir vendas negativas: os casos negativos exercitam sinal/escala, não uma regra nova de receita. Estado desconhecido e validado sem publicação também têm capturas e assertions na suite.

A inspeção identificou e corrigiu problemas concretos, além de overflow:

- O primeiro agrupamento da matriz repetia mês/ano em fonte minúscula. Agora há um cabeçalho por mês e dias legíveis.
- Um cabeçalho agrupado fez colunas se sobreporem na interação sem JS. Colunas explícitas corrigiram a geometria; a âncora nativa foi exercitada novamente.
- O símbolo ativo e a leitura da matriz precisavam permanecer juntos; seleção e link exato usam a mesma célula, sem 360 paradas de Tab.
- O valor de R$ 1.234.567.890.123,45 quebrava os centavos em 320 px. A versão final preserva o número inteiro e seu foco, sem abreviação.
- O primeiro screenshot de Arquivos congelou a animação entre duas abas. As capturas finais usam movimento reduzido; o comportamento normal de 180 ms é testado separadamente.
- O aviso de snapshot desaparecia com o header compacto. No mobile, “Snapshot · somente leitura” fica junto do título de contexto.
- O espaço abaixo da decisão era branco sem conteúdo. Agora o contexto termina naturalmente e a análise ocupa sua própria superfície; não se estica conteúdo para simular densidade.

A matriz mantém rolagem horizontal local em telas estreitas. Isso preserva eixo e dimensões; os registros exatos continuam acessíveis. A série também mantém sua tabela equivalente. A inspeção não declarou toda a paginação de PDF aprovada a partir de um screenshot de mídia print.

## Matriz de onze dimensões — antes e depois

Esta matriz é o histórico da revisão v4 de 22/09/2026. Suas classificações C, PC, NA e NV descrevem aquele baseline, candidato e protocolo. O resultado de outros motores, por exemplo, permaneceu NV na v4; ele não classifica o candidato de UI/UX de outubro.

Legenda: **C** = Conforme no escopo descrito; **PC** = Parcialmente conforme; **NC** = Não conforme; **NV** = Não verificado; **NA** = Não aplicável, com motivo. Cada célula compara **antes → depois**. Não há nota média nem certificação. A classificação é uma avaliação técnica das provas, não aprovação de usuários.

O antes é exclusivamente o baseline visual `636e8408f1108ce387ddc291318d2d1ebe042dee`; o depois é a fonte v4 identificada no manifesto. Os [14 pares](evidence/interface-v4/comparison.json) usam os mesmos cinco payloads, estados e dimensões. As [provas v3](evidence/interface-v3/review-manifest.json) descrevem as capacidades já existentes no baseline; não se creditam navegação, separação tentativa/publicação ou tabelas exatas como funcionalidades novas. A demonstração editorial posterior tem outros dados e não substitui essa comparação.

| Dimensão                           | Execução | Indicadores | Arquivos | Fundamento e limite da classificação                                                                                                                                                                                                 |
| ---------------------------------- | -------- | ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1. Público e tarefa                | C→C      | C→C         | C→C      | Tentativa, publicação e origem já eram separadas; a composição reforça essas tarefas. Não houve estudo com usuários.                                                                                                                 |
| 2. Hierarquia e organização        | PC→C     | PC→C        | PC→C     | Os pares mostram superfícies antes semelhantes; agora decisão/cobertura, publicação/análise e registro documental têm grupos próprios.                                                                                               |
| 3. Layout e densidade              | PC→C     | PC→C        | PC→C     | Matriz ocupa a largura, série/ranking têm altura natural e as três vistas reorganizam-se em telas estreitas. [Geometria e capturas](evidence/interface-v4/visual-review.json).                                                       |
| 4. Identidade, tipografia e cor    | PC→C     | PC→C        | PC→C     | Fonte do SO e marca anterior substituídas por assets locais; fonte efetiva, glifos, contraste amostrado e estados textuais conferidos. Não é certificação integral de contraste.                                                     |
| 5. Indicadores, gráficos e tabelas | C→C      | PC→C        | C→C      | Cobertura e referências exatas preservadas; ranking zero-base, matriz e tabela equivalente acrescentam comparação. Gráfico em Arquivos é NA: a tarefa é consultar IDs/versões.                                                       |
| 6. Navegação e ações               | C→C      | C→C         | C→C      | Hash, foco, retorno e detalhes preservados; roving/setas e âncora da matriz exercitados, cópia/fallback conferidos. Não há filtro remoto ou ação de pipeline.                                                                        |
| 7. Estados e atualização           | C→C      | PC→C        | C→C      | Fixtures distinguem bloqueio, falha, unknown, zero e ausência. Em Indicadores, a publicação vazia real exigiu correção separada do leitor, descrita abaixo; não é mérito apenas do redesign.                                         |
| 8. Acessibilidade e responsividade | PC→PC    | PC→PC       | PC→PC    | Teclado, foco, 320–1440 px, reflow, sem JS, contraste selecionado e [axe](evidence/interface-v4/accessibility.json) conferidos. Leitor de tela, outros motores e zoom nativo permanecem NV.                                          |
| 9. Desempenho                      | PC→PC    | PC→PC       | PC→PC    | Relatório local sem polling; tamanho/custo da fonte e limite da matriz documentados. Hardware lento e Web Vitals permanecem NV; não se afirma ganho de velocidade.                                                                   |
| 10. Manutenção e reutilização      | C→C      | C→C         | C→C      | Renderer/CSS separados já existiam; helpers e recursos no wheel mantêm essa separação. [Pacote e checks da fonte integrada](evidence/interface-v4/merged/checks.json).                                                               |
| 11. Dados, regras e permissões     | C→C      | PC→C        | C→C      | Valores, tabelas, IDs e fontes dos cinco payloads são equivalentes. Zero aditivo de publicação vazia foi corrigido e testado separadamente; ticket/datas ausentes continuam ausentes. Autorização/edição de tela são NA no snapshot. |

“C” nas dimensões visuais limita-se aos estados e larguras conferidos. Carregamento remoto, respostas fora de ordem, formulários, permissões de tela e paginação remota são **NA**: o HTML não consulta uma API nem modifica dados. A apresentação sem JavaScript, a impressão e os links locais são aplicáveis. A paginação completa do PDF permanece **NV**.

### Problemas tratados e prioridades

As prioridades abaixo expressam o impacto do problema observado, sem transformar refinamentos em falhas de domínio. Validação visual não substitui os testes de preservação dos valores.

| Tela/componente                    | Evidência e impacto no baseline ou na primeira iteração                                             | Prioridade                 | Correção                                                                                  | Validação existente                                                                        |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Todas / contexto e análise         | Superfícies semelhantes faziam identidade, decisão e análise competir                               | P2                         | Contexto, análise e documento com papéis e eixos próprios                                 | Pares do mesmo baseline e três vistas em cinco larguras                                    |
| Indicadores / produtos e loja×dia  | Lista alta e 360 observações recolhidas exigiam percorrer a tabela para comparar distribuição       | P2                         | Matriz, ranking horizontal e tabelas exatas; limites antes de alocar células              | Comparação de dados, `matrixChecks` e `baselineComparisons` no registro do navegador       |
| Indicadores / matriz sem JS        | Cabeçalho agrupado sobrepôs colunas na primeira iteração; a âncora precisava alcançar a linha exata | P1                         | Colunas explícitas e disclosure nativo; uma célula no percurso Tab com JS                 | `matrixChecks`, `no_script` e navegação por teclado                                        |
| Todas / números extensos em 320 px | Centavos quebravam de linha na primeira iteração, prejudicando a leitura monetária                  | P1                         | Número íntegro e rolagem local focável, sem abreviar                                      | Fixture de valor grande, `long_content` e captura de 320 px                                |
| Todas / contexto móvel             | O header compacto ocultava a condição de snapshot                                                   | P2                         | “Snapshot · somente leitura” junto do título de contexto                                  | Capturas móveis e `refinements` no registro do navegador                                   |
| Indicadores / publicação vazia     | O leitor retornava `None` para soma de zero linhas; o novo formatter revelou a ausência indevida    | P1, preexistente no leitor | Contagem explícita de linhas e zero apenas para totais aditivos vazios; correção separada | Integrações de fronteiras e checks integrados, sem reatribuir o resultado à mudança visual |

No encerramento da v4, as próximas validações eram **P2**, tecnologia assistiva, zoom nativo e outro motor de navegador; **P3**, hardware lento e PDF página a página. Naquela matriz, a dimensão 8 permaneceu PC, a 9 permaneceu PC e a paginação integral do PDF permaneceu NV. Axe, tamanho do arquivo e screenshots não substituem essas verificações.

## Verificação, origem e limites

Os resultados abaixo pertencem à revisão v4 e à sua integração de setembro. As contagens de 200 e 234 unitários, o axe, o contraste e os limites de navegador não foram reatribuídos à fonte de UI/UX de outubro. Os recibos vinculados conservam seus números, datas e hashes originais.

- **200 testes unitários no candidato**, incluindo 50 do renderer; Ruff, formatação e mypy. Após integrar os 34 testes da prova de estado, **234 unitários**, lint, formato, tipos, wheel e smoke isolado passaram na fonte combinada. [Verificação após integração](evidence/interface-v4/merged/checks.json). [Comandos/versões](evidence/interface-v4/checks.json), [JUnit](evidence/interface-v4/unit-tests.xml). O primeiro gate de tipos pediu uma anotação `list[str]`, corrigida; nenhuma regra foi afrouxada.
- Wheel construído sem rede; oito recursos de CSS/JS/fonte/marca/licença correspondem aos bytes da fonte. Um Python isolado importou o wheel e gerou HTML com fonte e OFL. O módulo Python do loader também foi conferido no pacote.
- Edge/Playwright: **15 combinações principais** (três vistas × 1440/1366/768/390/320), **30 capturas** da suite, mais **14 pares** antes/depois. Hash, histórico, skip-link, foco, cópia/fallback, disclosures, estados, roving, linha exata e ausência de erro JS passaram. [Registro](evidence/interface-v4/visual-review.json).
- **Axe: 14 vistas, zero violações automáticas** nas regras WCAG selecionadas. [Resultado completo](evidence/interface-v4/accessibility.json). Os itens `incomplete` de contraste em SVG não são convertidos em “passou”: os tokens correspondentes foram conferidos separadamente.
- Oito pares de contraste textual: mínimo **5,524:1**. Bordas de campo verificadas ≥3:1. Estados mantêm texto; zero/ausência da matriz têm marca distinta. Isso é amostragem, não certificação integral de contraste.
- Ampliação CSS 200% e viewport de 683 CSS px/DPR2, sem alegar zoom nativo. Leitura móvel, strings longas e valor monetário extenso sem overflow da página. Controles primários têm ao menos 24 CSS px de altura; a matriz usa células de 26 px e uma parada de Tab.
- Sem JS: três painéis, detalhes nativos, dados exatos, IDs selecionáveis e link de célula funcionam. Print: painéis e disclosures visíveis. Sem validação integral de paginação PDF.
- Offline: fonte custom efetiva em título/número/ranking; **zero requisições HTTP externas**. A licença inteira permanece no HTML.
- Igualdade de métricas, todas as tabelas, IDs e fontes dos **cinco payloads históricos**. Os hashes desses JSONs continuam iguais ao baseline; escala gráfica não altera dados de negócio.

O replay de interface não reexecutou lotes, demo ou benchmark. Em trabalho separado, a investigação do CI encontrou que `Spark.sum` sobre a publicação vazia devolvia `None`: o leitor agora conta linhas e define zero somente para totais aditivos de **zero linhas**, preservando ticket/datas ausentes e valores não informados quando há linhas. [Leitor](../src/retail_pipeline/reporting.py), [integrações de fronteiras](../tests/integration/test_boundaries.py). Três integrações passaram para essa correção, incluindo vazio/cancelamento/venda gratuita e datas extremas. Aquele processo carregou o renderer antes de ajustes visuais finais; não é descrito como teste de toda a fonte final. O CI do commit integrado é o aceite remoto correspondente.

A apresentação está em [report_view.py](../src/retail_pipeline/report_view.py), [report.css](../src/retail_pipeline/report.css), [report.js](../src/retail_pipeline/report.js) e [report_assets.py](../src/retail_pipeline/report_assets.py). Regressões: `_store_matrix`, `_product_ranking`, `_revenue_chart` e o [teste de relatório](../tests/unit/test_reporting.py); recursos empacotados no [pyproject.toml](../pyproject.toml). A normalização LF aplica-se somente a textos: WOFF2 é binário e seu SHA cobre os bytes originais.

## Reprodução e histórico

Os comandos abaixo geram uma nova rodada com a fonte presente no checkout. Para reproduzir os bytes da v4, é preciso usar a fonte identificada no manifesto histórico e os mesmos inputs. Executá-los na fonte de outubro não renova os resultados da v4 nem substitui o protocolo atual de 22 casos.

```sh
PYTHONPATH=src python scripts/render_review.py
node scripts/visual-review.cjs
node scripts/a11y-review.cjs
ruff check src tests scripts
ruff format --check src tests scripts
mypy src/retail_pipeline
python -m pytest tests/unit -q
```

Playwright e axe são ferramentas opcionais de desenvolvimento, não dependências do relatório. `PLAYWRIGHT_MODULE`/`AXE_MODULE` podem apontar para módulos instalados; `PLAYWRIGHT_CHANNEL=msedge` reproduz o motor desta revisão. `REVIEW_BASELINE_DIR` deve conter os HTMLs do commit inicial com os mesmos payloads; habilita a comparação e os pares. Sem essa variável, a suite funcional continua.

Novas execuções gravam em `artifacts/interface-review`, sem sobrescrever as evidências históricas. `REVIEW_HTML_DIR`, `REVIEW_IMAGES` e `REVIEW_EVIDENCE` permitem manter toda a conferência fora do repositório; veja a [reprodução com saídas separadas](image-review.md#reproduzir-a-conferência).

Histórico preservado: [revisão v3](evidence/interface-v3/review-manifest.json), [v2](evidence/interface-v2/review-manifest.json), [jornadas](evidence/interface-journeys/review.json) e [limpeza v2](evidence/interface-v2/cleanup.json). Esses registros descrevem fontes e contagens anteriores. A [verificação operacional](verification.md), o [problema e solução](problem-solution.md) e as [decisões técnicas](decisoes-tecnicas.md) continuam separados desta prova de apresentação.

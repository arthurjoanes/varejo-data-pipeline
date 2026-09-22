# Qualidade da interface de fechamento

Direção visual v4, revisada em 22/09/2026. Baseline visual: `636e8408f1108ce387ddc291318d2d1ebe042dee`. Esta revisão usa os mesmos cinco payloads históricos. O [manifesto da revisão](evidence/interface-v4/review-manifest.json) registra fontes, normalização de hashes, assets e capturas; a [comparação](evidence/interface-v4/comparison.json) contém 14 pares nas mesmas dimensões e estados. As evidências v2, v3 e de restauração continuam históricas, sem substituição de seus resultados.

## Produto, diagnóstico e duas composições

Quem confere o fechamento precisa separar três perguntas: **o que aconteceu com a tentativa**, **o que já está publicado** e **quais arquivos explicam a publicação**. Não há acompanhamento ao vivo, edição ou execução pela página.

O baseline já preservava essa separação e os valores, mas usava a mesma luminosidade para contexto, decisão e análise. A marca era um pequeno arranjo de blocos; a fonte efetiva era Segoe UI do sistema. Em Indicadores, a lista de produtos ocupava uma coluna alta e as 360 observações loja/dia ficavam num disclosure. A leitura exata existia, mas comparar distribuição exigia percorrer a tabela.

Antes de implementar, foram renderizadas duas propostas com **o mesmo snapshot demo30k, fonte, valores e viewport de 1440 × 1000**:

| Proposta | Composição | Decisão |
| --- | --- | --- |
| [A — panorama comercial](images/interface-v4/proposta-a.png) | Publicação e métricas numa faixa; matriz loja/dia primeiro; série e ranking lado a lado | Escolhida. Usa a largura para comparar as duas dimensões e mantém a identidade junto dos totais. |
| [B — mesa de consulta](images/interface-v4/proposta-b.png) | Publicação e métricas numa coluna contextual; série, ranking e matriz na coluna principal | Rejeitada para este recorte. A coluna reduz a análise e empurra loja/dia para o fim. Não há uma tarefa de edição que justifique um inspetor fixo. |

As propostas são explorações da interface com dados históricos sintéticos, não provas novas do pipeline. A implementação final acrescenta limites monetários da escala, teclado, valores exatos, fontes licenciadas, estados e tabelas. O espaço abaixo de uma série curta fica livre: não se cria gráfico ou métrica para completar uma coluna.

## Pesquisa visual e o que foi aplicado

As fontes abaixo foram abertas e suas figuras/interfaces inspecionadas em navegador. Documentação, exemplo de biblioteca e portfólio conceitual não são pesquisa com usuários do nosso produto. As escolhas são inferências de design, sem alegar aprovação, exclusividade da marca ou produtividade medida.

| Fonte primária e tipo | Observação útil | Adaptação e rejeição |
| --- | --- | --- |
| [Linear, relato do redesign de 2024](https://linear.app/now/how-we-redesigned-the-linear-ui) — artigo com figuras reais | A moldura, a vista e os detalhes têm camadas distintas; alinhamentos reduzem competição | Navegação compacta, contexto de publicação escuro, análise branca, registro técnico neutro. Não copiamos layout, marca, ícones ou controle de tarefas. |
| [Carbon Charts: barras](https://charts.carbondesignsystem.com/bar) — exemplo executável, versão 1.27.20 observada | Comparação horizontal com nomes legíveis e origem em zero | Ranking por unidades já fornecido pelo payload, valor na própria linha e tabela com receita. Sem legenda de doze cores, reordenação por receita ou barras com base truncada. |
| [Carbon Charts: heatmap](https://charts.carbondesignsystem.com/heatmap) e [escalas](https://carbondesignsystem.com/data-visualization/color-palettes/) — exemplo executável e guia | Duas dimensões categóricas/temporais e intensidade para magnitude | Loja × dia, limites em BRL, leitura selecionável e tabela equivalente. Hachura/traço para ausência; 0 explícito. Intensidade não indica sucesso, anomalia ou entrega pendente. |
| [Radix: composição da escala](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale) — documentação visual | Fundo, superfície, borda, ação e texto têm funções diferentes | Tokens próprios por função; não importamos biblioteca nem tratamos um tom bonito como prova de contraste. |
| [Source Sans, Adobe](https://github.com/adobe-fonts/source-sans) e [IBM Plex](https://www.ibm.com/plex/) — projetos oficiais | Famílias próprias para interfaces, com numerais e acentos verificáveis | [Comparação renderizada](images/interface-v4/tipografia.png): Source Sans 3 escolhida para a leitura comercial. Plex foi alternativa, não asset do produto. |
| [Swavee, Tobi Victor e Nifemi Adelana](https://www.behance.net/gallery/241721015/Visual-Identity-design-for-Swavee) — portfólio conceitual dos autores, abril de 2026 | Palavra, símbolo e aplicações formam um sistema coerente | Inspiração somente para consistência entre marca completa, compacta e mono. Nenhuma forma, cor proprietária, imagem ou código foi copiado; efeitos de vidro e argumentos promocionais foram rejeitados. |

Prefect/GX continuam explicando a proximidade entre tentativa, resultado e regra nas revisões anteriores. Nesta rodada, não foram usados como justificativa para repetir a mesma estrutura. A [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) foi relida: semântica nativa, foco, movimento reduzido, texto longo, carregamento de fonte e estados. As skills `frontend-design` e `web-design-guidelines` orientaram plano, construção e crítica; React não se aplica ao renderer Python.

## Identidade, fonte, superfícies e movimento

A marca original combina três linhas de registro com um V aberto, usando a mesma geometria no [símbolo compacto](../src/retail_pipeline/assets/brand-mark.svg), [monocromático](../src/retail_pipeline/assets/brand-mono.svg) e [favicon](../src/retail_pipeline/assets/favicon.svg). O nome completo é texto real ao lado do símbolo. O SVG decorativo do link é ocultado da árvore acessível; o nome continua legível. A marca não comunica o resultado da execução: somente os rótulos de estado o fazem.

A fonte **Source Sans 3 VF** é carregada de WOFF2 local e embutida como data URI em cada HTML. Não depende de Google Fonts, CDN ou rede. O arquivo original tem **170.188 bytes**; o Base64 acrescenta aproximadamente 227 KB por relatório. Esse é o custo consciente de um artefato portátil, sem declarar ganho de desempenho. O wheel inclui fonte, SVGs e licença; um render isolado diretamente do wheel confirmou os recursos. [Origem, commit e SHA](evidence/interface-v4/assets.json).

O [OFL 1.1 completo](../src/retail_pipeline/assets/source-sans-LICENSE.md), com copyright, permanece no pacote e no HTML gerado, em “Licença da fonte”. Não houve modificação da fonte. O [exame dos glifos](evidence/interface-v4/font-glyphs.json) confirma os caracteres PT-BR testados e avanços iguais dos dígitos por padrão — não se afirma que exista uma feature `tnum`. A [prova do navegador](evidence/interface-v4/visual-review.json) registra `SourceSans3VF`, `isCustomFont: true` em título, valor monetário e produto, com rede offline.

Tokens principais: texto `#263248`, apoio `#596274`, marca/foco `#49488F`, base `#F2F3F5`, contexto `#E5E8EF` e análise branca. Erro `#923B35`, confirmação `#226348` e alerta `#76550E` acompanham palavras. A escala azul da matriz representa receita; a barra índigo representa unidades. Não são estados operacionais.

Corpo de 16 px; tabelas de 14 px; metadados de 12–13 px; títulos de 28–32 px. IDs usam monoespaçada. Valores extensos continuam inteiros: tamanho mínimo de 19 px e rolagem local focável se necessária, sem cortar centavos. Conteúdo centralizado, máximo de 1376 px com margens internas de 24 px; gutters e superfícies compartilham eixos. Transições de 180 ms servem apenas a hover, foco e seleção, desativadas com `prefers-reduced-motion`. Não há números animados, spinner de execução nem movimento infinito.

## Telas e dados

| Vista | Tarefa, composição e próximo destino | Limites preservados |
| --- | --- | --- |
| Execução | Decisão, causa, lote e início em contexto próprio; cobertura e ocorrências numa superfície de conferência. “Conferir pendência” leva o foco ao registro. No mobile, a decisão vem antes da cobertura. | S02 pendente não equivale a erro nas vendas recebidas. S03 pode confirmar zero movimento. Contadores e tempos permanecem sob demanda. |
| Indicadores | Identidade, período e totais da publicação numa unidade; matriz primeiro, depois série e ranking. No mobile, a ordem é Matriz → Série → Ranking. | A tentativa bloqueada não troca a publicação disponível. “Publicação anterior preservada” é explícito. Nenhum CTA para abrir a própria vista. |
| Arquivos | Registro de publicação em superfície contextual; versões, lotes e referências numa superfície documental. IDs de tentativa e última falha têm disclosures próprios. | Copiar ou selecionar ID é a ação real; não há botão de download, deploy, reexecução ou atualização. |

Exemplo de bloqueio: S01 e S03 recebidas, S03 com zero confirmado, S02.csv ausente → **2 de 3 lojas confirmadas**, causa visível e publicação anterior de **R$ 64,00**. O período da tentativa não está no payload e aparece como não informado; não se toma emprestada a janela da publicação.

### Pergunta, métrica, grão e representação

| Informação | Fonte e significado | Representação e cuidado |
| --- | --- | --- |
| Receita líquida | `summary.net_revenue_brl`; descontos aplicados, cancelados excluídos | Valor exato BRL, sem cor de aprovação ou comparação inventada. |
| Unidades e vendas | Campos já agregados pelo leitor; vendas distintas por loja/dia | Numerais tabulares; itens e unidades não são a mesma contagem. |
| Ticket | `average_ticket_brl`, calculado no leitor a partir de receita/vendas | Sem vendas: indisponível, não ticket zero. Venda gratuita com vendas existentes pode ter ticket zero. |
| Receita por dia | `daily`, um dia comercial em America/Sao_Paulo | Posição por calendário; lacunas interrompem a linha. Receita não informada não ganha ponto zero. Tabela preserva todos os valores do recorte. |
| Produtos | `products`, ordenado por unidades, receita e ID no leitor; até 20 | Barra horizontal por unidades, começando em zero. Não existe reclassificação global por receita sobre um recorte já limitado. Receita continua na tabela. |
| Loja × dia | `stores`, até 500 linhas do grão loja/dia | Cor sequencial por receita daquela observação. Zero: célula com 0; sem observação ou valor ausente: hachura e traço. Não se infere loja esperada nem cobertura de entrega. |

A matriz não soma registros, interpola dias ou calcula indicador novo. A razão usada para cor/largura é apenas escala gráfica. Duplicatas de loja/dia recebem `!` e remetem à tabela, sem escolher ou somar uma receita silenciosamente. Datas não interpretáveis, mais de 366 dias entre extremos ou mais de 1.200 células possíveis usam um aviso e a tabela completa do recorte. O limite é verificado **antes** de materializar dias; datas 0001/1800/9999 não criam milhões de elementos. Totais sempre pertencem ao conjunto publicado; os avisos de truncamento do payload continuam explícitos.

A matriz usa tabela semântica e valores textuais equivalentes. Com JavaScript, somente uma célula entra no percurso Tab; setas, Home e End mudam a seleção e o valor visível. “Consultar linha na tabela” revela e foca o registro. Sem JavaScript, a âncora nativa abre o detalhe correspondente. Nenhuma informação essencial depende só de hover ou da cor.

## Estados e crítica das capturas

| Estado | Prova atual |
| --- | --- |
| Publicado, demo30k | [Execução](images/interface-v4/report.png), [Indicadores](images/interface-v4/indicators.png), [Arquivos](images/interface-v4/files.png) — 12 lojas, 30 dias, 360 linhas loja/dia e 12 produtos históricos |
| Bloqueio de cobertura | [Desktop](images/interface-v4/blocked.png), [390 px](images/interface-v4/blocked-report-qualidade-390.png), [1024 px](images/interface-v4/blocked-report-qualidade-1024.png) |
| Erro nos registros, sem publicação | [Ocorrências em 390 px](images/interface-v4/quality-mobile.png) |
| Falha antes de publicar / retomada | [Falha](images/interface-v4/failure.png), [retomada](images/interface-v4/recovered.png): R$ 57 e R$ 77 preservados |
| Auditoria incompleta, vazio, sem conclusão | [Auditoria](images/interface-v4/audit.png), [vazio](images/interface-v4/empty.png), [sem resultado final](images/interface-v4/running.png) — fixtures, sem nova execução |
| Zero / ausência / valor extenso | [Zero](images/interface-v4/zero-fixture-320.png), [ausência](images/interface-v4/missing-metrics-fixture-320.png), [valor grande](images/interface-v4/large-fixture-320.png) |
| Matriz com ausência, zero e negativo / datas extremas | [Semântica visual](images/interface-v4/matrix-fixture-390.png), [fallback](images/interface-v4/extreme-dates-fixture-390.png) — fixtures de campos isolados, não fechamentos reconciliados |
| IDs longos / impressão | [320 px](images/interface-v4/long-files-320.png), [CSS de impressão](images/interface-v4/print-preview.png) |

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

“Conforme” refere-se ao escopo testado, não a certificação universal. A coluna anterior é o baseline v3, que já tinha funções úteis; não as creditamos como novas.

| Dimensão | Antes | Execução atual | Indicadores atuais | Arquivos atuais |
| --- | --- | --- | --- | --- |
| 1. Público e tarefa | Conforme na separação tentativa/publicação; aparência pouco própria | Decisão e cobertura como conferência | Distribuição e comparação da publicação | Identidade e origem como consulta documental |
| 2. Hierarquia | Parcial: superfícies semelhantes e análise escondida | Causa/ação/contexto separados dos contadores | Publicação+totais; matriz cedo; exatidão por tabela | Identidade contextual; versões e fontes legíveis |
| 3. Layout e densidade | Parcial: lista alta, geometria uniforme | Contexto e conferência em colunas; ordem móvel explícita | Matriz usa largura; série/ranking têm altura natural | Duas superfícies com espaçamento; uma coluna ≤900 px |
| 4. Identidade, tipo e cor | Parcial: marca genérica e fonte do SO | Marca original, Source Sans carregada, estados textuais | Números consistentes; cor de dados não é estado | IDs mono, conteúdo humano na fonte local |
| 5. Dados e visualização | Tabelas exatas, comparação visual limitada | Zero movimento distinto de pendência | Ranking zero-base, matriz exata, lacunas e limites | Versões/caminhos íntegros; gráfico não aplicável |
| 6. Navegação e ações | Conforme: hash, foco, cópia e detalhes | Mesmo destino para causa e registro | Matriz roving+setas, âncora para linha; sem filtro fictício | Cópia/fallback e IDs completos preservados |
| 7. Estados e atualização | Conforme nos estados já capturados | Bloqueio/falha/unknown/auditoria separados | Zero/ausência/sem publicação/recorte extremo explícitos | Ausência não gera botão para copiar ID vazio |
| 8. A11y e responsividade | Parcial: limites de auditoria documentados | Teclado, 320–1440, reflow, axe e contraste | Tabelas equivalentes, roving, semJS e fonte offline | Foco/seleção/cópia e rolagem local; sem leitor de tela completo |
| 9. Desempenho | Local sem rede; sem benchmark de produção | Sem polling/animação infinita | Matriz limitada antes de alocar; custo da fonte explícito | Sem chamadas remotas; sem alegação de Web Vitals |
| 10. Manutenção e reuso | Renderer/CSS separados, sem biblioteca | Estrutura local e estados existentes preservados | Helpers de visualização testados; fonte/brand no wheel | Helper de campos e fontes preservado; licença empacotada |
| 11. Regras, origem e permissões | Modelo correto; leitor vazio expunha ausência no CI | Cobertura não é taxa de erros | Cinco payloads iguais; nenhuma fórmula de domínio nova | IDs/fontes iguais; permissão/edição não aplicáveis |

A dimensão 8 continua **parcialmente conforme** quanto a leitor de tela, outros motores e zoom nativo; os checks citados passaram, mas não cobrem esses casos. A dimensão 9 é **parcialmente conforme** quanto a performance de produção, não medida. Autenticação, edição, paginação remota e ações de pipeline não se aplicam a este relatório estático.

## Verificação, origem e limites

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

Histórico preservado: [revisão v3](evidence/interface-v3/review-manifest.json), [v2](evidence/interface-v2/review-manifest.json), [jornadas](evidence/interface-journeys/review.json) e [limpeza v2](evidence/interface-v2/cleanup.json). Esses registros descrevem fontes e contagens anteriores. A [verificação operacional](verification.md), o [problema e solução](problem-solution.md) e as [decisões técnicas](decisoes-tecnicas.md) continuam separados desta prova de apresentação.

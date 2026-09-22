# Qualidade da interface de fechamento

Revisão de 22/09/2026. Baseline: `bff7a4ac5e9563c0a94fa81def27f3f4c7250853`. Esta rodada reconstrói a composição das três vistas do relatório, mantendo o pipeline e os payloads históricos. O [manifesto](evidence/interface-v3/review-manifest.json) identifica fontes, imagens e evidências da revisão; as revisões v2 continuam históricas.

## Produto e tarefas de leitura

O público é quem confere a entrega das lojas antes de usar um fechamento e quem precisa explicar de onde vieram os indicadores. A primeira pergunta é se o lote pode ser considerado publicado; a segunda é qual loja, arquivo ou regra explica o resultado. O relatório não é um monitor em tempo real.

| Vista | Pergunta e ação principal | Dados e limites |
| --- | --- | --- |
| Execução | O que aconteceu nesta tentativa? Conferir a loja/arquivo pendente ou abrir seu registro. | Estado, lote, início, cobertura, ocorrências, contadores e tempos capturados. Tempo medido não prova aprovação. |
| Indicadores | Quais valores pertencem à publicação disponível? Conferir receita, produtos e loja/dia. | Identidade e janela comercial da publicação; valores exatos nas tabelas. Tentativa bloqueada não substitui a publicação anterior. |
| Arquivos | Qual versão e qual entrada explicam esses valores? Consultar ou copiar o ID completo. | Publicação, execução, versões Delta, caminhos bronze e hashes capturados. Não há download, edição ou reexecução pela página. |

O exemplo central é concreto: S01 e S03 constam como recebidas; S03 confirmou zero movimento; S02.csv não chegou. A tela informa **2 de 3 lojas confirmadas**, mantém S02 pendente e explica a reposição dos bytes originais. A publicação anterior conserva **R$ 64,00**. Zero rejeições em registros recebidos não torna a cobertura completa.

O payload da tentativa não contém sua janela comercial. Por isso, **Período da entrega: não informado no snapshot** é explícito. O período de `summary` pertence à publicação e aparece apenas com os indicadores; usar essa data como período da tentativa bloqueada seria atribuir um dado a outra entidade.

## Arquitetura e escopo

O leitor em [reporting.py](../src/retail_pipeline/reporting.py) captura uma publicação e suas versões. [ReportPayload](../src/retail_pipeline/report_model.py) transporta esse resultado. [report_view.py](../src/retail_pipeline/report_view.py) produz o HTML com [CSS](../src/retail_pipeline/report.css) e [JavaScript](../src/retail_pipeline/report.js) locais. O wheel inclui esses dois assets pelo [pyproject.toml](../pyproject.toml).

Nesta rodada mudaram renderer, CSS, fixtures e verificadores da apresentação. O JavaScript existente, a captura por versão, o domínio, os contratos de ingestão, as fórmulas e as dependências de runtime permaneceram intactos. Não existe React neste frontend; migrar o stack não ajudaria a leitura do HTML offline.

## Direção visual e referências

O layout é uma folha de conferência de fechamento. Decisão, causa, destino e identidade ficam no mesmo bloco; uma lista de lojas torna a cobertura verificável sem expansão. Ocorrências detalham a causa; contadores e duração ficam em disclosures. O fluxo usa divisores e registros, sem transformar cada loja ou etapa em um card.

As cores separam texto `#24334B`, apoio `#536278`, marca/foco `#334FB0`, base `#F2F5FA`, superfície branca e linhas `#D5DEEB`. Erro `#963D37`, confirmação `#226348` e alerta `#76550E` acompanham rótulos textuais. Corpo de 15 px, conteúdo tabular de 14 px e metadados de 12 px usam Segoe UI/Aptos local; IDs usam Consolas. O conteúdo tem largura máxima de 1280 px; espaçamento principal de 24/28 px, reduzido em telas estreitas.

Referências consultadas, com limites:

- [Prefect: figura oficial de uma execução](https://github.com/PrefectHQ/prefect/blob/c352eb8668a97d31ba8e7636d26d929f0db84d48/docs/v3/img/ui/flow-run-details.png). A figura histórica aproxima identidade, resultado e horário. Aplicamos essa relação, sem DAG, retry ou controle de execução inexistente.
- [GX: Data Docs 0.18](https://docs.greatexpectations.io/docs/0.18/core/introduction/introduction/). A figura histórica aproxima regra e observação; aqui, esperado/recebido e arquivo/loja ficam juntos. Não importamos a aparência Bootstrap, percentuais globais nem código do produto.
- [Carbon: dashboards](https://carbondesignsystem.com/data-visualization/dashboards/) e [NN/g: progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/). Priorização e revelação de detalhes orientam a hierarquia; não justificam esconder a causa ou a cobertura.
- [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md), consultada em 22/09/2026: semântica nativa, foco, teclado, movimento reduzido, strings longas e estados explícitos. A skill `frontend-design` orientou plano e crítica visual; `web-design-guidelines`, a auditoria. Nenhum código, fonte, ícone ou imagem dessas referências foi copiado para o produto.

As observações nas referências são fatos de capturas/documentação. A escolha desta composição é uma inferência de design para nossas tarefas, não uma alegação de aprovação por usuários ou de ganho de produtividade medido.

## Inventário de telas e estados

| Entrada/estado | O que foi conferido | Evidência |
| --- | --- | --- |
| Publicado, 30 mil linhas históricas | 12 lojas, 30 dias, 360 linhas loja/dia, 12 produtos, valores e fontes | [Execução](images/interface-v3/report.png), [Indicadores](images/interface-v3/indicators.png), [Arquivos](images/interface-v3/files.png) |
| Bloqueio de cobertura | S02 pendente, S03 zero confirmado, causa e ação; R$ 64 anteriores | [Desktop](images/interface-v3/blocked.png), [390 px](images/interface-v3/blocked-report-qualidade-390.png), [1024 px](images/interface-v3/blocked-report-qualidade-1024.png) |
| Erro em registros, sem primeira publicação | Ocorrências distintas, campos e severidade; sem falsos indicadores | [Ocorrências no celular](images/interface-v3/quality-mobile.png) |
| Falha antes de publicar / retomada | R$ 57 preservados na falha; R$ 77 no snapshot posterior | [Falha](images/interface-v3/failure.png), [retomada](images/interface-v3/recovered.png) |
| Auditoria final incompleta | Publicação continua disponível; não reclassificar como falha anterior | [Fixture de auditoria](images/interface-v3/audit.png) |
| Sem tentativa/publicação | Ausência explícita; sem CTA para uma tentativa inexistente | [Fixture vazia](images/interface-v3/empty-fixture-qualidade-390.png) |
| Sem resultado final | Estado do snapshot; sem spinner, porcentagem ou promessa de atualização | [Fixture sem conclusão](images/interface-v3/running-fixture-qualidade-390.png) |
| Estado desconhecido / validado | Não inferir publicação ou falha a partir de estado insuficiente | [Suite de navegador](evidence/interface-v3/visual-review.json), testes do renderer |
| Zero / métricas ausentes | Zero monetário real difere de travessão; período desconhecido não vira período sem movimento | [Zero](images/interface-v3/zero-fixture-320.png), [ausência](images/interface-v3/missing-metrics-fixture-320.png) |
| Números e IDs longos | Valor exato sem abreviação; ID completo selecionável; sem vazamento horizontal da página | [Valor extenso](images/interface-v3/large-fixture-320.png), [IDs](images/interface-v3/long-files-320.png) |
| Datas sem observação | Espaçamento de calendário real; linha interrompida, sem criar zeros nos dias ausentes | [Fixture de lacunas](images/interface-v3/gaps-fixture-320.png), teste `test_chart_preserves_calendar_gaps_without_inventing_observations` |
| Sem JavaScript / impressão | Três painéis e disclosures nativos; impressão expõe os detalhes | [Registro](evidence/interface-v3/visual-review.json), [preview de impressão](images/interface-v3/print-preview.png) |

Os arquivos `*-fixture` são cenários de apresentação derivados em [render_review.py](../scripts/render_review.py), identificados como sintéticos no HTML. O stress de número grande e o cenário de lacunas alteram campos isolados para testar apresentação; não são fechamentos reconciliados nem provas operacionais.

O formatador também foi testado com `R$ -12,34`, preservando o sinal. Não foi inventado um fechamento negativo: o contrato vigente rejeita preços negativos e descontos maiores que o valor bruto. Esse teste cobre a formatação, não uma nova regra de receita ou série negativa no gráfico.

Não aplicáveis neste produto: autenticação/permissão, formulário de edição, filtros de dados, seleção múltipla, ordenação interativa, paginação remota, salvamento, polling e carregamento assíncrono. As três vistas e seus recortes são navegação por âncora, não filtros. Não foram inventados controles para preencher essa lista.

## Problemas encontrados e correções

| Vista / evidência inicial | Impacto | Prioridade | Correção | Validação |
| --- | --- | --- | --- | --- |
| Execução: cobertura fechada e duração em área dominante | Exigia abrir detalhes para descobrir qual loja faltava | P1 | Lista esperado/recebido visível, duração secundária | Mesma fixture: antes cobertura oculta; depois 2/3 e S02 visíveis; igualdade dos valores |
| Indicadores: cabeçalho da tentativa e CTA “Consultar indicadores” na própria vista | Confundia entidade consultada e destino | P1 | Publicação, horário e janela junto aos indicadores; CTA restrito a Execução | Sem CTA visível na vista; link leva ao ID completo correto |
| Indicadores: métrica ausente formatada como zero | A ausência parecia um resultado conhecido | P1 | Formatadores retornam travessão para `None`; zero continua zero | Regressões com payload incompleto, zero e valor monetário exato |
| Indicadores: linha ligava datas faltantes; ponto único fora do recorte móvel inicial | Sugeriria continuidade sem observação ou gráfico vazio | P1 | Posição por calendário, segmentos somente entre datas consecutivas; ponto único no início | Três pontos 01/02/05, um segmento; tabela intacta; ponto visível em 320 px |
| Indicadores: tabela alta afastava Loja/dia | Espaço grande sob o gráfico e comparação distante | P2 | Loja/dia abaixo do gráfico na coluna esquerda; Produtos usa coluna direita | Distância de 24 px, sem altura artificial; mobile mantém ordem do DOM |
| Arquivos: conteúdo da tentativa precedia o registro consultado | Identidade e versões perdiam unidade | P2 | Registro de publicação à esquerda, versões/fontes à direita; empilhamento no mobile | Screenshot e cópia do ID; versões/caminhos iguais ao baseline |
| Métrica extensa em 320 px quebrava no meio do número | Valor difícil de ler apesar de não haver overflow | P2 | Valor longo recebe largura inteira, sem truncar ou abreviar | Captura de R$ 1.234.567.890.123,45 e assertion do texto completo |
| Controles: bordas claras; grupo de ocorrências com ARIA sem papel | Limite visual fraco e nome acessível sem semântica adequada | P2 | Bordas com contraste ≥3:1; `role=group`; h1 global e h2 por vista | Contrastes 3,694/3,288; axe sem violação; leitura semântica e teclado |

Nenhum P0/P1 conhecido fica aberto no escopo testado. As limitações de cobertura de auditoria estão registradas abaixo e não são tratadas como aprovação implícita.

## Matriz de onze dimensões — antes e depois

“Conforme” significa atendido no escopo e nos estados examinados, não certificação geral. “Parcialmente conforme” indica limite explícito. O baseline já preservava funções úteis; elas não são creditadas como novas nesta rodada.

### Execução

| Dimensão | Antes | Depois / prova ou limite |
| --- | --- | --- |
| 1. Objetivo e público | Parcialmente conforme: diagnóstico existia; duração competia com decisão | Conforme: decisão, lote, causa, destino e cobertura guiam a conferência |
| 2. Hierarquia da informação | Parcialmente conforme: cobertura essencial recolhida | Conforme: lojas visíveis; contadores e tempos sob demanda |
| 3. Layout, alinhamento e densidade | Parcialmente conforme: contexto dividido em faixas e lateral | Conforme: uma folha, eixos comuns e lista de lojas; capturas 320–1440 |
| 4. Tipografia, cor e consistência | Parcialmente conforme: título genérico repetido entre vistas | Conforme: escala local, estados textuais, foco/contraste e borda integral |
| 5. Indicadores, gráficos e tabelas | Parcialmente conforme: resumo de cobertura não imediato | Conforme: 2/3 confirmado, zero movimento distinto de ausência; nenhum progresso inventado |
| 6. Navegação, filtros e ações | Conforme: âncoras/foco/detalhes funcionavam | Conforme: mesmos contratos; CTA leva à pendência; filtros de dados não aplicáveis |
| 7. Estados e atualização | Parcialmente conforme: vazio tinha CTA circular | Conforme: nenhum registro, desconhecido, bloqueado, falha e auditoria distintos; snapshot explícito |
| 8. Acessibilidade e responsividade | Parcialmente conforme: teclado/reflow prévios; sem auditoria abrangente | Parcialmente conforme: axe, teclado, contraste e reflow passam; leitor de tela e zoom nativo não verificados |
| 9. Performance | Parcialmente conforme: local sem rede, sem benchmark de produção | Parcialmente conforme: 0 requisições externas; HTML bloqueado menor; sem Lighthouse/Web Vitals |
| 10. Manutenção e reuso | Parcialmente conforme: regras de composição dispersas | Conforme: renderer/CSS separados, ledger reutilizado, verificadores e guia; sem dependência nova |
| 11. Dados, regras e permissões | Conforme: tentativa/publicação distintas no modelo | Conforme: modelo/leitor/domínio intactos; equivalência de cinco snapshots; permissão não aplicável |

### Indicadores

| Dimensão | Antes | Depois / prova ou limite |
| --- | --- | --- |
| 1. Objetivo e público | Parcialmente conforme: tentativa dominava a vista de vendas | Conforme: publicação identificada e recortes de consulta |
| 2. Hierarquia da informação | Não conforme: ação para a própria vista e identidade dispersa | Conforme: identidade e período da publicação acima das métricas |
| 3. Layout, alinhamento e densidade | Parcialmente conforme: espaço sob gráfico e tabela loja/dia distante | Conforme: gráfico/loja-dia à esquerda e produtos à direita; coluna única ≤1100 px |
| 4. Tipografia, cor e consistência | Parcialmente conforme: valor extenso quebrava em coluna estreita | Conforme: números tabulares; valor longo ocupa linha inteira no mobile |
| 5. Indicadores, gráficos e tabelas | Parcialmente conforme: tabela exata, mas ausência virava zero e lacunas eram ligadas | Conforme: calendário real, linha descontínua, zeros/ausência distintos, BRL e grão explícitos |
| 6. Navegação, filtros e ações | Parcialmente conforme: CTA redundante | Conforme: recortes levam a gráfico/produtos/loja-dia; sem filtro inexistente |
| 7. Estados e atualização | Parcialmente conforme: zero/vazio ambíguos com summary incompleto | Conforme: período desconhecido, zero, sem publicação e publicação anterior explícitos |
| 8. Acessibilidade e responsividade | Parcialmente conforme: tabela equivalente e teclado prévios | Parcialmente conforme: axe, contraste, reflow e tabela por teclado; leitura de SVG/tecnologia assistiva não auditada integralmente |
| 9. Performance | Parcialmente conforme: sem medição de produção | Parcialmente conforme: 402 linhas históricas preservadas, 0 requisições; DOM local medido, sem alegar ganho de velocidade |
| 10. Manutenção e reuso | Parcialmente conforme: renderers separados, composição inadequada | Conforme: mesmas tabelas/formatadores, geometria de lacunas testada, sem biblioteca de gráfico |
| 11. Dados, regras e permissões | Parcialmente conforme: fórmulas corretas, ausência visualmente errada | Conforme: valores/tabelas iguais em cinco snapshots; `None` não vira zero; sem nova agregação |

### Arquivos

| Dimensão | Antes | Depois / prova ou limite |
| --- | --- | --- |
| 1. Objetivo e público | Parcialmente conforme: contexto genérico precedia a consulta | Conforme: publicação e versões como assunto da vista |
| 2. Hierarquia da informação | Parcialmente conforme: identidade diluída pelo cabeçalho de tentativa | Conforme: ID/publicação, tabelas e fontes; tentativa/falha em detalhes próprios |
| 3. Layout, alinhamento e densidade | Parcialmente conforme: painel amplo com contexto duplicado | Conforme: dois registros contíguos, empilhados ≤760 px, sem altura fixa |
| 4. Tipografia, cor e consistência | Parcialmente conforme: identidade técnica com o mesmo peso de contexto | Conforme: rótulo, ID monoespaçado, versões numéricas e cores de superfície distintas |
| 5. Indicadores, gráficos e tabelas | Conforme: versões e caminhos no grão correto | Conforme: conteúdo integral preservado, cabeçalhos e região de rolagem nomeada; gráfico não aplicável |
| 6. Navegação, filtros e ações | Conforme: copiar, fallback e links profundos | Conforme: mesmos IDs/âncoras; nome de botão e status de cópia preservados |
| 7. Estados e atualização | Conforme: identidade ausente indisponível | Conforme: nenhuma publicação não vira ID vazio copiável; data ausente é travessão |
| 8. Acessibilidade e responsividade | Parcialmente conforme: testes funcionais anteriores | Parcialmente conforme: axe e controles >3:1; teclas/cópia/reflow passam; leitor de tela não auditado |
| 9. Performance | Parcialmente conforme: dependência zero, sem benchmark | Parcialmente conforme: sem rede; strings longas não alteram largura da página; custo local registrado |
| 10. Manutenção e reuso | Conforme: helper de campos e fontes | Conforme: helpers preservados, novo agrupamento sem biblioteca, wheel inclui assets iguais |
| 11. Dados, regras e permissões | Conforme: identidades e versões separadas | Conforme: comparação de todos IDs/caminhos/fontes em cinco snapshots; hashes de entradas intactos |

## Comparação visual e crítica das capturas

Os pares usam o mesmo payload, vista por hash e dimensão; sem filtros de dados. A [comparação](evidence/interface-v3/comparison.json) registra 14 pares, incluindo 1024 px, vazio, falha, execução inconclusa e auditoria. Seis imagens anteriores estão no repositório para consulta portátil; o manifesto distingue as origens.

| Vista | Antes | Depois |
| --- | --- | --- |
| Execução 1440 | [Baseline](images/interface-v3/before/blocked-report-qualidade-1440.png) | [Candidato](images/interface-v3/blocked-report-qualidade-1440.png) |
| Execução 390 | [Baseline](images/interface-v3/before/blocked-report-qualidade-390.png) | [Candidato](images/interface-v3/blocked-report-qualidade-390.png) |
| Indicadores 1440 | [Baseline](images/interface-v3/before/blocked-report-indicadores-1440.png) | [Candidato](images/interface-v3/blocked-report-indicadores-1440.png) |
| Indicadores 390 | [Baseline](images/interface-v3/before/blocked-report-indicadores-390.png) | [Candidato](images/interface-v3/blocked-report-indicadores-390.png) |
| Arquivos 1440 | [Baseline](images/interface-v3/before/demo30k-report-proveniencia-1440.png) | [Candidato](images/interface-v3/demo30k-report-proveniencia-1440.png) |
| Arquivos 390 | [Baseline](images/interface-v3/before/demo30k-report-proveniencia-390.png) | [Candidato](images/interface-v3/demo30k-report-proveniencia-390.png) |

A crítica foi além de `scrollWidth`. Em 390 px, a primeira iteração colocava metadados antes da decisão; a ordem foi invertida. Em desktop, o gráfico esticava para acompanhar Produtos; passou a ter altura natural e Loja/dia logo abaixo. Em 320 px, um valor grande cabia na página mas quebrava os dígitos; agora recebe largura inteira. O ponto de um único dia ficava depois da área inicialmente visível; foi movido para o início da área de plotagem. No registro de ocorrência, título, metadado e toggle mantêm colunas próprias e a borda cobre o conteúdo expandido. Arquivos conserva IDs em campos selecionáveis e rolagem local nas tabelas, em vez de quebrar caminhos em colunas ilegíveis.

A rolagem horizontal das tabelas é intencional: mantém comparação entre colunas e cabeçalhos, sem descartar valores. O gráfico longo tem tabela equivalente. Não há animação de números; somente o indicador de navegação usa 180 ms e respeita `prefers-reduced-motion`.

## Verificações executadas

- Ruff e formatação de `src tests scripts`; mypy de `src/retail_pipeline`: aprovados.
- **193 testes unitários**, incluindo **43 do renderer**: aprovados. [JUnit completo](evidence/interface-v3/unit-tests.xml), [renderer](evidence/interface-v3/reporting-tests.xml), [comandos e versões](evidence/interface-v3/checks.json).
- Wheel Python construído sem rede; CSS/JS empacotados iguais aos bytes da fonte. Nenhum serviço ou JVM foi iniciado.
- Edge 153 / Playwright 1.63: 15 combinações principais (três vistas × 1440/1366/768/390/320), 28 capturas da suite e 14 pares adicionais. Hash, histórico, foco, skip-link, cópia/fallback, disclosures, estados e ausência de erro JS aprovados. [Resultado](evidence/interface-v3/visual-review.json).
- Axe 4.13: dez vistas/estados, **zero violações automáticas** nas regras WCAG selecionadas. [Relatório](evidence/interface-v3/accessibility.json). Os resultados `incomplete` restantes são contraste de texto SVG: a inspeção confirmou `#536278` sobre branco, coberto pelo contraste dos tokens; não são transformados automaticamente em “passou”.
- Seis pares de contraste textual amostrados: mínimo **5,675:1**. Bordas dos controles: **3,694:1** sobre branco e **3,288:1** sobre a superfície azul. Estados usam texto além da cor. Teclado foi exercitado nos três painéis, incluindo Enter, foco de destino e histórico.
- Links de navegação, botões e summaries visíveis tiveram altura mínima de 24 CSS px nas 15 combinações principais; os botões/disclosures usam 44 px. Links no texto continuam sujeitos à exceção de alvo inline, sem alegar que todo link tem área de botão.
- Ampliação CSS de 200% e viewport equivalente de 683 CSS px/DPR2; não são zoom nativo do navegador. Leitura a 320 px, strings longas, ausência de overflow da página e mídia de movimento reduzido verificadas.
- Sem JavaScript: todos os painéis, IDs e tabelas equivalentes continuam disponíveis. Impressão: três painéis e conteúdos de disclosures visíveis; o preview não certifica paginação completa de PDF.
- Igualdade de métricas, todas as linhas de tabelas, todos IDs e todas fontes em cinco snapshots históricos; 0 requisições HTTP externas e 0 âncoras internas quebradas na comparação.

O primeiro run unitário encontrou três assertions antigas que esperavam o título de estado em `h1`: 189 passaram. Elas foram atualizadas para o `h2#execution-title`, preservando o texto esperado; logs iniciais foram mantidos. O h1 agora existe em todas as vistas. Isso é manutenção do contrato semântico, não uma prova operacional que falhou.

Rastreabilidade da revisão de código: [report_view.py:114](../src/retail_pipeline/report_view.py#L114) preserva ausência; [:257](../src/retail_pipeline/report_view.py#L257) interrompe lacunas de calendário; [:372](../src/retail_pipeline/report_view.py#L372) torna a cobertura explícita; [:588](../src/retail_pipeline/report_view.py#L588) dá semântica ao grupo de ocorrências; [:932](../src/retail_pipeline/report_view.py#L932) mantém o título global. Em [report.css:15](../src/retail_pipeline/report.css#L15), [:177](../src/retail_pipeline/report.css#L177) e [:268](../src/retail_pipeline/report.css#L268), foco, fronteiras dos controles e movimento reduzido têm regras explícitas. [report.js:6](../src/retail_pipeline/report.js#L6) conserva a navegação/foco existente; não foi reescrito.

## Reprodução e limites

Em ambiente de desenvolvimento com dependências instaladas:

```sh
PYTHONPATH=src python scripts/render_review.py
node scripts/visual-review.cjs
node scripts/a11y-review.cjs
ruff check src tests scripts
ruff format --check src tests scripts
mypy src/retail_pipeline
python -m pytest tests/unit -q
```

Playwright e axe são ferramentas opcionais de desenvolvimento. `PLAYWRIGHT_MODULE` e `AXE_MODULE` podem apontar para instalações existentes, sem adicionar dependências ao relatório. `PLAYWRIGHT_CHANNEL=msedge` seleciona o browser usado nesta revisão. A comparação automática com o baseline exige `REVIEW_BASELINE_DIR`, contendo os HTMLs renderizados pela fonte do commit inicial com os mesmos payloads. Sem essa variável, os demais checks continuam executando.

Não foram reexecutados demo Spark, benchmark ou provas operacionais: o leitor e o domínio não mudaram. A rodada prova apresentação de snapshots já capturados e regressões unitárias. CI remoto, leitor de tela, zoom nativo, paginação integral de PDF, outros motores de navegador e performance de produção não foram verificados nesta rodada. O tempo de navegação `file://` é somente uma amostra diagnóstica local; não se afirma ganho de velocidade com base nele.

O [problema e solução](problem-solution.md), as [decisões técnicas](decisoes-tecnicas.md) e a [verificação histórica](verification.md) continuam sendo as referências de domínio e de execução. Novas evidências da interface não substituem esses registros.

# Verificação e reprodução

## Evolução de perfis e lineage em 12/10/2026

Base desta entrega: `53f998d820d3b5e7a0f2231b370907f7dc77a7bb`, checkout limpo e remoto conferido antes da edição. A branch é `feat/evolucao-varejo-data-pipeline-20261012`. [Isolamento, comandos e saídas](evolution.md). Os registros históricos seguintes permanecem associados às suas próprias execuções.

Em 12/10/2026, a suíte completa passou no container Linux: **369 testes, zero falhas e zero skips**, em 1.536,62 s. A fonte ficou congelada no commit `0ddab5e15f34bd28101a3124a42cc6a5e04ac60f`, com a imagem `sha256:d510a4c939b714b5e3c1bd7199f7d19ad9b0575fe631ce34590c2912675eef87`. O batch usou rede desabilitada, 3 GiB, 2 CPUs e limite de 1.024 processos/threads. Os [inventários antes](evidence/evolucao-20261012-a12e4a/source-before.json) e [depois](evidence/evolucao-20261012-a12e4a/source-after.json) mantiveram os mesmos hashes dos 316 arquivos operacionais; o [diff capturado](evidence/evolucao-20261012-a12e4a/candidate.diff) registra o delta contra a baseline `53f998d`. Os hashes identificam os bytes montados, incluindo eventuais alterações locais fora de HEAD.

| Verificação | Resultado e recibo |
| --- | --- |
| Suíte completa, incluindo Spark/Delta reais | 369 aprovados em 1.536,62 s; [JUnit](evidence/evolucao-20261012-a12e4a/tests-final.xml) e [log](evidence/evolucao-20261012-a12e4a/tests-final.log). |
| Ruff, formato e mypy | Lint aprovado, 62 arquivos formatados e 20 módulos sem erros de tipo; [log](evidence/evolucao-20261012-a12e4a/check-final.log). |
| Smoke Delta e compatibilidade LZ4 | Dois testes aprovados em 29,76 s; [JUnit](evidence/evolucao-20261012-a12e4a/smoke-final.xml) e [log](evidence/evolucao-20261012-a12e4a/smoke-final.log). |
| Scan OS, JVM e Python | Gate aprovado: zero HIGH/CRITICAL e dois MEDIUM, um no sistema e outro na JVM; [scan, identidade e correção](evidence/evolucao-20261012-a12e4a/security-index.json). |

As regressões cobrem contrato e limites de perfil, recálculo do recorte equivalente, UUID, formatos e schemas OpenLineage, retenção e interface. [test_profile_snapshots.py](../tests/integration/test_profile_snapshots.py) confere revisão/CANCEL com um oráculo Decimal independente, truncamento de apresentação e leitura das versões oficiais depois de uma falha entre as Gold. [test_evolution_commit.py](../tests/integration/test_evolution_commit.py) confere WARNING publicável, falha de perfil, reexportação idempotente depois do commit e replay sem novo perfil oficial.

O scan inicial encontrou um HIGH no LZ4 Java 1.11.3. A imagem final usa 1.11.4 e passou pelo mesmo gate, sem ignorar achados. A [prova de API e interoperabilidade](evidence/evolucao-20261012-a12e4a/security-index.json) e o smoke identificam o componente conferido. A primeira coleta dos testes também revelou nomes iguais nos arquivos unitário e de integração; o arquivo de integração foi renomeado para `test_profile_snapshots.py`, conservando as asserções.

Esta suíte completa precede os ajustes de rótulos da interface em `bc6696856f61d66366748becdca2c57c6ac8f9de`. Depois deles, **352 testes unitários passaram em 13,53 s**, com zero skips, e Ruff, formato de 62 arquivos e mypy em 20 módulos passaram novamente. O [JUnit](evidence/evolucao-20261012-a12e4a/unit-labels.xml) e o [log](evidence/evolucao-20261012-a12e4a/unit-labels.log) descrevem essa execução; o [inventário](evidence/evolucao-20261012-a12e4a/source-labels-before.json) e o [diff](evidence/evolucao-20261012-a12e4a/candidate-labels.diff) identificam a fonte. Os rótulos distinguem datas registradas, origem do catálogo e alterações que incluem CANCEL. Cálculos Spark e versões publicadas permanecem os mesmos; as integrações da suíte completa continuam identificadas pela fonte anterior.

Essa rodada unitária usou a imagem `d510a4c9` com os dois arquivos de rótulos modificados no bind, antes de seu commit. Eles foram persistidos sem mudança em `bc66968`; a reconstrução seguinte produziu `8165ad96`, usada pela demo e pela restauração. O inventário pós-commit registra os mesmos bytes, mas sua imagem corresponde à fase seguinte. Não foi salvo um inspect do container unitário removido. [Associação da rodada e limites do registro](evidence/evolucao-20261012-a12e4a/unit-labels-association.json).

### Comparação e reexportação executadas

A demonstração de 12/10/2026 concluiu os três lotes sintéticos com a fonte `bc66968` e a imagem `sha256:8165ad96042fa91bdd62d8477c38ec17984fd136c6d536092aba0ab72335a6e8`. Os 316 arquivos operacionais permaneceram iguais durante a execução. O [índice](evidence/evolucao-20261012-a12e4a/demo-index.json), a [confirmação das fontes](evidence/evolucao-20261012-a12e4a/demo-source-confirmation.json) e o [registro dos lotes](evidence/evolucao-20261012-a12e4a/evolution-demo/execution.json) identificam publicações, baseline, recortes e parâmetros.

| Lote | Resultado publicado e perfil |
| --- | --- |
| `initial` | R$ 64,00; `NO_BASELINE`, quatro linhas, sete unidades e três vendas; [perfil](evidence/evolucao-20261012-a12e4a/evolution-demo/initial-profile.json). |
| `comparable` | R$ 104,00; `COMPARABLE` nas mesmas datas e lojas, com WARNING de preço médio; [perfil](evidence/evolucao-20261012-a12e4a/evolution-demo/comparable-profile.json). |
| `incomparable` | R$ 64,00; `NOT_COMPARABLE`, sem datas comuns à publicação anterior e sem regras calculadas; [perfil](evidence/evolucao-20261012-a12e4a/evolution-demo/incomparable-profile.json). |

O lote `comparable` também injetou falha de exportação depois do commit. Ele permaneceu `PUBLISHED`, com `LINEAGE_EXPORT_FAILURE` como WARNING. A reexportação criou um `COMPLETE` válido no schema fixado; uma segunda chamada conservou os bytes do terminal. O [recibo](evidence/evolucao-20261012-a12e4a/evolution-demo/reexport.json) confirma preservação da publicação, perfil e evidências, e o [evento recuperado](evidence/evolucao-20261012-a12e4a/evolution-demo/reexport-terminal.json) conserva as versões publicadas. As duas chamadas posteriores do comando público `lineage` retornaram zero erros e JSONs idênticos: [primeira](evidence/evolucao-20261012-a12e4a/evolution-demo/cli-lineage-first.json) e [segunda](evidence/evolucao-20261012-a12e4a/evolution-demo/cli-lineage-second.json). O comando `profile` também passou; seu [JSON](evidence/evolucao-20261012-a12e4a/evolution-demo/cli-profile.json) descreve a publicação final.

As etapas de perfil duraram 3,6761 s, 9,8586 s e 6,2000 s nas três fixtures. São observações desta execução, sem medição pareada de overhead. O intervalo de `publication` contém o de `profile`; somá-los contaria esse tempo duas vezes. [Comandos e saídas reproduzíveis](evolution.md).

Os três HTMLs gerados passaram no probe funcional com Edge 155.0.4283.45: 12 combinações de estado/largura, de 1440 a 320 px, com teclado, foco, tabelas, fallback de cópia e leitura sem JavaScript. Não houve erro JavaScript, requisição HTTP externa ou overflow global. O [índice de navegador](evidence/evolucao-20261012-a12e4a/browser-index.json) identifica os recibos de cada estado, e a [qualidade da interface](frontend-quality.md#relatórios-gerados-pela-demonstração) registra as capturas inspecionadas. O escopo é funcional; uma auditoria integral de UX/acessibilidade não foi executada.

### Restauração com perfis referenciados

A prova `pf-varejo-proof-3503857bb22f` passou em 12/10/2026, com a fonte `bc66968` e a imagem `8165ad96042f…`, em 293,535 s no cenário completo. Origem, destino novo e releitura da origem conservaram três publicações com 6.400, 6.400 e 7.700 centavos, as mesmas versões e linhas Delta e perfis `AVAILABLE`. O inventário próprio do runner registrou 322 arquivos: os 316 operacionais e seis metadados ignorados de `src/varejo_data_pipeline.egg-info`, gerados pelo build do pacote. Todos permaneceram iguais durante a prova. A cópia preservou 198 arquivos em um tar de 788.480 bytes. [Resultado público](evidence/evolucao-20261012-a12e4a/restore/result.public.json), [observações no destino](evidence/evolucao-20261012-a12e4a/restore/target-after.json), [manifesto da cópia](evidence/evolucao-20261012-a12e4a/restore/backup-manifest.json) e [índice com hashes](evidence/evolucao-20261012-a12e4a/restore/index.json).

O destino ocupado foi recusado sem alterar os arquivos restaurados; o tar adulterado foi recusado antes de criar a raiz de estado. Os [controles negativos](evidence/evolucao-20261012-a12e4a/restore/occupied-refused.json) e a [recusa da cópia adulterada](evidence/evolucao-20261012-a12e4a/restore/tampered-refused.json) conservam o resultado esperado. A conferência de hashes preservou os bytes da origem, inclusive perfis e eventos. Preparação, instalação e leituras levaram 149,906 s, 1,890 s e 62,578/62,125 s, respectivamente, dentro dos prazos de cada fase. São observações locais; a prova não estabelece RTO de produção.

Os containers próprios foram removidos. Três volumes ficaram preservados: `pf-varejo-proof-3503857bb22f-source`, `pf-varejo-proof-3503857bb22f-target` e `pf-varejo-proof-3503857bb22f-tampered-target`. Havia 23 containers externos em execução nos snapshots anteriores e posteriores, iguais no escopo observado; a carga e o tráfego externos não foram controlados. O recibo público omite nomes e estatísticas desses recursos e registra o hash do original privado. Os arquivos tar permanecem privados. [Procedimento e limites](state-recovery.md).

### Loja nova e imagem final

O teste Spark de inclusão de S04 passou junto do smoke Delta e do teste LZ4: **três aprovados em 79,14 s, zero falhas, erros ou skips**. A fonte é `6c968333f8e54bcb37b7f48c93b94d9b9525c80e`, e a imagem é `sha256:e54034991f90d5fc612bb0ae3b4c9369e439d2fbcc06c0cf96185e370615ccb8`. Os [inventários antes](evidence/evolucao-20261012-a12e4a/source-delivery-before.json) e [depois](evidence/evolucao-20261012-a12e4a/source-delivery-after.json) mantiveram 317 arquivos iguais. Ruff aprovou lint e formato de 63 arquivos, e mypy aprovou 20 módulos. [Resumo dirigido](evidence/evolucao-20261012-a12e4a/delivery-directed-summary.json), [JUnit](evidence/evolucao-20261012-a12e4a/delivery-directed.xml) e [log](evidence/evolucao-20261012-a12e4a/delivery-directed.log).

Na fixture, S04 aumentou o total original de R$ 64,00 para R$ 1.000.064,00. O contexto identificou a loja nova e a comparação conservou o recorte de S01–S03 em 01/01/2026: receita equivalente de R$ 64,00 nas duas versões, regras `STABLE` e nenhum WARNING. O total de uma loja sem baseline não entrou na variação do grupo comparável.

O scan da imagem final também passou, em 17,55 s: zero HIGH/CRITICAL e dois MEDIUM, com inventários de 52 pacotes do sistema, 441 JVM e 37 Python. O [recibo](evidence/evolucao-20261012-a12e4a/security-delivery-summary.json), o [scan integral](evidence/evolucao-20261012-a12e4a/security-delivery-scan.json) e o [gate](evidence/evolucao-20261012-a12e4a/security-delivery-gate.log) identificam esse artefato. Nenhum achado foi ignorado. Esses testes dirigidos e o scan final têm sua própria fonte; a suíte completa de 369 testes continua descrita pelo candidato anterior, sem somar execuções como se fossem uma nova suíte integral. As observações históricas abaixo conservam suas datas e fontes.

## Auditoria do candidato local em 22/09/2026

Base fixada antes das alterações: `main`, `b4d4d7c80d637bf2b67e06ce95b389f6324de4da`, remoto `https://github.com/arthurjoanes/varejo-data-pipeline.git`, consulta às 13h de Brasília. O checkout estava limpo: 589 arquivos rastreados, nenhum novo e 943 ignorados. O SHA permaneceu igual durante a revisão; as correções abaixo foram validadas localmente antes da autorização posterior de commit e push. Não houve deploy. O [CI dessa base](https://github.com/arthurjoanes/varejo-data-pipeline/actions/runs/35744800146) foi conferido por job e passo; a execução da revisão publicada deve ser consultada pelo seu próprio SHA no [workflow](https://github.com/arthurjoanes/varejo-data-pipeline/actions/workflows/ci.yml).

A implementação separa gravação física e publicação, usa contas com `Decimal`, preserva versões e inclui testes que injetam falhas entre tabelas. O requisito justifica Delta e o manifesto; os rebuilds JVM e a recomputação ampliam bastante o custo de manutenção. A alternativa de atualizar componentes oficiais continua preferível quando compatível.

**P2 corrigido — contribuições vazias.** Em `src/retail_pipeline/reporting.py`, `explain_indicator` ainda retornava receita/unidades `null` para uma publicação válida sem itens, embora o relatório já tivesse sido corrigido. A reprodução em `tests/integration/test_boundaries.py` falhou com `None != Decimal("0.00")`. Agora somente a seleção com zero linhas recebe totais aditivos zero. Publicação inexistente continua sendo erro; vendas gratuitas conservam unidades e linhas, e um filtro vazio não comprova cobertura. A regressão cobre vazio, cancelamento total, reativação gratuita e loja sem contribuições, mantendo a identidade da publicação.

| Requisito                                                  | Evidência examinada e situação                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Público, tarefa, problema → exemplo → decisão → limite     | **Conforme.** Leitura simulada somente do README: fechamento de varejo, entradas por origem/loja, cobertura, R$ 64 → R$ 74, falha parcial e retomada são compreensíveis sem reconstruir a narrativa em outros arquivos. A demo R$ 77 é identificada como outro cenário. Não houve estudo com participantes.                                          |
| Referências e autoria concreta                             | **Conforme no escopo documental.** A fonte primária Delta foi lida e ligada ao limite de transação por tabela em [problema e solução](problem-solution.md). Cenário sintético e benefício comercial não são confundidos. O código demonstra o mecanismo, não a motivação histórica do autor.                                                         |
| Dados, contratos, falhas, estados e publicação             | **Conforme após a correção acima.** Suíte real Spark/Delta e regressão dirigida; publicação anterior, zero, ausência, cancelamento e transação parcial permanecem distintos.                                                                                                                                                                         |
| Identidade, hierarquia, gráficos, teclado e responsividade | **Conforme nos percursos executados; parcial para acessibilidade integral.** Replay atual: 15 combinações de vista/largura, 30 capturas, teclado/foco, matriz, leitura sem JS e offline; 14 vistas Axe sem violação automática. Contraste integral, zoom nativo e leitor de tela não verificados. A revisão do README renderizado é descrita abaixo. |
| Código e complexidade proporcionais                        | **Parcial, mantido com justificativa.** Leitura aprofundada de publicação, manifesto, escrita atômica, processamento e relatório; amostra de geradores, operação, testes e build. O custo dos componentes JVM permanece explícito em [runtime](runtime-upgrade.md); não foi feita leitura integral de todos os arquivos ou testes upstream.          |
| Instalação, testes, CI e segurança                         | **Conforme no laboratório descrito abaixo.** Nenhuma chamada paga, ambiente de produção ou credencial pessoal foi usado. Desempenho de produção: **não verificado**. Este registro descreve a validação local anterior à publicação; o CI remoto pertence ao SHA publicado.                                                                          |
| Manutenção, navegação, imagens e resíduos                  | **Conforme no escopo inspecionado.** README encaminha regra/contrato, reprodução, diagnóstico e limites. Foram inventariados 167 PNG, três SVG e uma fonte WOFF; famílias históricas e assets têm consumidores, portanto foram preservados. Não foram encontrados resíduos cuja exclusão estivesse comprovada.                                       |

Validação executada em cópia pública isolada, sem `.env` ou estado anterior: build da imagem com dependências fixadas, **249 testes aprovados, zero skips**, em 919,23 s. Essa suíte completa precede a correção restrita de `explain`. Depois dela, a imagem candidata foi reconstruída; **234 unitários e a integração de fronteiras alterada passaram**, esta em 117,92 s. Ruff, formato de 51 arquivos e mypy em 17 módulos passaram. O teste dirigido usa fonte somente leitura, rede desabilitada e volume novo. Layers JVM de build foram reaproveitados: não é um build frio nem uma nova execução de todas as suítes upstream. Restore e medição históricos abaixo não foram repetidos ou reatribuídos a esta revisão.

**P2 corrigido — sincronização da prova visual.** O replay atual de `scripts/render_review.py`, sem `--capture`, usou cinco payloads históricos e fixtures de apresentação numa cópia publicável isolada. As primeiras tentativas de `visual-review.cjs` falharam ao observar `aria-current` e um disclosure antes de `hashchange` atualizar o DOM. Um probe registrou hash novo, painel anterior e posterior atualização natural, sem erro JavaScript. O script agora aguarda link/painel ou foco antes das asserções e exige cardinalidade nas coleções geométricas e de ocorrências; nenhum timeout foi aumentado nem código da interface alterado. Um controle negativo removeu o listener apenas de um HTML descartável: a prova continuou falhando, código 1, no limite padrão de 30 s.

A execução final passou em Chromium **153.0.8010.12 / Playwright 1.63.0**: **15 combinações** de três vistas em 1440/1366/768/390/320 px e **30 capturas**, sem erro JS ou overflow global. Conferiu R$ 64/57/77 nos estados correspondentes, 360 linhas loja/dia, 30 dias, zero/ausência, matriz e teclado, foco, cópia/fallback, leitura sem JS e fontes offline sem requisições HTTP. Foram inspecionadas quatro capturas: Execução/Indicadores desktop, bloqueio expandido em 320 px e matriz com ausência/zero/negativo em 390 px. `a11y-review.cjs` passou **14 vistas, zero violações automáticas**; itens incompletos `color-contrast` e `aria-prohibited-attr` permanecem sem aprovação manual integral. O menor dos oito pares textuais amostrados foi 5,524:1. `node --check` e diff passaram. Não houve novo lote, benchmark, comparação pareada histórica, zoom nativo ou teste com leitor de tela; as novas saídas ficaram fora do Git em `.audit-runtime/varejo-visual-final-20260922`, preservando payloads, imagens e relatórios históricos do repositório.

Gitleaks 8.30.1 aprovou o histórico e a cópia publicável final. Trivy 0.74.0 sobre a imagem candidata, com a base consultada em 22/09, registrou **zero HIGH/CRITICAL e um MEDIUM**, `CVE-2025-48924` em Commons Lang 2.6, cujo backport e limites permanecem em [runtime](runtime-upgrade.md). O scanner também avisou que Alpine 3.24 não constava em sua lista de EOL. Esses resultados não significam ausência de vulnerabilidades futuras. Uma primeira tentativa de scan por caminho absoluto não aplicou duas exceções exatas já existentes; o scan corrigido usou caminhos relativos, sem ampliar exceções.

O README efetivamente exibido no GitHub foi inspecionado: títulos, parágrafos, tabelas, código, imagens/legendas, links, âncoras e navegação. A 320 px não houve overflow global; tabelas largas rolam localmente. O candidato também participou de 24 prévias locais dos seis READMEs em 1440/320 px e temas claro/escuro, com CSS obtido do GitHub e navegador offline. Prévia não equivale à publicação. O parser GFM verificou destinos locais e âncoras; URLs externas foram consultadas separadamente. O 404 do endereço antigo do jQuery Barcode está em avisos de terceiros, preservados como crédito histórico; bloqueios e indisponibilidade não foram classificados automaticamente como links mortos.

Links relativos e geração de âncoras seguem as orientações oficiais de [README](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) e [sintaxe do GitHub](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax). Um título principal, densidade de imagens e extensão das seções são escolhas editoriais desta revisão, não limites impostos pelo GitHub. A leitura do tema seguiu a orientação de [adequação ao público](https://developers.google.com/tech-writing/one/audience).

Os logs, JUnit e scans desta rodada foram conservados fora do repositório na pasta temporária `portfolio-final-audit-20260922`; a reprodução usa os comandos deste guia e o teste citado. Os registros anteriores abaixo continuam históricos, com seus resultados desfavoráveis e limites.

A demonstração editorial posterior usou a imagem `95abfa120b95…`, construída do código da base `93d80c0` com a exportação de HTML do teste. Seu [scan próprio](evidence/editorial-20260922/security.json), com base de 22/09 às 07:24 UTC, registrou zero HIGH/CRITICAL e um MEDIUM. A imagem `3cc3b95c…` e os resultados JVM abaixo permanecem históricos; não identificam o artefato dessa demonstração.

## Correção posterior da publicação vazia — 22/09/2026

O [CI de `939f2b7`](https://github.com/arthurjoanes/varejo-data-pipeline/actions/runs/35708715138) teve 241 testes aprovados e uma falha. `Spark.sum` devolvia `None` para a publicação confirmada sem linhas, e o relatório exibia ausência em vez de totais aditivos zero. Os scans de imagem desse job não rodaram após a falha. A correção conta linhas e define zero somente quando não há nenhuma; ticket e datas continuam indefinidos sem vendas.

Para conferir a causa, uma cópia isolada de `939f2b7` recebeu somente o leitor corrigido. Os **43 testes de relatório e três integrações de fronteira passaram**, mantendo as assertions HTML originais: vazio e cancelamento total têm receita zero e ticket indefinido; três vendas gratuitas têm ticket zero. A execução usou a imagem 3cc identificada abaixo, sem rede, fonte somente leitura, 3 GiB/2 CPUs/1.024 PIDs. Pytest levou 173,731 s; o ensaio completo, incluindo preparação e limpeza, 176,719 s. [Resultado, identidade e limites](evidence/state-proof-followup/empty-publication.json) · [JUnit](evidence/state-proof-followup/targeted.xml).

Esse teste dirigido usa o renderer anterior. A fonte integrada em `44cd017` inclui a interface nova e testes por métricas nomeadas; sua suíte completa pertence ao CI do respectivo commit. As provas anteriores de restore e medição não foram reexecutadas nem tiveram seus hashes substituídos. [Associação das fontes históricas](state-recovery.md).

## Recuperação e medição local — 22/09/2026

O [índice desta entrega](evidence/state-proof/index.json) separa a restauração, a medição e as tentativas de regressão. A [história operacional](state-recovery.md) explica o problema, as escolhas, as capturas e os limites.

- Restauração: 187 arquivos, três publicações com versões/linhas/totais iguais, origem preservada e duas recusas reais. Cenário completo de 251,851 s, não RTO comercial.
- Medição: seis amostras aprovadas pelo oráculo CSV/Decimal, sem censura. Medianas de processamento de 37,045 e 38,180 s para históricos de 3.600 e 10.800 linhas, ambos com 360 novas. Startup medido separadamente; carga externa apareceu durante a janela e impede atribuir causalidade ao tamanho.
- Regressão dirigida: 183 testes em seis arquivos, incluindo o limite de publicação Spark/Delta; não é toda a suíte. A primeira imagem histórica e a tentativa atual com 512 PIDs falharam; o limite de 1.024 foi fixado antes dos ensaios seguintes.
- Ruff 0.6.9, versão do lock, aprovou lint e formato de 50 arquivos. Seis capturas dos relatórios reais foram conferidas em desktop/celular. Fonte e imagem são identificadas por execução; o scan existente da imagem 3cc permanece separado de um novo scan.

Containers próprios removidos, volumes preservados. Recuperação externa, retenção destrutiva, desempenho de produção e estudo com usuários não foram executados.

Arquivos em artifacts são gerados localmente e não são pré-requisitos do clone. O comando `scripts/verify_problem.py` grava os resultados em `artifacts/`; passos em [demo.md](demo.md).

## Reconstruções JVM históricas em 22/09/2026 (UTC)

Spark core, Hadoop runtime e Commons Lang têm builds identificados, com fontes e ferramentas fixadas, proveniência e hashes. O scan da imagem combinada registra **zero HIGH/CRITICAL e um MEDIUM**, mantido por versão no Commons Lang com backport. [Decisões, receitas e limites](runtime-upgrade.md) · [tratamento individual dos 18 achados anteriores](evidence/security-triage.json).

| Verificação                                    | Resultado                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Suíte completa antes de incorporar a interface | 188 aprovados: 173 unitários e 15 integrações; zero falhas/erros/pulados, 1.003,963 s. A fonte permaneceu inalterada. [JUnit](evidence/jvm-rebuild-tests.xml) · [resultado e hashes](evidence/jvm-rebuild-full-suite.json).                                                                                                                                                                                                                                    |
| Fonte combinada com a interface publicada      | Incorporado o commit `899c9f3`. Os 182 unitários passaram; Ruff, formato de 46 arquivos Python e mypy nos 16 módulos passaram. [JUnit](evidence/jvm-rebuild-post-interface-unit.xml).                                                                                                                                                                                                                                                                          |
| Demo na fonte combinada                        | Oito passos e totais 64 → 64 → 64 → 64 → 77 → 57 → 57 → 77 aprovados, incluindo bloqueio, falha intencional e recuperação, em 151,742 s. [Resultado](evidence/jvm-rebuild-demo.json).                                                                                                                                                                                                                                                                          |
| Migração da imagem anterior para os rebuilds   | A imagem `91f08a83dbb7…` criou R$ 64,00 em volume novo. A imagem `3cc3b95c1985…`, já com a fonte da interface incorporada, leu esse estado, respondeu `NO_CHANGE` ao reenvio e publicou R$ 77,00. A versão anterior continuou em R$ 64,00 e o HTML foi gerado. Ambas usam Spark 4.2.0/Delta 4.4.0; esta prova verifica a troca dos componentes JVM. [Seed](evidence/jvm-rebuild-migration-seed.json) · [retomada](evidence/jvm-rebuild-migration-resume.json). |
| Scan integral                                  | 52 pacotes Alpine e 28 Python sem achados; 441 pacotes JVM, com CVE-2025-48924/MEDIUM. Sem exclusões de achados ou filtros de severidade; o gate reprova qualquer HIGH/CRITICAL. [Relatório bruto](evidence/security-scan.json).                                                                                                                                                                                                                               |

O runtime verificado **nessa rodada histórica** foi a imagem `sha256:3cc3b95c1985397f1a3601a1c66531180ba0b8ef8738e5901dd400e805c719f3`; os testes usam a fonte do checkout montada somente leitura, rede desabilitada, 2 CPUs e 3 GiB. A suíte de 188 precedeu a interface incorporada posteriormente: os testes unitários, a demo e a migração da fonte combinada são registrados separadamente, sem somar execuções como casos distintos. O CI repetirá a suíte integral no commit publicado. [Registro consolidado](evidence/jvm-rebuild.json) · [fontes e materiais da suíte inicial](evidence/jvm-rebuild-source-before-interface.json) · [fontes depois da interface](evidence/jvm-rebuild-source-after-interface.json).

Os testes de componentes não equivalem a executar todas as suítes upstream. Em especial, os 44 casos de `ClassUtils` passaram, mas a suíte histórica completa de Commons Lang mantém 29 problemas de compatibilidade/expectativas no Java 17. A matriz distingue regressões com controle negativo, verificações de compatibilidade, atualização de versão e remoção integral. As receitas reproduziram os hashes dos três JARs; não há promessa de imagem inteira idêntica byte a byte.

## Revisão de explicações e jornadas — 22/09/2026

README, problema/solução e decisões técnicas foram conferidos contra as funções e testes citados. Os exemplos distinguem a demo que termina em R$ 77,00 do teste de negócio que termina em R$ 74,00. As contas, entradas e limites são os desses cenários existentes; nenhuma nova execução Spark é atribuída a esta revisão.

O Edge percorreu bloqueio, falha e retomada em três larguras, comparando receita, linhas por loja, IDs, versões e caminhos com os payloads. Foram 13 registros de verificação de jornada/estado, com três novas capturas, teclado/foco/histórico, rolagem interna, sem JavaScript e visibilidade dos painéis na impressão. [Registro e hashes dos inputs/capturas](evidence/interface-journeys/review.json), [roteiro e imagens](interface.md#revisão-anterior-de-jornadas-em-2209). Não foi encontrada regressão funcional nesse escopo; fontes da aplicação e interface não precisaram mudar. A ampliação foi CSS de 200% e reflow a 640 CSS px, sem zoom nativo nem leitor de tela. As provas de runtime abaixo permanecem históricas.

## Interface do fechamento em 22/09/2026 (UTC)

A interface separa Execução, Indicadores e Arquivos. A publicação vigente continua visível ao consultar uma tentativa bloqueada ou com falha. Etapas mostram somente medições existentes; contadores indisponíveis não viram zero. O código de captura e replay permite repetir esta revisão sem executar novos lotes. [Comportamento e reprodução](interface.md).

| Verificação                     | Resultado                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unitários na fonte da interface | 160 aprovados, zero falhas/pulados. [JUnit](evidence/interface/unit.xml).                                                                                                                                                                                                                                                                                                                    |
| Ruff, formato e mypy            | Aprovados; 37 arquivos Python formatados e 16 módulos de aplicação verificados.                                                                                                                                                                                                                                                                                                              |
| Dados das capturas              | Cinco payloads relidos com Spark 4.2.0, por versão Delta, de um volume histórico somente leitura. Demo pequena: R$ 64,00 no bloqueio, R$ 57,00 na falha e R$ 77,00 após recuperação. Volume: R$ 1.141.858,51, 10.008 vendas e 89.903 unidades. Nenhum lote ou benchmark reexecutado. [Payloads e proveniência](evidence/interface/payloads).                                                 |
| Edge / Playwright               | 14 capturas; três vistas em 1440, 1366, 768, 390 e 320 CSS px sem rolagem horizontal da página. Gráfico com 30 valores diários equivalentes e 360 linhas loja/dia conservadas. [Registro](evidence/interface/visual-review.json).                                                                                                                                                            |
| Navegação e estados             | Teclado, foco, histórico, âncoras de IDs, detalhes nativos, cópia exata e fallback, leitura sem JavaScript, bloqueio/falha com publicação anterior, vazio, execução sem resultado final e auditoria incompleta. O link de salto conserva Indicadores/Arquivos, foca o conteúdo e mantém essa vista ao voltar/avançar. Estados artificiais são identificados em [interface.md](interface.md). |
| Ampliação e conteúdo longo      | Três vistas com ampliação CSS de 200% e com viewport equivalente de 683 CSS px / DPR 2; IDs, código de ocorrência e texto longo a 320 px. Não houve teste de zoom nativo do navegador nem auditoria com leitor de tela.                                                                                                                                                                      |

As capturas usam publicações da demonstração histórica de 21/09, originalmente processadas em Spark 3.5.9/Delta 3.2.1. O runtime atual apenas releu suas versões. Nos estados intermediários de bloqueio/falha, a apresentação foi reconstituída a partir do manifesto imutável e da tentativa registrada, sem modificar o ponteiro no volume. Os payloads registram o hash da evidência de origem e o modo de seleção. Testes de captura não substituem a suíte de integração do runtime descrita abaixo.

Os [hashes da fonte verificada](evidence/interface/source.json) identificam os arquivos desta revisão histórica. A pasta [images/interface](images/interface) conserva as três capturas de jornadas vinculadas por hash. Os exports antigos sem referências foram arquivados fora do repositório; a [conferência posterior](image-review.md) registra a classificação e a apresentação atual.

## Revisão anterior de segurança em 22/09/2026 (UTC)

Spark 4.2.0/Delta 4.4.0, com 45 JARs substituídos integralmente, 22 componentes opcionais removidos e limites de entrada. [Registro consolidado](evidence/remediation.json).

| Verificação                          | Resultado                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Suíte completa do runtime atualizado | 166 aprovados, zero falhas/pulados, em 1.350,58 s: 151 unitários e 15 integrações. [JUnit](evidence/remediation-tests.xml).                                                                                                                                                                                                                                                                                                                                                                         |
| Ajuste posterior da evidência        | Depois da suíte completa, a gravação de `operator-references.json` foi antecipada para também preservar a referência aprovada quando a cópia ultrapassa o orçamento. Foram repetidos os [151 unitários](evidence/remediation-final-unit.xml) e [uma integração real](evidence/remediation-final-focused.xml), todos aprovados. Essa integração verifica a referência preservada, o bloqueio por bytes e a publicação anterior intacta. A suíte integral não foi repetida após esse ajuste restrito. |
| Ruff, formato e mypy na fonte final  | Aprovados; 36 arquivos Python e 16 módulos de aplicação.                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Demo CLI do runtime atualizado       | Oito passos aprovados, receitas 64 → 64 → 64 → 64 → 77 → 57 → 57 → 77, incluindo falha/retomada. [Resultado](evidence/remediation-demo.json).                                                                                                                                                                                                                                                                                                                                                       |
| Migração da fixture anterior         | Spark 3.5.9 publicou R$ 64,00; Spark 4.2.0 releu, reconheceu reenvio sem mudança e corrigiu para R$ 77,00, com leitura da versão anterior preservada. [Resultado](evidence/runtime-migration.json).                                                                                                                                                                                                                                                                                                 |
| Volume demonstrativo                 | 30 mil linhas, mesmos totais esperados: R$ 1.141.858,51, 10.008 vendas, 89.903 unidades, 12 lojas/30 dias. Pipeline em 83,65 s e pico de 1.358.082.048 bytes. Houve concorrência com testes isolados: é validação funcional, não comparação controlada de desempenho. [Medição](evidence/remediation-benchmark.json).                                                                                                                                                                               |
| Scan da imagem final                 | OS/Python sem achados; JVM com 18 residuais não corrigidos, 7 HIGH e 11 MEDIUM, zero CRITICAL. Sem exclusões no scanner. [Scan e triagem](security.md).                                                                                                                                                                                                                                                                                                                                             |

A suíte completa, a demo e o benchmark usaram a imagem `bfef20f37677…`; o ajuste posterior foi incorporado à imagem final `91f08a83dbb7…`, novamente inventariada e escaneada. As identidades completas e os SHA-256 do código estão nos registros de [fonte da suíte completa](evidence/remediation-full-suite-source.json) e [fonte final](evidence/remediation-source.json). Os 16 módulos da fonte final correspondem byte a byte aos arquivos da imagem final. Os testes usaram o código/testes do bind do checkout; a integração manteve esse bind somente leitura, rede desabilitada e os limites do Compose. [Isolamento observado na suíte](evidence/remediation-full-suite-isolation.json).

Os registros distinguem SHA-256 dos arquivos locais e OIDs dos blobs Git após normalização por `.gitattributes`. Parte do checkout Windows tinha CRLF; o conteúdo publicado usa LF. Portanto, o hash local não é apresentado como hash dos bytes do clone público. Esta revisão do runtime não refez capturas; a revisão posterior da interface está descrita acima.

## Evidência histórica de publicação em 21/09/2026

Esta execução usou Spark 3.5.9/Delta 3.2.1. Uma cópia contendo somente arquivos públicos candidatos foi construída e executada em Docker Linux, sem `.env`, caches ou dados da instalação anterior. [Registro da execução](evidence/publication.json).

| Verificação               | Resultado                                                                                                                                                             |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Suíte completa            | 156 aprovados, zero falhas e zero pulados; 15 integrações, sendo 14 com Spark/Delta e uma de lock entre processos. [JUnit](evidence/publication-tests.xml).           |
| Ruff, formato e mypy      | Aprovados; 32 arquivos Python formatados e 15 módulos verificados por tipos.                                                                                          |
| Demo CLI                  | Oito passos e totais manuais conferidos; publicação final R$ 77,00, preservação durante bloqueio/falha e retomada sem duplicação.                                     |
| Volume demonstrativo      | 30 mil registros, 12 lojas e 30 dias; pipeline em 69,45 s, 76,96 s incluindo geração e relatório, pico do container de 984,2 MiB. [Medição](evidence/benchmark.json). |
| Relatório                 | Dez capturas em cinco larguras; teclado, cópia, fallback sem JavaScript e servidor HTTP local aprovados. Dados sintéticos identificados no HTML.                      |
| Publicação e dependências | Actionlint e Gitleaks aprovados; scan integral e triagem JVM em [segurança](security.md).                                                                             |

As medições são desta execução, com limite de 3 GiB/2 CPUs; não são uma previsão de desempenho para outros computadores ou produção. O CI repete a suíte, o scanner e os verificadores no commit publicado.

## Runtime

| Componente         | Versão fixada                            |
| ------------------ | ---------------------------------------- |
| Python             | 3.11.16                                  |
| Java               | OpenJDK 17.0.20+8 (Alpine 17.0.20_p8-r0) |
| PySpark / Spark    | 4.2.0                                    |
| Delta Lake / Scala | 4.4.0 / 2.13                             |
| pytest             | 9.0.3                                    |

As [notas Delta 4.4.0](https://github.com/delta-io/delta/releases/tag/v4.4.0) confirmam suporte ao Spark 4.2.0; o JAR específico é `delta-spark_4.2_2.13`. Os digests estão no Dockerfile; dependências Python têm hashes nos locks; os JARs Delta são conferidos por SHA-256 em `scripts/download_jars.py`. O build instala ferramentas de construção antes dos pacotes, sem resolução isolada implícita. O [lock JVM](../runtime-jars.lock.json) registra substituições completas e componentes opcionais removidos; [motivos e pendências](runtime-upgrade.md).

Base e dependências fixadas não significam imagem reproduzível byte a byte: apk instala as dependências do runtime a partir dos repositórios Alpine durante o build. A consulta OSV de 16 pins Python está em [dependencies.json](evidence/dependencies.json). A varredura atual inclui sistema operacional, Python e bibliotecas JVM: [resultado e triagem](security.md).

## Comandos verificáveis

Na raiz do clone, sem instalação de Python ou Java no Windows:

```powershell
.\scripts\pipeline.ps1 setup
.\scripts\pipeline.ps1 check
.\scripts\pipeline.ps1 test -q --junitxml=/app/artifacts/tests.xml
.\scripts\pipeline.ps1 demo
docker compose run --rm --entrypoint python pipeline scripts/benchmark.py
.\scripts\pipeline.ps1 serve
```

No Linux, substitua o wrapper por sh scripts/pipeline.sh. Setup baixa as dependências; os demais comandos do batch usam network_mode:none. Relatórios abrem diretamente como HTML ou no servidor opcional de 127.0.0.1:3103. O serviço não entrega o volume Delta pela rede.

O Compose limita o batch a 3 GiB e 2 CPUs, Spark local[2], driver 1 GiB, duas partições de shuffle/snapshot. Testes e demos executam um runtime Spark por vez. Dados, cache, temporários e logs ficam no volume Linux; o bind do código e as exportações pequenas ficam no diretório do clone. O workflow usa o mesmo runtime e permissões contents:read.

## O que os testes verificam

- Totais manuais independentes por loja e produto: R$ 44,00 + R$ 20,00 = R$ 64,00; sete unidades, quatro linhas e três vendas.
- Revisão crescente, revisão antiga, duplicata dentro/entre arquivos, conflitos com histórico elegível, mudança de dia, cancelamento e reativação.
- CSV/JSON estritos, schema, hashes, contagem, referências, zero explícito, loja ausente, multiviolação e preservação física da entrada.
- Mesmo batch não pode mudar manifesto, catálogo ou calendário; reposição dos bytes esperados continua possível.
- Falhas após ingestão, gold e antes do ponteiro; candidato não se torna autoridade; leitura antiga permanece estável.
- Lock entre processos e liberação após término; falha de auditoria depois do commit não desfaz publicação visível.
- Argumentos inválidos e saída de geração ocupada recusados antes do Spark; dados extremos de contrato e formato sem exceções de conversão.
- Publicação sem vendas com ticket indisponível; venda gratuita com ticket zero; mesmo sale_id em origens distintas; datas históricas e limite monetário gravados em Delta.
- HTML sem execução de conteúdo de origem; ausência de publicação distinta de zero; indicadores associados a versões fixadas; gráfico com tabela equivalente.
- Aliases de caminho com .. não permitem copiar a entrada recursivamente para dentro dela mesma.

## Verificação visual opcional

O HTML não depende de Node. Para repetir apenas as capturas, instale Playwright em um diretório de ferramentas ignorado:

```powershell
npm install --prefix .visual-tools --no-save --package-lock=false playwright@1.63.0
.\.visual-tools\node_modules\.bin\playwright.cmd install chromium
$env:NODE_PATH = (Join-Path (Get-Location) '.visual-tools/node_modules')
```

Antes do script de navegador, gere os HTMLs por replay dos payloads versionados:

```powershell
docker compose run --rm --entrypoint python pipeline scripts/render_review.py
node scripts/visual-review.cjs
```

Não é necessário repetir a demo nem o benchmark. O script verifica três vistas em 1440, 1366, 768, 390 e 320 CSS px, foco e histórico de âncoras, expansão por teclado, 30 totais diários equivalentes ao gráfico e 360 linhas loja/dia em detalhe. A cópia é testada com Clipboard API interceptada e fallback indisponível, sem escrever no clipboard real. Uma sessão sem JavaScript verifica leitura e expansão nativa. Novas capturas ficam em `artifacts/interface-review/images` e as medições em `artifacts/interface-review/evidence`; as pastas `docs/evidence/interface*` conservam registros históricos e payloads de origem. [Saídas externas e conferência atual](image-review.md). O registro distingue ampliação CSS, viewport equivalente e as limitações de acessibilidade.

## Limites

Não há VACUUM automático nem backup agendado ou externo. A [prova posterior de recuperação](state-recovery.md) acrescentou cópia local, restauração e contrato conservador de retenção, sem remover dados antigos. Fabric ainda não foi executado. Duração e memória estão registradas por execução.

## Refinamento da interface — 22/09/2026

Esta rodada altera apresentação e seleção de texto do relatório, sem alterar processamento, publicação ou contratos. Os payloads da demonstração histórica foram renderizados offline; não houve nova execução Spark, benchmark ou build.

- **38 testes do relatório aprovados**, incluindo escape, valores, estados sem conclusão, auditoria incompleta e agrupamento de arquivo/loja sem perder ocorrências por ordem ou limite. [JUnit](evidence/interface-v2/reporting-tests.xml). Ruff e mypy da fonte de apresentação aprovados.
- **20 capturas** com Edge: três vistas em cinco larguras (1440, 1366, 768, 390 e 320 px), bloqueio expandido em quatro larguras e estados de publicação, falha, qualidade, ausência, execução sem conclusão e auditoria incompleta. [Registro](evidence/interface-v2/visual-review.json).
- Teclado, foco, histórico, link de salto, IDs/copiar/fallback, equivalência gráfico/tabela, conteúdo longo, alinhamento dos painéis, coluna de expansão, borda da ocorrência aberta, contadores e redução de movimento verificados. Impressão expõe painéis e detalhes; sem JavaScript, os detalhes nativos continuam acessíveis.

A ampliação foi feita por CSS a 200% e viewport equivalente de 683 CSS px/DPR 2; não é uma prova de zoom nativo. As amostras de contraste atendem 4,5:1, sem equivaler a auditoria completa de acessibilidade. Não houve leitor de tela nem revisão de paginação integral de PDF. [Escopo e hashes da fonte](evidence/interface-v2/review-manifest.json). As contagens e provas de runtime anteriores descrevem suas próprias revisões.

## Demonstração editorial — 22/09/2026

A [rodada editorial](demo.md#demonstração-editorial-executada) acrescenta evidência nova sem substituir os testes ou medições históricos: build do Dockerfile atual, smoke (**1 teste**) e tese de negócio (**1 teste**, com oito tentativas e leituras reais Delta). Ambos passaram. O aviso de cache do pytest ocorreu porque `/app` estava somente leitura; não houve teste ignorado por isso.

A exportação opcional de seis HTMLs no teste é a única alteração de código desta rodada. Não muda asserções, publicação nem cálculos. A base é `93d80c0` mais essa alteração; o [manifesto](evidence/editorial-20260922/verification.json) registra os hashes da fonte executada. Build com cache não equivale a build frio nem reprodução binária. O primeiro build sem rede falhou por falta de índice apk, e o build documentado com rede passou.

Cinco capturas explicam cobertura, revisão parcial/integral, falha e replay. São imagens de uma execução funcional com dados sintéticos, não provas isoladas da consistência interna. O [JSON de negócio](evidence/editorial-20260922/business-thesis.json) e os dois JUnit sustentam os valores. Não repeti a suíte de 249 testes nem o scan de imagem do [CI da base](https://github.com/arthurjoanes/varejo-data-pipeline/actions/runs/35722366378), aprovado antes desta edição documental. A revisão editorial e seus limites estão no [registro próprio](evidence/editorial-20260922/execution.json).

### Scan da imagem da demonstração editorial

O [scan novo](evidence/editorial-20260922/security.json) examinou o ID da imagem usada nesta demonstração, com Trivy 0.74.0 e base de 22/09/2026 às 07:24 UTC. Incluiu pacotes do sistema, Python e Java, todas as severidades e achados sem correção, sem nova exceção: HIGH/CRITICAL ficaram em zero. Há um MEDIUM em `commons-lang:commons-lang` 2.6 (CVE-2025-48924), sem versão corrigida informada nesse relatório; ele permanece visível. Não substituí JARs nesta revisão editorial nem tratei esse resultado como ausência de qualquer vulnerabilidade. O relatório identifica o artefato atual, separado do scan histórico do CI.

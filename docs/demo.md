# Demo

## Comparar perfis e recuperar exportação

O [roteiro de evolução](evolution.md) usa estado, imagem, volume e exportações exclusivos. A fixture começa em R$ 64,00; a revisão de preço mantém datas e lojas e permite comparação equivalente. Mover integralmente as vendas para outro dia elimina a interseção e produz `NOT_COMPARABLE`. Esses são resultados esperados pelo [executor com asserts](../scripts/prove_evolution.py); a execução e seus arquivos possuem registro próprio, separado das demos históricas abaixo.

O mesmo executor injeta falha na exportação terminal depois da publicação, verifica `PUBLISHED`, reexporta um COMPLETE e confere preservação de bytes e idempotência. `profile` consulta o JSON do snapshot, e `lineage` permite repetir explicitamente a reconciliação. [Mapeamento OpenLineage](openlineage.md).

## Consultar o fechamento no dashboard

A demo de evolução de 12/10/2026 contém publicações de R$ 64,00, R$ 104,00 e R$ 64,00, com dados sintéticos. O HTML captura o estado da publicação e permanece estático ao ser aberto.

1. Em Visão geral, confira período, identidade e totais. Leia a receita diária, o ranking de até seis lojas e o mix de até cinco produtos, com os demais agrupados quando houver excedentes. Os percentuais das lojas usam todas as lojas com receita completa do recorte.
2. Em Lojas, percorra a matriz por dia e abra a tabela para conferir valores exatos. Zero registrado e ausência de observação têm representações próprias.
3. Em O que mudou, veja anterior e atual nas mesmas datas e lojas. A publicação inicial não tem baseline. A publicação de 10/01 não tem datas em comum com 01/01 e informa que o recorte não é comparável. Períodos, IDs e razões ficam nos detalhes.
4. O relatório bloqueado abre em Qualidade. S02 está ausente; Visão geral conserva os R$ 64,00 da publicação anterior. Abra a ocorrência e a cobertura para investigar a entrega.
5. Em Arquivos, selecione ou copie IDs completos e confira fontes e versões Delta. As ações da página consultam o snapshot; não publicam ou reprocessam a entrega.

O [guia da interface](interface.md) descreve os gráficos e a reprodução offline das fixtures em `tests/fixtures/reports/`. Os relatórios de domínio históricos mantêm seus horários originais.

## Testar o problema e a correção

Após o setup, execute em uma janela sem outro Spark:

```powershell
docker compose run --rm --entrypoint python pipeline scripts/verify_problem.py --thesis-only --output /app/artifacts/thesis
```

O comando cria estado temporário novo, testa Spark/Delta real e gera `artifacts/thesis/business-thesis.json`, seis HTMLs dos estados, `tests.xml` e `verification.json` com fingerprints. Não altera a demo anterior. Para conferir tudo, omita `--thesis-only`.

1. A fixture inicial publica R$64,00 e três vendas.
2. Um novo lote remove S02 da entrega e do próprio calendário: o calendário do operador mantém três lojas esperadas, portanto a publicação é bloqueada.
3. Uma revisão99 move só um item de A1 para outro dia. Agrupar a entrada diretamente continua somando R$64,00, mas conta quatro vendas. O pipeline bloqueia `SALE_DATE_CONFLICT`, também em `validate`.
4. Uma revisão2 corrige os dois itens de A1; é aceita porque a revisão99 rejeitada não é histórica. Gold mostra S01/01jan=R$20,00, S02/01jan=R$20,00, S01/02jan=R$24,00; uma venda em cada linha.
5. Nova correção falha após o primeiro Gold. A leitura oficial e o snapshot capturado continuam iguais. Retry publica R$74,00, três vendas; replay é NO_CHANGE. O snapshot inicial ainda retorna R$64,00.

O relatório final desse teste é pequeno e permite conferir cada valor mentalmente. Ele verifica correção e recuperação, não desempenho. O teste multiprocesso adicional da suíte completa disputa a entrada `process_batch` enquanto outro processo mantém o lock; a tentativa concorrente é recusada antes de criar uma execução, e o kernel libera o lock ao terminar o detentor.

## Jornada operacional

Depois do setup, execute `scripts/pipeline.ps1 demo` (ou `sh scripts/pipeline.sh demo`). O comando cria uma pasta UUID em `/data/demos/` dentro do volume; preserva demos anteriores e não pede reset. Não usa rede. O caminho efetivo fica em `artifacts/demo-evidence.json` e `/data/last-demo.json`.

| Passo | Ação executada                                         | Resultado que deve aparecer                                            |
| ----- | ------------------------------------------------------ | ---------------------------------------------------------------------- |
| 1     | Gerar/publicar fixture manual                          | 4 linhas, 7 unidades, 3 vendas, R$ 64,00; S03 confirma zero            |
| 2     | Explicar S01/01-01-2026                                | R$ 44,00; arquivos/linhas/chaves e versões em `artifacts/explain.json` |
| 3     | Reexecutar exatamente o mesmo lote                     | NO_CHANGE, mesma publicação, R$ 64,00                                  |
| 4     | Remover S02 da entrega já contratada                   | BLOCKED, loja ausente, publicação anterior R$ 64,00                    |
| 5     | Repor os bytes originais sem mudar manifesto           | PUBLISHED, R$ 64,00; duplicatas sem efeito                             |
| 6     | Revisar primeira linha e cancelar S02 posteriormente   | Receita passa a R$ 77,00 e depois R$ 57,00                             |
| 7     | Tentar reativação e falhar antes da troca de manifesto | TECHNICAL_FAILURE; candidato gravado, relatório oficial ainda R$ 57,00 |
| 8     | Reexecutar a tentativa interrompida                    | Publicação consistente com R$ 77,00, sem dupla receita                 |

A demo contém asserts dos estados e valores. Antes da jornada principal, gera também quality-review.html em estado isolado: cinco registros recebidos, um rejeitado com quatro violações e nenhuma publicação. Duração e identificadores de uma execução dessa jornada estão em docs/evidence/round-2/demo.json.

A jornada aprova as referências sintéticas separadamente antes de criar entregas. Para comandos individuais, execute `configure --catalog /app/data/operator/fixture/catalog.json --schedule /app/data/operator/fixture/schedule.json` uma vez. Sem configuração o processamento bloqueia. Mudanças no calendário aprovado exigem um novo `--data-dir` e reprocessamento; isso evita reinterpretar silenciosamente a história.

## Ver resultados

1. Abra `artifacts/report.html`: em Qualidade, confira a última tentativa; em Visão geral, confira a receita final de R$ 77,00. Arquivos identifica a publicação e suas versões.
2. Abra `artifacts/blocked-report.html`: a publicação válida aparece junto do bloqueio por loja ausente. Abra a ocorrência em Qualidade e consulte Visão geral para conferir os R$ 64,00 preservados.
3. Abra `artifacts/failure-report.html`: o candidato da reativação não aparece no total oficial. Visão geral mantém R$ 57,00 da publicação anterior.
4. Abra `artifacts/explain.json`: amostra rotulada liga o indicador à origem. O documento se refere à primeira publicação; não se confunde com a versão final da demo.
5. Veja `tests/integration/test_pipeline.py`: correção de data, revisão antiga, conflito, lote rejeitado, concorrência real e leitura por versão também são exercitados.

O servidor opcional abre com `scripts/pipeline.ps1 serve`; consulte http://localhost:3103/report.html. Ele entrega os HTMLs diretamente em `artifacts`, sem listar a pasta ou expor os JSONs. Os três HTML também abrem diretamente como arquivo. `scripts/pipeline.ps1 stop` encerra o servidor sem remover dados.

## Inspecionar uma demo específica

Copie `data_dir` de `artifacts/demo-evidence.json` e substitua `<diretorio>` abaixo; é um caminho Linux no volume:

```powershell
docker compose run --rm pipeline --data-dir <diretorio> explain --store-id S01 --business-date 2026-01-01
docker compose run --rm pipeline --data-dir <diretorio> report --output /app/artifacts/inspected-report.html
```

Leitores carregam o manifesto uma única vez e usam `versionAsOf` em todas as tabelas. Não use leitura Delta latest para conferir a publicação oficial: latest pode ser um candidato interrompido.

## Cenário de 30 mil linhas

O roteiro manual usa poucas linhas para permitir cálculo mental. O experimento maior é independente:

```powershell
docker compose run --rm --entrypoint python pipeline scripts/benchmark.py
```

Gera 30 mil registros, 12 lojas e 30 dias com seed 42 em estado isolado; valida, publica, mede a memória máxima do container e produz `artifacts/benchmark.json` e `artifacts/demo30k-report.html`. Não aumenta escala automaticamente. Limites do container em [verification.md](verification.md).

## Diagnosticar e retomar

Para acompanhar uma cópia e restauração já executadas, leia a [sequência de recuperação](state-recovery.md). Ela usa quatro estados de uma fixture pequena e conserva os relatórios reais: publicação, bloqueio, reposição e correção. Os comandos de reprodução criam volumes novos; não operam sobre o estado persistente desta demo.

- Exit 2: se a CLI informar argumento inválido, corrija o uso antes de executar; para lote bloqueado, examine códigos de qualidade e arquivos em quarentena. Reponha arquivo faltante/corrompido de acordo com o manifesto original. Se mudar conteúdo esperado, use novo batch_id e correction_of.
- Exit 3: confira logs estruturados e `runs/<run_id>/attempt.json`; reexecute a mesma entrada após corrigir a causa. O manifesto continua sendo a autoridade sobre visibilidade.
- Injeção manual: `run <entrada> --demo-mode --fail-at before_publish` (alternativas: `after_ingestion` e `after_gold`). Sem `--demo-mode`, a CLI recusa a simulação.
- Não há reset destrutivo automático. Não execute VACUUM em tabelas que tenham versões referenciadas pelos manifestos.

## Execução de domínio em 22/09/2026

Em 22/09/2026, a tese pequena rodou em estado novo, com Spark 4.2.0 e Delta 4.4.0 reais. A fonte usou a base `93d80c0` com a exportação opcional de HTML em `test_business_thesis.py`; as regras de domínio permaneceram iguais. O [registro da execução](evidence/editorial-20260922/execution.json) contém comandos, limites e hashes; [verification.json](evidence/editorial-20260922/verification.json) identifica as fontes presentes na imagem.

O build normal passou usando cache local. Uma tentativa anterior de build com rede desativada falhou ao consultar o índice Alpine: o primeiro setup não é prometido como offline. O batch posterior rodou com `--network none`, raiz somente leitura, 3 GiB e duas CPUs, em um volume próprio. Smoke e teste de negócio passaram: [smoke.xml](evidence/editorial-20260922/smoke.xml) e [tests.xml](evidence/editorial-20260922/tests.xml). Essa rodada histórica não incluiu benchmark de 30 mil linhas ou recuperação de volume.

| Caso real, com fixture sintética | Saída observada | Chave na prova de domínio |
| -------------------------------- | --------------- | ------------------------- |
| S02 retirada da entrada e do calendário do remetente | `BLOCKED`; expectativa independente ainda exige S02 | `steps` |
| Só um item de A1 muda de dia | `SALE_DATE_CONFLICT`; soma ingênua 64, contagem ingênua 4 em vez de 3 | `baseline_partial_date` |
| Ambos os itens mudam de dia | Publica 64; recortes 20, 20 e 24 | Teste das linhas literais |
| Falha controlada após o primeiro Gold | Latest por loja/produto = 74/64; oficial = 64/64 | `after_failure_*` |
| Retry e replay | Publica 74; replay `NO_CHANGE`, mesma publicação | `final_publication` e `steps` |

Todas as chaves da tabela estão em [business-thesis.json](evidence/editorial-20260922/business-thesis.json). O esperado foi escrito como valores literais no teste, além do contraexemplo calculado em Python independente das transformações Spark. O tempo de execução é contexto local, não medição de capacidade.

Para repetir, use o comando `verify_problem.py --thesis-only` do início deste guia. A variável `RETAIL_THESIS_EVIDENCE_DIR` ativa os exports no teste; o script já a configura. Cada execução cria estado temporário, mas reutiliza o diretório de saída escolhido: use outro `--output` para conservar uma rodada anterior. Os HTMLs mostram o estado capturado na geração, sem atualização automática ou acompanhamento ao vivo.

# Demo

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

| Passo | Ação executada | Resultado que deve aparecer |
| --- | --- | --- |
| 1 | Gerar/publicar fixture manual | 4 linhas, 7 unidades, 3 vendas, R$ 64,00; S03 confirma zero |
| 2 | Explicar S01/01-01-2026 | R$ 44,00; arquivos/linhas/chaves e versões em `artifacts/explain.json` |
| 3 | Reexecutar exatamente o mesmo lote | NO_CHANGE, mesma publicação, R$ 64,00 |
| 4 | Remover S02 da entrega já contratada | BLOCKED, loja ausente, publicação anterior R$ 64,00 |
| 5 | Repor os bytes originais sem mudar manifesto | PUBLISHED, R$ 64,00; duplicatas sem efeito |
| 6 | Revisar primeira linha e cancelar S02 posteriormente | Receita passa a R$ 77,00 e depois R$ 57,00 |
| 7 | Tentar reativação e falhar antes da troca de manifesto | TECHNICAL_FAILURE; candidato gravado, relatório oficial ainda R$ 57,00 |
| 8 | Reexecutar a tentativa interrompida | Publicação consistente com R$ 77,00, sem dupla receita |

A demo contém asserts dos estados e valores. Antes da jornada principal, gera também quality-review.html em estado isolado: cinco registros recebidos, um rejeitado com quatro violações e nenhuma publicação. Duração e identificadores de uma execução dessa jornada estão em docs/evidence/round-2/demo.json.

A jornada aprova as referências sintéticas separadamente antes de criar entregas. Para comandos individuais, execute `configure --catalog /app/data/operator/fixture/catalog.json --schedule /app/data/operator/fixture/schedule.json` uma vez. Sem configuração o processamento bloqueia. Mudanças no calendário aprovado exigem um novo `--data-dir` e reprocessamento; isso evita reinterpretar silenciosamente a história.

## Ver resultados

1. Abra `artifacts/report.html`: em **Execução**, confira a última tentativa; em **Indicadores**, confira a receita final de R$ 77,00. **Arquivos** identifica a publicação e suas versões.
2. Abra `artifacts/blocked-report.html`: a publicação válida aparece junto do bloqueio por loja ausente. Abra a ocorrência para ver seu contexto e **Indicadores** para conferir R$ 64,00.
3. Abra `artifacts/failure-report.html`: o candidato da reativação não aparece no total oficial. **Indicadores** mantém R$ 57,00 da publicação anterior.
4. Abra `artifacts/explain.json`: amostra rotulada liga o indicador à origem. O documento se refere à primeira publicação; não se confunde com a versão final da demo.
5. Veja `tests/integration/test_pipeline.py`: correção de data, revisão antiga, conflito, lote rejeitado, concorrência real e leitura por versão também são exercitados.

Servidor opcional: `scripts/pipeline.ps1 serve` → http://localhost:3103/report.html. Os três HTML também abrem diretamente como arquivo. `scripts/pipeline.ps1 stop` encerra o servidor sem remover dados.

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

## Demonstração editorial executada

Em 22/09/2026, executei a instalação pelo Dockerfile atual e a tese pequena em estado novo, com Spark 4.2.0 e Delta 4.4.0 reais. A base foi `93d80c0`, acrescida somente da exportação opcional de HTML em `test_business_thesis.py`; não atribuo essa execução ao commit puro. Interface e regras de domínio permaneceram iguais. O [registro da execução](evidence/editorial-20260922/execution.json) contém comandos, limites e hashes; [verification.json](evidence/editorial-20260922/verification.json) registra as fontes que de fato estavam na imagem.

O build normal passou usando cache local. Uma tentativa anterior de build com rede desativada falhou ao consultar o índice Alpine: o primeiro setup não é prometido como offline. O batch posterior rodou com `--network none`, raiz somente leitura, 3 GiB e duas CPUs, em um volume próprio. Smoke e teste de negócio passaram: [smoke.xml](evidence/editorial-20260922/smoke.xml) e [tests.xml](evidence/editorial-20260922/tests.xml). Não repeti o benchmark de 30 mil linhas nem a recuperação de volume desta rodada histórica.

| Caso real, com fixture sintética | Saída observada | Captura e prova |
|---|---|---|
| S02 retirada da entrada e do calendário do remetente | `BLOCKED`; expectativa independente ainda exige S02 | [Cobertura](images/editorial-20260922/coverage-blocked.png), `steps` no JSON |
| Só um item de A1 muda de dia | `SALE_DATE_CONFLICT`; soma ingênua 64, contagem ingênua 4 em vez de 3 | [Ocorrência](images/editorial-20260922/partial-date-blocked.png), `baseline_partial_date` |
| Ambos os itens mudam de dia | Publica 64; recortes 20, 20 e 24 | [Correção](images/editorial-20260922/whole-sale-corrected.png), teste das linhas literais |
| Falha controlada após o primeiro Gold | Latest por loja/produto = 74/64; oficial = 64/64 | [Publicação preservada](images/editorial-20260922/failure-before-publication.png), `after_failure_*` |
| Retry e replay | Publica 74; replay `NO_CHANGE`, mesma publicação | [Resultado](images/editorial-20260922/recovered.png), `final_publication` e `steps` |

Todas as chaves da tabela estão em [business-thesis.json](evidence/editorial-20260922/business-thesis.json). O esperado foi escrito como valores literais no teste, além do contraexemplo calculado em Python independente das transformações Spark. O tempo de execução é contexto local, não medição de capacidade.

As cinco imagens vêm dos HTMLs exportados imediatamente após cada operação, abertos no Edge a 1120 × 960 CSS px, zoom normal, fonte carregada. Usei somente navegação e expansão nativas; não substituí texto, números ou estados no DOM. Os recortes de indicadores mantêm a identificação da publicação e a tabela exata. [Registro das capturas](evidence/editorial-20260922/captures.json). As imagens da interface anteriores continuam documentando suas próprias versões e não foram sobrescritas.

Para repetir, use o comando `verify_problem.py --thesis-only` do início deste guia. A variável `RETAIL_THESIS_EVIDENCE_DIR` ativa os exports no teste; o script já a configura. Estado temporário novo não significa diretório de saída novo: escolha outro `--output` para conservar uma rodada anterior. Os HTMLs são snapshots, sem atualização automática; não são um painel de execução ao vivo.

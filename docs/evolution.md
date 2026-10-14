# Perfis de publicação e exportação local

O perfil conserva o fechamento ativo e o lote recebido separadamente. Sua comparação identifica a publicação anterior, mostra mudanças de contexto e recalcula datas e lojas comuns nas duas Silver versionadas. O adaptador [OpenLineage](openlineage.md) exporta o que o manifesto publicou e permite recuperar eventos ausentes.

## Isolamento da execução

Esta entrega reservou o projeto Compose `pf-varejo-evolucao-a12e4a`, a imagem `pf-varejo-data:evolucao-20261012-a12e4a`, o volume `pf-varejo-evolucao-a12e4a_data` e `artifacts/evolucao-20261012-a12e4a/`. O caminho interno do estado permanece em `/data`, o batch usa `network_mode: none`, 3 GiB e 2 CPUs. A porta prevista para o servidor é `127.0.0.1:3117`; iniciar o servidor é opcional. Os wrappers usam apenas o Compose principal; os comandos desta execução passam projeto e arquivos explicitamente.

Crie a pasta de exportação e salve este override em `artifacts/evolucao-20261012-a12e4a/compose.override.yaml`. Para repetir depois, use um sufixo novo nos nomes de projeto, imagem, volume e diretório.

```yaml
services:
  pipeline:
    image: pf-varejo-data:evolucao-20261012-a12e4a
    pids_limit: 1024
    volumes:
      - type: bind
        source: ./artifacts/evolucao-20261012-a12e4a
        target: /app/artifacts
  report-server:
    image: pf-varejo-data:evolucao-20261012-a12e4a
    ports: !override
      - "127.0.0.1:3117:3103"
    volumes:
      - type: bind
        source: ./artifacts/evolucao-20261012-a12e4a
        target: /app/artifacts
        read_only: true
volumes:
  data:
    name: pf-varejo-evolucao-a12e4a_data
```

No PowerShell, a partir da raiz do projeto:

```powershell
$varejoCompose = @('compose', '-p', 'pf-varejo-evolucao-a12e4a', '-f', 'compose.yaml', '-f', 'artifacts/evolucao-20261012-a12e4a/compose.override.yaml')
docker @varejoCompose --profile report config --format json
docker @varejoCompose build pipeline
docker @varejoCompose run --rm --entrypoint python pipeline -m pytest tests/integration/test_smoke.py -q
docker @varejoCompose run --rm --entrypoint sh pipeline -c 'ruff check src tests scripts && ruff format --check src tests scripts && mypy src/retail_pipeline'
docker @varejoCompose run --rm --entrypoint python pipeline -m pytest -q --junitxml=/app/artifacts/tests.xml
```

Confira no JSON resolvido a tag, o bind de exportação e o nome do volume. O nome de projeto sozinho não isola os outros dois. O scan segue o [workflow existente](../.github/workflows/ci.yml), usando esta tag, inventário OS/JVM/Python e o gate HIGH/CRITICAL de `scripts/check_image_scan.py` sem exclusões adicionais.

## Comparação válida versus não comparável

```powershell
docker @varejoCompose run --rm --entrypoint python pipeline scripts/prove_evolution.py --state-dir /data/evolution-demo --output /app/artifacts/evolution-demo
docker @varejoCompose run --rm pipeline --data-dir /data/evolution-demo profile
```

O [executor](../scripts/prove_evolution.py) exige diretórios novos. Ele produz `evolution-demo/initial-profile.json`, `comparable-profile.json`, `incomparable-profile.json`, os três manifestos correspondentes, `initial.html`, `comparable.html`, `incomparable.html` e `execution.json`. As asserts esperam:

| Cenário sintético | Decisão verificável |
| --- | --- |
| Primeira publicação, R$ 64,00 | `NO_BASELINE`; quatro linhas, sete unidades, três vendas. |
| Revisão de preço, R$ 104,00 | `COMPARABLE`; mesmas datas/lojas, WARNING de preço médio e correção publicada. |
| Todas as vendas movidas para outro dia, R$ 64,00 | `NOT_COMPARABLE`; nenhuma data em comum com a publicação anterior. |

Nos relatórios gerados pelo renderer atual, abra **O que mudou** para consultar a comparação. Nos HTMLs históricos preservados desta execução, abra **Indicadores** e use o link **Perfil e comparação**. Contexto e baseline precedem as variações; as tabelas preservam os valores exatos. Abrir o HTML não inicia Spark. O perfil conserva os totais originais e os do recorte equivalente; grupos e datas de apresentação truncados não alimentam o recálculo.

Os parâmetros demonstrativos podem ser ajustados na execução publicadora:

```powershell
docker @varejoCompose run --rm pipeline --data-dir /data/evolution-demo run /data/nova-entrega --profile-min-lines 5 --profile-quantity-threshold 0.30 --profile-price-threshold 0.20
```

Esse último caminho é um exemplo de entrega a preparar, não um arquivo produzido pelo roteiro. A configuração fica no perfil imutável. Primeira publicação, vazio, amostra pequena, ausência de baseline válida e denominador zero têm resultados próprios.

## Falha de exportação e reexportação

A etapa `comparable` do executor injeta o ponto `lineage_export` depois de trocar o ponteiro, equivalente ao argumento CLI `--demo-mode --fail-at lineage_export`. O resultado permanece `PUBLISHED`, com `LINEAGE_EXPORT_FAILURE` como WARNING e sem terminal inicial. A reconciliação gera o COMPLETE ausente e uma segunda chamada conserva seus bytes. O executor também compara hashes da publicação, perfil e evidências recebidas.

As saídas são `evolution-demo/reexport.json` e `reexport-terminal.json`. O recibo identifica o run; a faceta `varejo_outcome` do terminal identifica a publicação. Os eventos duráveis ficam em `/data/evolution-demo/lineage/events/<UUID canônico>/`. Para reconciliar novamente pelo comando público:

```powershell
docker @varejoCompose run --rm pipeline --data-dir /data/evolution-demo lineage
docker @varejoCompose run --rm pipeline --data-dir /data/evolution-demo lineage
```

Eventos existentes conservam os bytes; `errors` informa falhas de exportação e faz esse comando terminar com código 3. Isso não muda o estado do fechamento. Um escritor ativo causa `WriterBusy`, sem encerrar a tentativa. [Contrato e timestamps de reconstrução](openlineage.md).

## Recuperação, retenção e evidências

O backup inclui perfis e eventos, junto dos diretórios Delta completos e fontes anteriores. Perfis referenciados são validados por hash, vínculo e limites. Snapshots legados continuam legíveis com `LEGACY`. Repetir um lote publicado conserva publicação e perfil; candidatos órfãos não servem de baseline. [Procedimento de recuperação](state-recovery.md).

As evidências novas ficam em `docs/evidence/evolucao-20261012-a12e4a/`; exportações volumosas e ferramentas locais ficam no diretório ignorado de artifacts. Cada teste ou captura identifica os arquivos do candidato e seu diff. Durante uma suíte/captura, agentes suspendem edições ou usam cópia congelada. Tempos das fixtures são observações, sem comparação controlada de overhead ou alegação de capacidade comercial.

O servidor pode ser iniciado com `docker @varejoCompose --profile report up -d report-server`. A limpeza permitida é `docker @varejoCompose --profile report down`, que conserva o volume; não use `-v`, prune ou VACUUM para reduzir esta entrega. [Verificações e limites efetivamente executados](verification.md).

## Resultado dos dois roteiros em 12/10/2026

O executor terminou com código 0 na fonte `bc66968`, usando Spark 4.2.0/Delta 4.4.0 em Linux/amd64. Os três fechamentos foram publicados: R$ 64,00 sem baseline, R$ 104,00 com comparação equivalente e um WARNING de preço, e R$ 64,00 sem datas comuns. [Execução e parâmetros](evidence/evolucao-20261012-a12e4a/evolution-demo/execution.json) · [arquivos e hashes](evidence/evolucao-20261012-a12e4a/demo-index.json).

A falha injetada do exportador ocorreu depois do commit do segundo fechamento. A reconciliação criou o COMPLETE ausente e preservou publicação, perfil e evidências; a segunda exportação manteve os bytes do terminal. [Recibo](evidence/evolucao-20261012-a12e4a/evolution-demo/reexport.json) · [evento validado](evidence/evolucao-20261012-a12e4a/evolution-demo/reexport-terminal.json). O comando público `profile` e duas chamadas de `lineage` também terminaram com código 0; seus JSONs estão no mesmo diretório de evidências. Essa prova injeta erro no exportador; não simula desligamento do sistema operacional.

Os HTMLs reais [inicial](evidence/evolucao-20261012-a12e4a/evolution-demo/initial.html), [comparável](evidence/evolucao-20261012-a12e4a/evolution-demo/comparable.html) e [não comparável](evidence/evolucao-20261012-a12e4a/evolution-demo/incomparable.html) passaram pelos controles funcionais em quatro larguras no Edge. [Resultados e capturas](frontend-quality.md). Os tempos de perfil, 3,6761 s, 9,8586 s e 6,2000 s, incluem carga concorrente e estão dentro do intervalo `publication`; não devem ser somados a ele nem usados como overhead percentual.

As capturas de perfil no [índice desta execução](evidence/evolucao-20261012-a12e4a/browser-index.json) conservam a interface histórica e o estado dos detalhes naquele momento. Nas imagens estreitas, parte das colunas fica além da região visível da tabela; abra o HTML e role a tabela, ou consulte a captura desktop, para conferir todos os valores. O print móvel registra o arranjo e o foco visível, sem substituir a tabela completa como evidência numérica.

O servidor desta execução ficou ativo em [127.0.0.1:3117](http://127.0.0.1:3117/profile-comparable.html#perfil), com cópias dos relatórios comparável e não comparável na raiz da exportação. Para repetir, copie `evolution-demo/comparable.html` para `profile-comparable.html` no diretório exportado antes de iniciar o servidor: ele serve HTMLs da raiz. Um volume Compose e três volumes da restauração foram preservados. [Recursos e comando de encerramento](evidence/evolucao-20261012-a12e4a/resources.json).

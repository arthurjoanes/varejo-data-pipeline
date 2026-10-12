# OpenLineage local

O comando `lineage` reconcilia eventos a partir das tentativas e publicações duráveis. Ele não abre Spark. Uma execução reconciliada com sucesso conserva um `START` e um terminal em `/data/lineage/events/<UUID canônico>/`, gravados atomicamente. Os eventos descrevem a publicação que o manifesto tornou visível e as entradas que a sustentam.

## Estados e versões

| Estado do pipeline | Evento terminal | Dados anunciados |
| --- | --- | --- |
| `PUBLISHED` | `COMPLETE` | Saídas do manifesto comprometido, com versões Delta exatas; `newPublication=true`. |
| `NO_CHANGE` | `COMPLETE` | Publicação original identificada na faceta; versões oficiais como entradas, saídas vazias e `newPublication=false`. |
| `VALIDATED` | `COMPLETE` | Job `retail.validate`, sem novas saídas Gold nem nova publicação. |
| `BLOCKED` | `FAIL` | Códigos de bloqueio em `reasonCodes` e na faceta padrão `errorMessage`; saídas vazias. |
| `TECHNICAL_FAILURE` | `FAIL` | Motivo técnico ou `INTERRUPTED_ATTEMPT`; saídas vazias. |

O pipeline registra `START` depois de persistir a tentativa. O terminal vem depois da auditoria final. Se a exportação falhar depois da troca de `publication.json`, o fechamento permanece `PUBLISHED` e registra `LINEAGE_EXPORT_FAILURE` como `WARNING`. A reexportação produz o `COMPLETE` faltante.

`inputs` descreve fontes aceitas em uma publicação. `VALIDATED` e `FAIL` mantêm essa lista vazia: a tentativa conserva as evidências da entrega inspecionada, mas o evento não atribui aceitação comercial a ela.

As facetas padrão `schema`, `version` e `errorMessage` usam os schemas oficiais fixados. `varejo_outcome` registra modo, estado, publicação e lotes aceitos. `varejo_provenance` carrega o lote, UUID da origem, hash do manifesto e hashes das referências aprovadas disponíveis. Os namespaces são `urn:varejo-data-pipeline:local`, `urn:varejo-data-pipeline:delta` e `urn:varejo-data-pipeline:references`. Nomes de datasets usam identidades lógicas, sem os caminhos físicos do computador. Mensagens de exceção, stack traces, linhas brutas e credenciais ficam fora dos eventos.

## Identidade e tempo

`uuid.uuid4().hex` e sua forma UUID com hífens representam a mesma identidade. O adaptador converte a forma, sem gerar outro UUID aleatório. Identificadores legados que não sejam UUID usam UUIDv5, namespace fixo `b04ef31f-0b44-5cfa-9300-c6bba32ea0b0` e o identificador original como nome. `varejo_timing.identityMapping` distingue `uuid` de `uuid5`; o identificador legado bruto não é exportado.

O início usa `attempt.started_at`. O terminal usa `attempt.finished_at` quando disponível; na recuperação de um commit sem tentativa final, usa `publication.published_at`. `originalEventTime` conserva o horário observado, e `eventTimeSource` informa a origem. Eventos recuperados acrescentam `reconstructedAt`. Se não existir um horário original válido, `originalTimeAvailable=false`, `eventTimeSource=reconstruction` e `eventTime` corresponde ao momento da reconstrução. Esse instante não é apresentado como o horário exato de uma execução antiga.

## Recuperação e idempotência

`lineage` obtém o mesmo `writer_lock` não bloqueante do pipeline. Um escritor ativo impede a reconciliação; assim, ela não encerra uma execução que continua gravando. Depois de adquirir o lock, uma tentativa `RUNNING` sem commit pode receber `FAIL` com `INTERRUPTED_ATTEMPT`. Uma tentativa ainda `RUNNING` cujo run aparece em uma publicação comprometida recebe `COMPLETE`.

O ponteiro atual e a cadeia `previous_publication_id` identificam os commits. `publications/*.json` sozinho não prova publicação: a auditoria é preparada antes da troca do ponteiro. `candidate.json` nunca autoriza saídas. Ao alcançar um snapshot legado sem cadeia, a reconciliação também aceita uma tentativa final `PUBLISHED` cujo run e publication_id coincidam com sua auditoria imutável. Sem essa prova, não anuncia o manifesto como fechamento.

Uma execução conserva os caminhos `start.json` e `terminal.json`. Reexportar mantém os bytes existentes, inclusive seu primeiro horário de reconstrução. Divergências em entradas, saídas, estado ou identidade retornam erro; o comando não sobrescreve o evento anterior. A tentativa, o candidato, a publicação e as evidências também conservam seus bytes.

O comando informa `runs`, `events`, `paths`, `errors` e o schema fixado. Falhas de um evento permitem conferir os demais runs e corrigir o problema antes de repetir o comando. A cadeia de publicação inválida ou o lock ocupado impedem a reconciliação.

## Reprodução da falha de exportação

Prepare o override e a variável `$varejoCompose` do [roteiro isolado](evolution.md#isolamento-da-execução), com volume novo e caminhos internos em `/data`. A partir da raiz do repositório, no PowerShell:

```powershell
docker @varejoCompose run --rm pipeline generate --scenario valid --batch-id lineage-proof --output /data/input-lineage
docker @varejoCompose run --rm pipeline configure --catalog /data/input-lineage/catalog.json --schedule /data/input-lineage/schedule.json
docker @varejoCompose run --rm pipeline run /data/input-lineage --demo-mode --fail-at lineage_export
docker @varejoCompose run --rm pipeline lineage
docker @varejoCompose run --rm pipeline lineage
```

Após `run`, confira `publication.json`, o perfil referenciado e a tentativa `PUBLISHED` com o warning. O primeiro `lineage` deve criar o terminal `COMPLETE`; o segundo conserva seus bytes. Os arquivos ficam em `/data/lineage/events/<UUID canônico>/start.json` e `terminal.json`. A evidência da execução precisa registrar os arquivos e hashes realmente produzidos; os comandos deste guia não constituem prova de execução.

## Referência e limites

O [modelo de eventos do OpenLineage](https://github.com/OpenLineage/OpenLineage/blob/4e4a9186962094ce5fd29c5e4bc9d5ddb5fa39a8/spec/OpenLineage.md) orienta o par início/terminal e a identificação de runs/datasets. Os [schemas e a atribuição local](../src/retail_pipeline/schemas/README.md) fixam a especificação `2-0-2` da tag `1.39.0`, com licença Apache-2.0. O projeto aproveita esse contrato para exportação de arquivos; Marquez, Airflow, Kafka e collectors continuam fora desta demonstração. Validar os eventos localmente não comprova ingestão em uma plataforma externa. A URN das facetas próprias exige registro do schema local pelo consumidor.

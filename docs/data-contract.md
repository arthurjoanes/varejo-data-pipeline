# Contrato de dados, versão 1

## Identidade das referências de validação

Além do hash canônico do manifesto, a primeira tentativa fixa o SHA-256 dos bytes
de `catalog.json` e `schedule.json` no registro do lote. Uma repetição com qualquer
dessas referências alterada é bloqueada com `BATCH_REFERENCE_CONFLICT`, mesmo que
o CSV não mude. Reformatar esses JSON também exige novo `batch_id`; essa regra
conservadora evita reinterpretar silenciosamente uma entrega já auditada.
Arquivo CSV faltante/corrompido continua podendo ser reposto com os bytes previstos
no manifesto original. Referência recebida na entrega ausente ou inválida exige um novo lote após
a correção. Registros legados sem hashes seguem legíveis nas publicações anteriores,
mas não podem ser repetidos: use novo `batch_id` para validar referências conhecidas.
Esses hashes também acompanham cada fonte nova no manifesto publicado e no `explain`.

Origem: exportador sintético `synthetic-pos`, implementado em `generation.py`; nenhuma informação de empresa ou cliente real. Moeda única BRL, dia comercial em `America/Sao_Paulo`. A distribuição por loja, produto, horário e desconto é uma hipótese de simulação, sem representatividade estatística alegada.

## Arquivos e configuração

Uma entrega contém `manifest.json`, `catalog.json`, `schedule.json` e CSVs UTF-8 sem BOM. Separador vírgula, aspas duplas conforme CSV, cabeçalho obrigatório na ordem abaixo. Quebras LF no gerador. Cabeçalho de arquivo e schema não são inferidos pelo Spark. Arquivo de zero bytes é inválido; CSV contendo apenas cabeçalho requer confirmação explícita de zero movimento. Todo arquivo inesperado bloqueia o lote.

`catalog.json` é configuração do operador: `schema_version:1`, `stores` com `store_id,name,state,timezone,active` e `products` com `product_id,name,category`. Identificadores são únicos; somente lojas ativas são referências válidas. Nome/categoria são rótulos não vazios; estados são categorias fictícias do cenário; timezone é sempre `America/Sao_Paulo`.

`schedule.json` é configuração independente do manifesto do remetente: `schema_version:1`, `windows` com `window_id,source_system,stores,starts_at,ends_at`. A combinação origem/janela é única; a lista esperada é não vazia, sem repetições, e referencia lojas ativas. Início/fim são instantes ISO-8601 com offset e início anterior ao fim, representando um intervalo de entrega `[starts_at,ends_at)`. Na simulação, Jan1–Mar1 de 2026 permite demonstrar revisões atrasadas. A data da venda não precisa pertencer à janela de entrega. Não se valida o relógio da execução contra esse intervalo: reprocessar uma entrega antiga é permitido.

O comando explícito `configure --catalog <aprovado> --schedule <aprovado>` valida e fixa esses documentos em `<data-dir>/operator-references.json`, separado da entrega. A fixture aprovada fica em `data/operator/fixture`. Repetir a configuração idêntica é permitido; trocar conteúdo exige estado novo. Publicação legada sem configuração fixa continua legível, mas exige novo estado e reprocessamento para operar com essa fronteira de confiança.

As cópias de `catalog.json`/`schedule.json` na entrega continuam sendo validadas e auditadas; não autorizam lojas/produtos nem definem o denominador. O processamento exige a configuração externa (`OPERATOR_REFERENCES_MISSING` quando ausente), guarda uma cópia na tentativa e usa somente ela para referências e lojas esperadas. Cada fonte publicada registra seu `operator_reference_hash`. Um remetente que omite S02 nos arquivos, manifesto e calendário continua sendo comparado às três lojas aprovadas. O filesystem pertence ao operador local; não há autenticação multiusuário ou defesa contra quem altera diretamente o estado interno.

Exemplo de manifesto, abreviado:

```json
{
  "schema_version": 1,
  "batch_id": "fixture-valid",
  "source_system": "synthetic-pos",
  "window_id": "jan-2026",
  "files": [
    {
      "path": "S01.csv",
      "store_id": "S01",
      "sha256": "<64 hex minúsculos>",
      "row_count": 3
    }
  ],
  "zero_movement": [
    "S03"
  ],
  "covered_stores": [
    "S01",
    "S03"
  ]
}
```

`files` lista cada caminho uma vez. Hash é SHA-256 dos bytes, contagem exclui cabeçalho. Caminhos são relativos POSIX `.csv`, sem `..`, barra invertida, drive, caminho absoluto ou normalizações ambíguas. Symlinks são rejeitados sem ler o destino. `zero_movement` é uma lista de lojas esperadas, sem repetições e sem registros nessa entrega. `covered_stores`, opcional, deve coincidir exatamente com lojas dos arquivos mais confirmações. O campo opcional `correction_of` identifica o lote corrigido. Campos desconhecidos e chaves JSON duplicadas são inválidos.

## Grão e campos

Grão: revisão completa de um item de venda. Todos os campos são obrigatórios e não nulos. Identificador seguro significa expressão `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`; não há remoção silenciosa de espaços. A chave é `source_system,store_id,sale_id,line_id`.

| Campo               | Tipo/limites                         | Significado e exemplo                                               |
| ------------------- | ------------------------------------ | ------------------------------------------------------------------- |
| `source_system`     | Identificador                        | Origem; deve corresponder ao manifesto, ex. `synthetic-pos`         |
| `store_id`          | Identificador, referência ativa      | Loja; também corresponde à loja declarada para o arquivo, ex. `S01` |
| `sale_id`           | Identificador                        | Venda dentro da origem/loja, ex. `A1`                               |
| `line_id`           | Identificador                        | Item dentro da venda, ex. `1`                                       |
| `revision`          | Inteiro 1–2.147.483.647              | Ordem total das imagens da mesma chave                              |
| `operation`         | `UPSERT` ou `CANCEL`                 | Atualização completa ou cancelamento completo                       |
| `product_id`        | Identificador, referência de produto | Produto da imagem, ex. `P01`                                        |
| `sold_at`           | ISO-8601 com offset                  | Instante da venda, ex. `2026-01-01T12:00:00-03:00`                  |
| `quantity`          | Inteiro 1–1.000.000                  | Unidades da linha                                                   |
| `unit_price_brl`    | Decimal, 0–999.999.999,99            | Preço unitário BRL; ponto decimal, até 2 casas                      |
| `line_discount_brl` | Decimal não negativo, <= bruto       | Desconto total da linha, não por unidade                            |
| `source_updated_at` | ISO-8601 com offset                  | Instante de atualização informado pela origem                       |

Dinheiro não admite notação científica, sinal, vírgula, `NaN`, infinito ou arredondamento silencioso. Silver utiliza Decimal(18,2) em preço/desconto e Decimal(24,2) no líquido da linha; Gold utiliza Decimal(28,2) em receita/ticket; os limites por linha impedem overflow no bruto `quantity × unit_price_brl`. Desconto também deve caber em Decimal(18,2). `sold_at` e `source_updated_at` aceitam até 6 casas nos segundos. Datas sem timezone e datas impossíveis são bloqueadas. Minutos de offset devem ficar entre 00 e 59; o offset completo deve ser menor que 24 horas. O instante normalizado em UTC e o dia comercial de `sold_at` precisam caber nos anos 0001–9999 dos leitores Python. A persistência Parquet usa escrita `CORRECTED`, preservando o calendário gregoriano, inclusive em datas anteriores a 1900; não é uma conversão para calendários híbridos legados. Os timestamps são normalizados em UTC; source_updated_at é informativo e não ordena revisões nem impõe comparação causal entre relógios.

## Revisão, cancelamento e identidade

`CANCEL` exige a mesma imagem completa e as mesmas validações de um UPSERT. Mantém histórico e estado tipado, porém não contribui para indicadores. Uma revisão maior UPSERT pode reativar o item. Correções podem alterar produto, quantidade, preço, desconto e instante da venda; a chave permanece estável. Revisão menor nunca substitui a maior.

No estado candidato, todos os itens ativos de `(source_system,store_id,sale_id)` devem ter o mesmo dia comercial. Uma mudança parcial de data é `SALE_DATE_CONFLICT`: bloqueia o lote inteiro, inclusive em `validate`, antes das tabelas candidatas. A correção deve revisar todos os itens necessários; itens CANCEL não contam. O código em `issues` conta vendas inconsistentes; `rejected`/`violations` contam os registros recebidos dessas vendas, sem incluir linhas históricas no denominador. Revisões desse lote bloqueado não entram no histórico elegível.

Hash do payload cobre os 12 campos de negócio em JSON ordenado, UTF-8; inteiros sem zeros à esquerda, dinheiro com 2 casas, datas UTC com 6 casas. Não inclui run_id, nome do arquivo, linha ou horário de execução. Assim `10` e `10.00`, ou timestamps equivalentes com offsets distintos, representam o mesmo payload. Chave/revisão/payload igual é duplicata informativa; chave/revisão/payload diferente é conflito bloqueante. A autoridade histórica é somente o histórico referenciado pela publicação válida.

`batch_id` identifica contrato imutável; `run_id` identifica tentativa. Hash lógico do manifesto ordena chaves JSON e listas sem significado de ordem (`files`, cobertura e zero movimento), preservando hashes físicos dos arquivos. Corrigir arquivo ausente/corrompido segundo o manifesto original permite reexecução. Alterar conteúdo esperado exige novo batch_id. Reordenar CSV exige novos hashes/manifesto e novo batch_id, mas mantém os eventos de negócio. Metadados de execução podem variar sem alterar indicadores.

## Bronze, quarentena e contagens

Antes de interpretar a entrega, a ingestão copia arquivos regulares para `evidence/raw/` da tentativa. Todo processamento da entrega usa essa cópia; as referências aprovadas do operador são capturadas separadamente. Bytes inválidos, CSV quebrado e arquivos inesperados permanecem disponíveis para diagnóstico; symlinks têm apenas o caminho registrado como violação, nunca o conteúdo externo. Arquivos especiais, como FIFO, são rejeitados com `UNSAFE_FILE_TYPE` sem bloquear a leitura à espera de outro processo.

`rows.ndjson` guarda os 12 campos como strings canônicas quando válidas, ou o valor inválido original; acrescenta `batch_id,run_id,source_file,source_line,payload_hash,errors,raw_payload`. `source_line` é a linha física inicial do registro CSV, inclusive em registros com quebras de linha entre aspas. `raw_payload` contém os valores e cabeçalho originais, preservando inclusive colunas extras ou faltantes. Linhas inválidas compõem a quarentena pela lista `errors` e nunca tornam um lote parcialmente publicável.

`received` conta registros que o parser CSV conseguiu delimitar, inclusive registros com largura/schema/tipos inválidos. `valid` e `rejected` particionam esse denominador; um registro com quatro regras inválidas aumenta rejeitados em 1 e violações em 4. Arquivos ilegíveis/truncados podem impedir contagem completa; nesses casos o número é apenas o total legível, o erro físico bloqueia tudo e os bytes permanecem preservados. O relatório não trata esse total como cobertura completa. `violations` conta erros por registro, não erros físicos de arquivo/manifesto. Erros físicos e de cobertura aparecem separadamente em `issues` com severidade ERROR. Não há descarte silencioso seguido de publicação.

Códigos estáveis principais: `MISSING_FILE`, `MISSING_STORE`, `UNEXPECTED_FILE`, `UNSAFE_PATH`, `UNSAFE_SYMLINK`, `HASH_MISMATCH`, `ROW_COUNT_MISMATCH`, `SCHEMA_MISMATCH`, `ROW_WIDTH_MISMATCH`, `CSV_DECODE_ERROR`, `EMPTY_FILE`, `EMPTY_WITHOUT_ZERO_CONFIRMATION`, `INVALID_ZERO_CONFIRMATION`, `COVERAGE_MISMATCH`, `UNKNOWN_STORE`, `UNKNOWN_PRODUCT`, `INVALID_QUANTITY`, `INVALID_REVISION`, `INVALID_UNIT_PRICE_BRL`, `INVALID_LINE_DISCOUNT_BRL`, `DISCOUNT_EXCEEDS_GROSS`, `INVALID_SOLD_AT`, `INVALID_SOURCE_UPDATED_AT`. Todos bloqueiam a publicação. Erros adicionais identificam configurações/manifestos malformados. Contagens agregadas de cada regra são limitadas ao número de códigos, não à massa de registros.

## Orçamento da entrada

O snapshot limita bytes efetivamente lidos, sem confiar somente no tamanho informado pelo arquivo: 1 MiB por JSON, 64 MiB por arquivo, 256 MiB por entrega e 1.000 arquivos, incluindo inesperados. Ajuste `RETAIL_MAX_JSON_BYTES`, `RETAIL_MAX_FILE_BYTES`, `RETAIL_MAX_TOTAL_BYTES` e `RETAIL_MAX_FILES` no `.env`, sempre com inteiros positivos. O menor teto prevalece. A leitura de JSON para `configure` também respeita o limite antes de decodificar ou analisar o documento.

Ao exceder um teto, a cópia para imediatamente. O prefixo já copiado permanece em `evidence/raw`, e `evidence/snapshot.json` registra `complete: false`, bytes copiados, caminho interrompido, motivo e limites. Esse prefixo **não é uma entrega completa**: nenhuma linha é interpretada a partir dele, e a tentativa fica BLOCKED (saída 2). A publicação anterior permanece igual. Os códigos são `INPUT_JSON_BYTES_LIMIT`, `INPUT_FILE_BYTES_LIMIT`, `INPUT_TOTAL_BYTES_LIMIT` e `INPUT_FILE_COUNT_LIMIT`. Um arquivo exatamente no limite é aceito.

O orçamento é por tentativa. Não define quota acumulada do volume nem elimina a necessidade de retenção de `runs`, arquivos Delta e logs. Preserve evidências necessárias à auditoria e faça backup antes de limpar estados ou migrar runtimes.

## Fixture e geração

Fixture manual: S01/A1 linha1 `2 × 10 − 1 = 19`; S01/A1 linha2 `1 × 5 = 5`; S01/A2 linha1 `3 × 7,50 − 2,50 = 20`; S02/B1 linha1 `1 × 20 = 20`; S03 confirma zero. Total R$ 64,00, 4 linhas, 7 unidades e 3 vendas. S01 tem R$ 44,00, 6 unidades, 2 vendas e ticket R$ 22,00; S02 tem R$ 20,00 e ticket R$ 20,00. Produto P01 soma R$ 39,00 e 3 unidades; P02 R$ 5,00 e 1 unidade; P03 R$ 20,00 e 3 unidades.

Gerador versão 2: `fixture` usa os exemplos manuais; `demo` usa 30 mil linhas, 12 lojas, 12 produtos e 30 dias; `scale` aceita volume e seed configuráveis. Mesma versão/seed/configuração produz bytes iguais, sem depender da hora atual. IDs têm loja/venda/linha determinísticas. O gerador escreve CSV em fluxo; a ingestão processa registros em fluxo; nenhum desses caminhos carrega a demo toda em memória. Cenários de correção/cancelamento/falha de valor usam a fixture pequena. Dados grandes ficam no volume Docker; apenas `data/samples/fixture-valid` permanece versionável.

Duplicatas, conflitos e revisões antigas só são avaliados depois que a integridade física e os contratos de linha passam. A flag revision_checks_executed diferencia zero ocorrências de verificação não executada; o relatório exibe Não avaliado nesses casos.

Na apresentação monetária, o relatório arredonda valores calculados para duas casas com `ROUND_HALF_UP`, coerente com o cast decimal do ticket em Spark: `1.005` é exibido como `R$ 1,01`. Essa decisão afeta a apresentação de médias e não flexibiliza o contrato de entrada, que continua recusando dinheiro com mais de duas casas.

## Resumo sem vendas e apresentação

Receita e unidades de uma publicação válida sem itens ativos são zero. O `explain` aplica a mesma regra às contribuições ativas selecionadas; um recorte vazio não confirma a cobertura da loja ou do período. Ticket médio é receita dividida pelas vendas: com zero vendas, o resumo guarda `None` e o relatório mostra `—` / “Sem vendas no período”. Com uma ou mais vendas de preço zero ou desconto integral, ticket zero é válido. O caso foi exercitado em Delta com zero movimento, todas as linhas CANCEL e reativação gratuita. Ausência de publicação continua distinta de uma publicação sem movimento.

O eixo do gráfico utiliza intervalos arredondados em reais; os pontos e a tabela diária conservam os valores monetários exatos. Durações aparecem com uma casa na leitura rápida e com a precisão registrada em detalhe. IDs longos no resumo são abreviados, com acesso aos valores completos e cópia na proveniência.

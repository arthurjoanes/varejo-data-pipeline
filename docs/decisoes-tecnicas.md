# Decisões técnicas

Resultados dos testes em [verification.md](verification.md).

## Grão, chaves e revisões

O grão de entrada é uma imagem completa de uma revisão de um item de venda. A chave de negócio é `(source_system, store_id, sale_id, line_id)`. A revisão é inteira positiva e ordena o estado da mesma chave; chegada mais recente não significa informação mais atual.

| Situação | Decisão e consequência |
|---|---|
| Chave + revisão + payload iguais | Duplicata exata: nenhum efeito adicional nos indicadores. |
| Chave + revisão iguais, payload diferente | Conflito bloqueante: o pipeline não escolhe arbitrariamente uma imagem. |
| Revisão maior | Nova imagem completa substitui o estado corrente. |
| Revisão menor que chega depois | Fica no histórico elegível; o estado não regride. |
| Revisão maior com `CANCEL` | Mantém imagem e trilha, retirando a linha dos indicadores. |
| Revisão ainda maior com `UPSERT` | Reativa a linha, conforme política explícita do contrato. |

O hash canônico usa os campos de negócio tipados e normalizados. `run_id`, instante de execução e arquivo de chegada são proveniência; incluí-los no hash transformaria o mesmo evento reenviado em evento diferente. `dropDuplicates` sozinho não resolve revisão, conflito nem desempate de proveniência. Antes de `MERGE`, a origem precisa conter no máximo uma linha por chave.

## Completude não é validade

Um lote pode conter apenas linhas válidas e ainda estar incompleto porque uma loja foi omitida. A expectativa vem de configuração independente da entrega. Por outro lado, a presença de todas as lojas não garante tipos, referências e valores corretos.

“Não recebi nada da loja” e “a loja confirmou zero movimento” são fatos diferentes. A confirmação explícita permite conciliar expectativa e entrega sem inventar vendas. Arquivo vazio, arquivo ausente e conteúdo corrompido têm diagnósticos próprios. O mesmo `batch_id` conserva a identidade do manifesto mesmo quando bloqueado: pode-se repor um arquivo correto que estava ausente, mas uma mudança do contrato exige novo lote.

Bronze guarda cópias de tentativas rejeitadas. Elas não se tornam autoridade para conflitos ou revisões futuras. O histórico de negócio elegível é selecionado pelo manifesto publicado, e não pela existência física de uma tabela candidata.

## Dinheiro, calendário e contagens

O contraexemplo central está em `test_business_thesis.py`: mover somente um item de uma venda entre dias preserva receita, mas um agrupamento direto conta a venda duas vezes. A decisão é bloquear o candidato inteiro até que todos os itens ativos da mesma origem/loja/venda tenham o mesmo dia; a revisão rejeitada não impede uma revisão menor posterior elegível. A configuração externa do operador impede o outro falso positivo: declarar menos lojas para que a entrega incompleta pareça completa.

`line_net_brl = quantity × unit_price_brl − line_discount_brl`. Dinheiro é decimal; descontos não podem ultrapassar o bruto. Cancelamentos são imagens completas validadas, não quantidades negativas ou heurísticas. Estorno parcial e reembolso monetário ficam fora desta versão.

O dia comercial deriva de `sold_at` em `America/Sao_Paulo`. Um evento recebido hoje pode corrigir um dia antigo; se corrigir a data da venda, o valor precisa sair do dia anterior e entrar no novo. `source_updated_at` é informação da origem, não substitui a ordenação por revisão.

Vendas são distintas por origem, loja, venda e dia comercial no conjunto ativo. Uma venda com vários produtos conta uma vez na loja/dia. Não se somam contagens distintas por produto para obter esse número. Ticket = receita líquida ÷ vendas daquele escopo. No relatório, o ticket do período usa a soma das contagens loja/dia e o total de receita; não é a média dos tickets das linhas gold.

Registro rejeitado é uma linha com pelo menos uma violação. Se uma linha tem três problemas, há um rejeitado e três violações. O percentual usa os registros recebidos como denominador; não promete completude quando um arquivo sequer chegou. Duplicatas e revisões antigas são contagens diagnósticas que podem se sobrepor a outros recortes.

## O que torna a publicação consistente

Delta fornece transações por tabela. Gravar dois gold em sequência não cria uma transação única entre eles. A decisão deste projeto é manter um escritor exclusivo durante toda a execução mutante, gravar candidatos, reconciliar e trocar um único manifesto no filesystem Linux local. Caminho e `versionAsOf` de cada saída ficam registrados nele.

Todos os leitores oficiais capturam o manifesto uma vez. Reconsultá-lo entre leituras poderia misturar silver de uma publicação e gold de outra. A falha depois do primeiro gold deixa candidatos físicos, mas preserva a visão oficial anterior. A retomada parte dessa visão oficial e reconstrói o candidato. `flock` é liberado pelo sistema operacional quando o processo termina; um mero arquivo de sinalização poderia ficar órfão.

A garantia demonstrável é de consistência diante das falhas de processo testadas no ambiente local. Ela não implica consenso distribuído, proteção contra qualquer perda de energia ou equivalência do rename local com operações remotas. Não há `VACUUM` automático: remover arquivos de versões ainda referenciadas quebraria a leitura oficial.

## Idempotência e custo de recomputar

Idempotência significa igualdade dos dados de negócio e indicadores ao reapresentar a mesma entrada. Tentativas, logs e versões técnicas podem ser diferentes. Reordenar fisicamente o CSV modifica seu hash de arquivo: esse teste usa novo lote e manifesto correto, mantendo os mesmos eventos lógicos.

Recompor silver e recalcular gold reduz estados intermediários e simplifica correções de data, cancelamentos e recuperação. O custo cresce com todo o histórico aceito, e o startup do Spark pesa no volume pequeno. É uma decisão proporcional a uma demonstração de cerca de 30 mil linhas.

Uma evolução incremental precisa guardar o estado anterior e o novo de cada chave, identificar ambos os dias afetados, tratar chaves canceladas/reativadas, proteger o histórico elegível e preservar o mesmo protocolo de publicação. O teste de equivalência é comparar o incremental à recomputação completa em cenários gerados e fixtures manuais.

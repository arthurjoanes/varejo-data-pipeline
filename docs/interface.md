# Interface do fechamento

O relatório é um snapshot: a geração consulta o manifesto uma vez, lê as versões Delta correspondentes e captura a última tentativa e a última falha disponíveis. Abrir o HTML depois não consulta o pipeline nem atualiza seu estado.

## Navegação

**Execução** começa pela decisão da última tentativa. Quando falta S02.csv, o título informa o bloqueio, a linha seguinte identifica arquivo e loja, e **Conferir pendência** leva o foco à ocorrência. **Como retomar** explica a reposição dos bytes originais ou a criação de outro lote, conforme o caso. A publicação anterior fica em uma faixa neutra, com sua própria identidade.

A ocorrência principal reúne causa e procedimento. A ausência de entrega da mesma loja fica em **Ocorrências relacionadas**, preservando o registro sem repetir o mesmo bloqueio na leitura inicial. Código, severidade e mensagem original permanecem no contexto técnico. Cobertura e contadores ficam em detalhes separados: zero erros em linhas recebidas não comprova que todas as lojas entregaram.

As etapas medidas formam uma lista de tempos, sem um painel repetido para a etapa selecionada. Cada etapa abre a explicação e seu tempo exato; uma medição não equivale a aprovação. As ocorrências conservam código, severidade e contexto de loja, arquivo e linha quando registrados. Cobertura e contadores mantêm a diferença entre zero, indisponível e não avaliado.

**Indicadores** contém os números da publicação vigente, com tabela equivalente ao gráfico e recortes por produto e loja/dia. Totais consideram o conjunto inteiro; avisos identificam o limite de exibição de 366 dias, 20 produtos e 500 linhas.

**Arquivos** permite consultar e copiar os IDs completos. As versões e os caminhos Delta vêm do manifesto; fontes bronze e hashes de catálogo/calendário permanecem associados ao lote de origem.

Com JavaScript, a navegação seleciona um painel e conserva âncoras e histórico do navegador. Sem JavaScript, os três painéis aparecem em sequência e os detalhes nativos continuam disponíveis. Nenhuma biblioteca externa, fonte remota ou API é necessária.

## Estados que não podem se confundir

- Tentativa bloqueada ou falha antes da publicação: a publicação anterior continua identificada, se existir; sem publicação, os indicadores ficam indisponíveis.
- Publicação concluída com falha no registro final: o fechamento permanece disponível, com aviso de auditoria incompleta. Duração e contadores ausentes não viram zero.
- Sem mudança: a tentativa preserva a publicação vigente.
- Última falha anterior: fica separada da última tentativa e acessível como ocorrência histórica.
- Execução sem resultado final: reflete o registro consultado, sem sugerir acompanhamento ao vivo.

## Capturas e reprodução

As capturas desta interface reutilizam os dados sintéticos da [demo histórica](evidence/round-2/demo.json) e do [experimento histórico de volume](evidence/benchmark.json). Os payloads foram extraídos por versão na revisão inicial e reutilizados offline nesta composição; nenhum lote, leitura Spark ou benchmark foi reexecutado nesta rodada. Os JSONs em [payloads](evidence/interface/payloads) identificam a fonte e seu SHA-256, além dos dados efetivamente usados.

Para renderizar esses payloads novamente, depois do setup:

```sh
docker compose run --rm --entrypoint python pipeline scripts/render_review.py
```

Esse comando gera `artifacts/interface/*.html` sem iniciar Spark. Os arquivos `empty-fixture`, `running-fixture`, `audit-fixture` e `long-fixture` são estados artificiais para testar a apresentação; não documentam novas execuções do pipeline.

A opção `--capture` do script é de desenvolvimento: exige o volume que contém as publicações históricas indicadas nos documentos e inicia Spark apenas para leitura. Ela não modifica o ponteiro de publicação nem executa entregas.

A verificação de navegador é `node scripts/visual-review.cjs`, com Playwright disponível no ambiente. `PLAYWRIGHT_MODULE` permite indicar um módulo instalado fora do repositório; `PLAYWRIGHT_CHANNEL=msedge` seleciona Edge. A biblioteca não é dependência do HTML. Resultados, escopo e limitações ficam em [verificação](verification.md).

Capturas: [execução](images/interface-v2/report.png), [bloqueio](images/interface-v2/blocked.png), [indicadores](images/interface-v2/indicators.png), [arquivos](images/interface-v2/files.png) e [tela estreita](images/interface-v2/report-390.png). As imagens `audit.png`, `empty.png` e `running.png` demonstram as fixtures de apresentação identificadas acima.

## Revisão anterior de jornadas em 22/09

No fechamento bloqueado, abra **Execução** e confira S02 ausente, duas de três lojas confirmadas e somente Ingestão medida. Em **Indicadores**, a publicação anterior conserva R$ 64,00. Em **Arquivos**, o ID da publicação e suas versões são distintos dos IDs da tentativa bloqueada. O mesmo percurso mantém R$ 57,00 no snapshot de falha anterior à publicação e R$ 77,00 depois da retomada.

A [revisão de jornadas](evidence/interface-journeys/review.json) conferiu esses três percursos em 1440, 390 e 320 px, incluindo valores por loja, versões e caminhos Delta, navegação por teclado, foco, histórico e rolagem interna das tabelas. Também conferiu ausência de publicação, execução sem resultado final, auditoria incompleta, leitura sem JavaScript, impressão dos três painéis e reflow. Não houve nova execução de lote: os payloads históricos foram renderizados offline pela fonte daquela revisão.

Capturas dessa revisão: [bloqueio no celular](images/interface/journey-blocked-390.png), [indicadores após retomada](images/interface/journey-recovered-indicators.png) e [origem da publicação](images/interface/journey-published-files.png). Elas complementam as imagens anteriores; não substituem sua evidência histórica.

## Refinamento da apresentação em 22/09

A composição atual usa navegação horizontal, diagnóstico no eixo principal e uma lista secundária de medições. Em telas estreitas, os painéis ocupam a mesma largura; títulos longos deixam o sinal de expansão em sua própria coluna. A borda de severidade pertence à ocorrência inteira, inclusive com o registro técnico aberto. A tipografia distingue decisão, conteúdo e metadados; valores não recebem animação. Hover e foco usam transições de 180 ms, removidas com `prefers-reduced-motion`.

[Revisão do navegador](evidence/interface-v2/visual-review.json), [bloqueio com detalhes em desktop](images/interface-v2/blocked-expanded-1366.png), [o mesmo estado em 390 px](images/interface-v2/blocked-expanded-390.png) e [erros em registros](images/interface-v2/quality-mobile.png). A impressão mostra os três painéis e o conteúdo dos detalhes; a captura verifica CSS de impressão, sem certificar paginação de PDF. As provas anteriores e suas imagens continuam preservadas.

## Limpeza de regras sem consumidores

Foram removidos dois seletores que não correspondiam ao HTML gerado e uma variável CSS sem uso. A composição e as capturas permanecem as mesmas. O [registro da limpeza](evidence/interface-v2/cleanup.json) descreve o delta e as verificações estáticas; as provas anteriores não foram reexecutadas nem substituídas.

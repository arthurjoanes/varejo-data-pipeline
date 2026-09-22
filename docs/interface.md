# Interface do fechamento

O relatório é um snapshot: a geração consulta o manifesto uma vez, lê as versões Delta correspondentes e captura a última tentativa e a última falha disponíveis. Abrir o HTML depois não consulta o pipeline nem atualiza seu estado.

## Navegação

**Execução** aproxima as etapas medidas do diagnóstico da entrega. Cada etapa abre a explicação e seu tempo exato; uma medição não equivale a aprovação. As ocorrências conservam código, severidade e contexto de loja, arquivo e linha quando registrados. Cobertura e contadores mantêm a diferença entre zero, indisponível e não avaliado.

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

As capturas desta interface reutilizam os dados sintéticos da [demo histórica](evidence/round-2/demo.json) e do [experimento histórico de volume](evidence/benchmark.json). As publicações foram relidas por versão com o renderizador atual; nenhum lote nem benchmark foi reexecutado para atualizar a apresentação. Os JSONs em [payloads](evidence/interface/payloads) identificam a fonte e seu SHA-256, além dos dados efetivamente usados.

Para renderizar esses payloads novamente, depois do setup:

```sh
docker compose run --rm --entrypoint python pipeline scripts/render_review.py
```

Esse comando gera `artifacts/interface/*.html` sem iniciar Spark. Os arquivos `empty-fixture`, `running-fixture`, `audit-fixture` e `long-fixture` são estados artificiais para testar a apresentação; não documentam novas execuções do pipeline.

A opção `--capture` do script é de desenvolvimento: exige o volume que contém as publicações históricas indicadas nos documentos e inicia Spark apenas para leitura. Ela não modifica o ponteiro de publicação nem executa entregas.

A verificação de navegador é `node scripts/visual-review.cjs`, com Playwright disponível no ambiente. `PLAYWRIGHT_MODULE` permite indicar um módulo instalado fora do repositório; `PLAYWRIGHT_CHANNEL=msedge` seleciona Edge. A biblioteca não é dependência do HTML. Resultados, escopo e limitações ficam em [verificação](verification.md).

Capturas: [execução](images/interface/report.png), [bloqueio](images/interface/blocked.png), [indicadores](images/interface/indicators.png), [arquivos](images/interface/files.png) e [tela estreita](images/interface/report-390.png). As imagens `audit.png`, `empty.png` e `running.png` demonstram as fixtures de apresentação identificadas acima.

## Jornada de leitura conferida em 22/09

No fechamento bloqueado, abra **Execução** e confira S02 ausente, duas de três lojas confirmadas e somente Ingestão medida. Em **Indicadores**, a publicação anterior conserva R$ 64,00. Em **Arquivos**, o ID da publicação e suas versões são distintos dos IDs da tentativa bloqueada. O mesmo percurso mantém R$ 57,00 no snapshot de falha anterior à publicação e R$ 77,00 depois da retomada.

A [revisão de jornadas](evidence/interface-journeys/review.json) conferiu esses três percursos em 1440, 390 e 320 px, incluindo valores por loja, versões e caminhos Delta, navegação por teclado, foco, histórico e rolagem interna das tabelas. Também conferiu ausência de publicação, execução sem resultado final, auditoria incompleta, leitura sem JavaScript, impressão dos três painéis e reflow. Não houve nova execução de lote: os payloads históricos foram renderizados offline pela fonte atual.

Capturas dessa revisão: [bloqueio no celular](images/interface/journey-blocked-390.png), [indicadores após retomada](images/interface/journey-recovered-indicators.png) e [origem da publicação](images/interface/journey-published-files.png). Elas complementam as imagens anteriores; não substituem sua evidência histórica.

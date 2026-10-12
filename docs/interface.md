# Interface do fechamento

O relatório é um snapshot: a geração consulta o manifesto uma vez, lê as versões Delta correspondentes e captura a última tentativa e a última falha disponíveis. Abrir o HTML depois não consulta o pipeline nem atualiza seu estado.

A revisão de UI/UX de 12/10/2026 aproxima a comparação dos totais publicados. Seu diagnóstico, direção e validação ficam em [Qualidade da interface](frontend-quality.md#revisão-de-uiux-em-12102026). A [conferência das imagens](image-review.md) e as capturas v2, v4 e de jornadas abaixo conservam suas fontes e datas anteriores.

## Quatro jornadas de consulta

| Jornada e estado inicial | Ação | Resultado esperado | Consequência de uma leitura errada |
| ----------------------- | ---- | ------------------ | --------------------------------- |
| Conferir o fechamento: publicação inicial ou revisão comparável | Abrir Indicadores e conferir identidade, horário e totais | R$ 64,00 ou R$ 104,00, quatro linhas, sete unidades e três vendas, vinculados à publicação capturada | Atribuir o total à tentativa ou à publicação errada. |
| Investigar uma entrega: tentativa histórica bloqueada, publicação anterior válida | Abrir Execução, ocorrência e cobertura; consultar Indicadores | S02 ausente na tentativa; R$ 64,00 anteriores continuam identificados como publicados | Tratar a entrega incompleta como novo fechamento aprovado. |
| Explicar uma variação: publicação comparável ou sem recorte comum | Abrir perfil, conferir contexto e recorte antes das regras | Aviso de preço nas mesmas datas e lojas; no relatório de 10/01, falta interseção com 01/01 e não há variação relativa aplicável | Interpretar mudança de período como comparação válida ou tomar WARNING por bloqueio. |
| Conferir a origem: publicação, tentativa e baseline identificadas | Abrir Arquivos e versões do perfil; selecionar ou copiar IDs completos | IDs próprios, caminhos, versões Delta e fontes consultáveis, sem alteração do estado | Investigar uma versão física latest ou uma execução diferente da publicação consultada. |

Os três payloads reais da evolução foram relidos pelas versões Delta já registradas, em uma única sessão Spark, sem processar novas entregas. Os valores comerciais usam dados sintéticos da demonstração de 12/10/2026. Os cinco payloads históricos mantêm os horários de setembro; reproduzir sua interface em outubro não muda a data do fechamento.

Os demais casos do corpus são fixtures de apresentação identificadas no HTML: amostra insuficiente, baseline zero, publicação ativa vazia, perfil legado, ausente ou inválido, ausência de publicação, tentativa sem resultado final, auditoria incompleta, IDs longos e campos não informados. A matriz com valores negativos e o nome de métrica desconhecido exercitam o renderer; não ampliam o contrato de vendas ou de leitura do perfil.

Os [recibos da revisão](evidence/uiux-20261012-a12e4a/) e as [capturas antes/depois](images/uiux-20261012-a12e4a/) registram os hashes dos mesmos 22 inputs, fontes e viewports. Edge conferiu os 22 casos e Firefox conferiu comparação, matriz e dinheiro extenso. [Resultados, reprodução e limites](evidence/uiux-20261012-a12e4a/README.md). As provas históricas abaixo permanecem vinculadas às fontes originais.

## Paleta e identidade

Azul petróleo `#245B64` identifica a marca, os links e as ações. Azul escuro `#263248` sustenta texto e faixa de indicadores; branco `#FFFFFF` e cinza claro `#F2F3F5` mantêm a leitura de uma folha de fechamento. Sucesso usa verde `#226348`, aviso usa ocre `#76550E` e bloqueio usa vermelho `#923B35`, sempre com estado escrito. O [README](../README.md#paleta-da-marca) mostra a paleta.

A marca existente acompanha a cor principal por `currentColor`; o favicon, a série diária e o ranking usam a mesma família. A matriz usa os tons `#E6F1F2`, `#C3DCE0`, `#96BDC4`, `#6695A0`, `#3D7380` e `#245B64`, mantendo a escala e os valores. Foco sobre a faixa escura usa branco. A seleção da matriz combina bordas internas clara e escura para permanecer visível em todos os tons. Source Sans 3, marca e licenças locais permanecem no HTML offline.

## Navegação

**Execução** começa pela decisão da última tentativa. Quando falta S02.csv, o título informa o bloqueio, a linha seguinte identifica arquivo e loja, e **Conferir pendência** leva o foco à ocorrência. **Como retomar** explica a reposição dos bytes originais ou a criação de outro lote, conforme o caso. A publicação anterior fica em uma faixa neutra, com sua própria identidade.

A ocorrência principal reúne causa e procedimento. A ausência de entrega da mesma loja fica em **Ocorrências relacionadas**, preservando o registro sem repetir o mesmo bloqueio na leitura inicial. Código, severidade e mensagem original permanecem no contexto técnico. A cobertura está visível por loja; contadores e tempos ficam em detalhes separados: zero erros em linhas recebidas não comprova que todas as lojas entregaram.

As etapas medidas formam uma lista de tempos. Cada etapa abre sua explicação e seu tempo exato, sem repetir um painel para a seleção. O tempo indica duração; a aprovação vem do resultado registrado. As ocorrências conservam código, severidade e contexto de loja, arquivo e linha quando registrados. Cobertura e contadores mantêm a diferença entre zero, indisponível e não avaliado.

**Indicadores** contém os números da publicação vigente, com sua identidade, horário e janela comercial. A comparação aparece junto desses totais, antes da matriz e dos gráficos. Contexto, recorte e disponibilidade da baseline precedem as regras. A regra com aviso abre a leitura; anterior, atual, diferença e motivo ficam disponíveis sem percorrer a tabela completa. Distribuições, lote recebido, versões e tabela das regras permanecem em detalhes nativos.

Depois da comparação, a matriz loja × dia, a série diária e o ranking mantêm suas tabelas exatas. Em desktop, série e ranking ficam lado a lado; no mobile, a ordem é Matriz → Série → Ranking. O gráfico acompanha o calendário e interrompe a linha entre datas sem observação. Setas percorrem a matriz com uma parada de Tab; o valor selecionado leva à linha exata. Zero é uma célula marcada com 0; ausência recebe traço e hachura. Períodos amplos ou dispersos usam a tabela, sem materializar uma grade enorme. Totais consideram o conjunto inteiro; avisos identificam o limite de exibição de 366 dias, 20 produtos e 500 linhas.

**Arquivos** permite consultar e copiar os IDs completos. As versões e os caminhos Delta vêm do manifesto; fontes bronze e hashes de catálogo/calendário permanecem associados ao lote de origem.

Com JavaScript, a navegação seleciona um painel e conserva âncoras e histórico do navegador. Sem JavaScript, os três painéis aparecem em sequência e os detalhes nativos continuam disponíveis. Nenhuma biblioteca externa, fonte remota ou API é necessária. Source Sans 3 é embutida no HTML com sua licença OFL; a marca SVG é original e local.

## Estados que não podem se confundir

- Tentativa bloqueada ou falha antes da publicação: a publicação anterior continua identificada, se existir; sem publicação, os indicadores ficam indisponíveis.
- Publicação concluída com falha no registro final: o fechamento permanece disponível, com aviso de auditoria incompleta. Duração e contadores ausentes não viram zero.
- Sem mudança: a tentativa preserva a publicação vigente.
- Última falha anterior: fica separada da última tentativa e acessível como ocorrência histórica.
- Execução sem resultado final: reflete o registro consultado, sem sugerir acompanhamento ao vivo.

## Capturas e reprodução

As capturas históricas v4 reutilizam os dados sintéticos da [demo histórica](evidence/round-2/demo.json) e do [experimento histórico de volume](evidence/benchmark.json). Os payloads foram extraídos por versão na revisão inicial e reutilizados offline naquela composição; o replay visual não executa lotes, leitura Spark ou benchmark. A integração separada do leitor vazio é descrita no guia de qualidade. Os JSONs em [payloads](evidence/interface/payloads) identificam a fonte e seu SHA-256, além dos dados efetivamente usados.

Para renderizar esses payloads novamente, depois do setup:

```sh
docker compose run --rm --entrypoint python pipeline scripts/render_review.py
```

Esse comando gera `artifacts/interface/*.html` sem iniciar Spark. Os arquivos `empty-fixture`, `running-fixture`, `audit-fixture` e `long-fixture` são estados artificiais para testar a apresentação; não documentam novas execuções do pipeline.

A opção `--capture` do script é de desenvolvimento: exige o volume que contém as publicações históricas indicadas nos documentos e inicia Spark apenas para leitura. Ela não modifica o ponteiro de publicação nem executa entregas.

A verificação de navegador é `node scripts/visual-review.cjs`, com Playwright disponível no ambiente. `PLAYWRIGHT_MODULE` permite indicar um módulo instalado fora do repositório; `PLAYWRIGHT_CHANNEL=msedge` seleciona Edge. A biblioteca não é dependência do HTML. Resultados, escopo e limitações ficam em [verificação](verification.md).

Layout da revisão v4 anterior, com dados históricos: [execução](images/interface-v4/report.png), [bloqueio](images/interface-v4/blocked.png), [indicadores](images/interface-v4/indicators.png), [arquivos](images/interface-v4/files.png) e [tela estreita](images/interface-v4/report-390.png). Na conferência de 22/09/2026, essas cinco imagens coincidiram byte a byte com a captura da fonte v4 examinada naquela data. Elas não representam a composição de UI/UX de outubro. As imagens `audit.png`, `empty.png` e `running.png` demonstram fixtures de apresentação, não novas execuções. [Conferência e limites](image-review.md), [evidência v4 original](evidence/interface-v4/review-manifest.json).

## Revisão anterior de jornadas em 22/09

No fechamento bloqueado, abra **Execução** e confira S02 ausente, duas de três lojas confirmadas e somente Ingestão medida. Em **Indicadores**, a publicação anterior conserva R$ 64,00. Em **Arquivos**, o ID da publicação e suas versões são distintos dos IDs da tentativa bloqueada. O mesmo percurso mantém R$ 57,00 no snapshot de falha anterior à publicação e R$ 77,00 depois da retomada.

A [revisão de jornadas](evidence/interface-journeys/review.json) conferiu esses três percursos em 1440, 390 e 320 px, incluindo valores por loja, versões e caminhos Delta, navegação por teclado, foco, histórico e rolagem interna das tabelas. Também conferiu ausência de publicação, execução sem resultado final, auditoria incompleta, leitura sem JavaScript, impressão dos três painéis e reflow. Não houve nova execução de lote: os payloads históricos foram renderizados offline pela fonte daquela revisão.

Capturas dessa revisão: [bloqueio no celular](images/interface/journey-blocked-390.png), [indicadores após retomada](images/interface/journey-recovered-indicators.png) e [origem da publicação](images/interface/journey-published-files.png). Elas complementam as imagens anteriores; não substituem sua evidência histórica.

## Refinamento anterior da apresentação em 22/09 (v2)

A composição v2 usou navegação horizontal, diagnóstico no eixo principal e uma lista secundária de medições. Em telas estreitas, os painéis ocupam a mesma largura; títulos longos deixam o sinal de expansão em sua própria coluna. A borda de severidade pertence à ocorrência inteira, inclusive com o registro técnico aberto. A tipografia distingue decisão, conteúdo e metadados; valores não recebem animação. Hover e foco usam transições de 180 ms, removidas com `prefers-reduced-motion`.

[Revisão do navegador](evidence/interface-v2/visual-review.json), [bloqueio com detalhes em desktop](images/interface-v2/blocked-expanded-1366.png), [o mesmo estado em 390 px](images/interface-v2/blocked-expanded-390.png) e [erros em registros](images/interface-v2/quality-mobile.png). A impressão mostra os três painéis e o conteúdo dos detalhes; a captura verifica CSS de impressão, sem certificar paginação de PDF. As provas anteriores e suas imagens continuam preservadas.

## Limpeza de regras sem consumidores

Foram removidos dois seletores que não correspondiam ao HTML gerado e uma variável CSS sem uso. A composição e as capturas permanecem as mesmas. O [registro da limpeza](evidence/interface-v2/cleanup.json) descreve o delta e as verificações estáticas; as provas anteriores não foram reexecutadas nem substituídas.

# Interface do fechamento

O relatório é um snapshot: a geração consulta o manifesto uma vez, lê as versões Delta correspondentes e captura a última tentativa e a última falha disponíveis. Abrir o HTML depois não consulta o pipeline nem atualiza seu estado.

A navegação tem cinco áreas: Visão geral, Lojas, O que mudou, Qualidade e Arquivos. Um fechamento publicado abre em Visão geral. Bloqueio, falha técnica, execução sem resultado final ou auditoria incompleta abrem em Qualidade.

## Onde consultar

| Área | Conteúdo |
| ---- | -------- |
| Visão geral | Totais publicados, receita diária, ranking de lojas e participação dos produtos |
| Lojas | Matriz de receita por loja e dia e tabela exata |
| O que mudou | Valores anterior e atual, recorte equivalente e estado da comparação |
| Qualidade | Decisão da tentativa, pendências, cobertura, contadores e etapas medidas |
| Arquivos | IDs completos, fontes, hashes e versões Delta da publicação |

No desktop, a navegação fica na lateral. Em telas estreitas, os links ficam acima do conteúdo. Âncoras conservam o histórico do navegador e revelam o detalhe que contém o destino. Sem JavaScript, as cinco áreas aparecem em sequência com seus detalhes nativos. Fonte, marca e scripts são locais; o HTML funciona offline.

## Ler os gráficos

A receita diária usa colunas com eixo que inclui zero. Um único dia produz uma coluna; datas sem observação deixam lacunas. O resumo identifica a maior receita registrada no recorte exibido quando há mais de um dia. Valores negativos conservam o sinal. **Ver valores** abre a tabela de datas e receitas.

O ranking agrega a receita por loja nas linhas recebidas pelo relatório e mostra até seis lojas. A participação usa a soma de todas as lojas com receita completa nesse input, inclusive as que ficaram fora das seis barras. Por isso, os percentuais exibidos podem somar menos de 100%. A legenda informa quantas lojas aparecem; um input truncado é identificado como recorte parcial. Uma loja com receita ausente fica fora do ranking, e valores negativos desabilitam a participação percentual.

O mix mostra até cinco produtos. Quando há mais, o segmento **Demais produtos exibidos** soma os restantes do input. A participação é em unidades conhecidas dos produtos desse recorte. A tabela conserva cada produto e seus valores. Unidades ausentes ficam indefinidas; zero registrado e participação indisponível têm mensagens próprias.

A matriz em Lojas mantém o valor exato de cada célula e o acesso à linha correspondente. Setas percorrem a matriz com uma parada de Tab. Zero é marcado com 0; ausência recebe traço e hachura. Períodos amplos ou dispersos usam a tabela. Limites de apresentação são 366 dias, 20 produtos e 500 linhas na tabela de loja/dia; os cartões de totais usam o período completo.

## Comparar publicações

O que mudou mostra barras para anterior e atual, com valores decimais preservados. O recorte equivalente fica junto das regras; períodos completos, IDs, razões, limiares e tabelas permanecem em detalhes recolhidos.

Quantidade média usa unidades por linha ativa. Preço médio por unidade usa a receita bruta dividida pelas unidades, antes dos descontos. A distribuição de preço nos detalhes calcula a média por linha, portanto seus valores podem diferir da regra ponderada por unidades.

A comparação depende das mesmas datas e lojas. Sem interseção, não há variação equivalente; com baseline zero, a diferença absoluta existe e a variação relativa fica indefinida. Amostra insuficiente, perfil legado, ausente ou inválido mantêm seu estado explícito. Um aviso de perfil acompanha uma publicação disponível e não bloqueia o fechamento.

## Conferir qualidade e origem

Qualidade começa pela decisão da última tentativa. **Conferir pendência** leva à ocorrência principal, que reúne a causa e o procedimento de retomada. Ocorrências relacionadas conservam os registros; código, severidade e contexto técnico ficam nos detalhes. Cobertura está visível por loja, enquanto contadores e tempos têm seus próprios detalhes. Zero erros nas linhas recebidas não comprova que todas as lojas entregaram.

Arquivos permite selecionar ou copiar IDs completos e conferir caminhos, versões Delta, fontes bronze e hashes das referências. A publicação, a tentativa e a baseline têm identidades próprias.

## Recursos locais

Source Sans 3 é embutida no HTML com sua licença OFL. Marca, favicon e scripts também são locais; a consulta ao snapshot não depende de serviços externos.

## Estados que não podem se confundir

- Tentativa bloqueada ou falha antes da publicação: a publicação anterior continua identificada, se existir; sem publicação, os indicadores ficam indisponíveis.
- Publicação concluída com falha no registro final: o fechamento permanece disponível, com aviso de auditoria incompleta. Duração e contadores ausentes não viram zero.
- Sem mudança: a tentativa preserva a publicação vigente.
- Última falha anterior: fica separada da última tentativa e acessível como ocorrência histórica.
- Execução sem resultado final: reflete o registro consultado, sem sugerir acompanhamento ao vivo.

## Gerar e consultar o HTML

Depois do setup, informe o diretório Linux da demo e capture a publicação por suas versões Delta:

```powershell
docker compose run --rm pipeline --data-dir <diretorio> report --output /app/artifacts/inspected-report.html
```

Abra o HTML em `artifacts`. O servidor local opcional usa `scripts/pipeline.ps1 serve`; os comandos de publicação e recuperação estão no [guia da demo](demo.md).

## Reproduzir fixtures de apresentação

Os JSONs em `tests/fixtures/reports/` permitem renderizar os estados sem iniciar Spark ou executar entregas. A partir da raiz, use Python 3.11+ e Node 22+. Instale as ferramentas de navegador pelo lock do projeto antes da primeira execução:

```sh
npm ci --prefix tools/browser
npm run install:browser --prefix tools/browser
```

No shell POSIX:

```sh
PYTHONPATH=src python scripts/render_report_fixtures.py tests/fixtures/reports artifacts/report-fixtures/html
DASHBOARD_INPUTS=tests/fixtures/reports node scripts/dashboard-review.cjs after artifacts/report-fixtures/html artifacts/report-fixtures/qa
```

No PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python scripts/render_report_fixtures.py tests/fixtures/reports artifacts/report-fixtures/html
$env:DASHBOARD_INPUTS = 'tests/fixtures/reports'
node scripts/dashboard-review.cjs after artifacts/report-fixtures/html artifacts/report-fixtures/qa
```

O harness resolve Playwright e `@axe-core/playwright` de `tools/browser/`. `PLAYWRIGHT_MODULE`, `AXE_MODULE` e `PLAYWRIGHT_CHANNEL` permitem selecionar outros módulos ou um navegador local. Use um diretório de saída novo para cada execução. A [documentação das verificações](frontend-quality.md#reproduzir-a-apresentação) inclui instalação das bibliotecas de sistema no Linux e os limites do teste.

As verificações automáticas cobrem os casos executados. Zoom nativo e leitura com tecnologia assistiva exigem conferência própria; reflow por largura e espaçamento CSS não substituem essas avaliações.

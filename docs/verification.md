# Verificação e reprodução

Arquivos em artifacts são gerados localmente e não são pré-requisitos do clone. O comando `scripts/verify_problem.py` grava os resultados em `artifacts/`; passos em [demo.md](demo.md).

## Runtime

| Componente | Versão fixada |
| --- | --- |
| Python | 3.11.16 |
| Java | Temurin 17.0.20+8 |
| PySpark / Spark | 3.5.9 |
| Delta Lake / Scala | 3.2.1 / 2.12 |
| pytest | 9.0.3 |

A [matriz oficial Delta](https://docs.delta.io/releases/) admite Delta 3.2.x com Spark 3.5.x. A [manutenção Spark 3.5.9](https://spark.apache.org/releases/spark-release-3-5-9.html) preserva essa linha. Os digests das imagens oficiais estão no Dockerfile; dependências Python têm versão e SHA-256 em requirements.lock e requirements-build.lock. O build instala ferramentas de construção antes dos pacotes, sem resolução isolada implícita. Os dois jars Delta são conferidos por SHA-256 em scripts/download_jars.py.

Base e dependências fixadas não significam imagem reproduzível byte a byte: apt instala procps a partir dos repositórios Debian durante o build. O resultado da consulta OSV de 16 pins Python está em [dependencies.json](evidence/dependencies.json); isso não é uma varredura das bibliotecas transitivas JVM nem dos pacotes do sistema operacional.

## Comandos verificáveis

Na raiz do clone, sem instalação de Python ou Java no Windows:

~~~powershell
.\scripts\pipeline.ps1 setup
.\scripts\pipeline.ps1 check
.\scripts\pipeline.ps1 test -q --junitxml=/app/artifacts/tests.xml
.\scripts\pipeline.ps1 demo
docker compose run --rm --entrypoint python pipeline scripts/benchmark.py
.\scripts\pipeline.ps1 serve
~~~

No Linux, substitua o wrapper por sh scripts/pipeline.sh. Setup baixa as dependências; os demais comandos do batch usam network_mode:none. Relatórios abrem diretamente como HTML ou no servidor opcional de 127.0.0.1:3103. O serviço não entrega o volume Delta pela rede.

O Compose limita o batch a 3 GiB e 2 CPUs, Spark local[2], driver 1 GiB, duas partições de shuffle/snapshot. Testes e demos executam um runtime Spark por vez. Dados, cache, temporários e logs ficam no volume Linux; o bind do código e as exportações pequenas ficam no diretório do clone. O workflow usa o mesmo runtime e permissões contents:read.

## O que os testes verificam

- Totais manuais independentes por loja e produto: R$ 44,00 + R$ 20,00 = R$ 64,00; sete unidades, quatro linhas e três vendas.
- Revisão crescente, revisão antiga, duplicata dentro/entre arquivos, conflitos com histórico elegível, mudança de dia, cancelamento e reativação.
- CSV/JSON estritos, schema, hashes, contagem, referências, zero explícito, loja ausente, multiviolação e preservação física da entrada.
- Mesmo batch não pode mudar manifesto, catálogo ou calendário; reposição dos bytes esperados continua possível.
- Falhas após ingestão, gold e antes do ponteiro; candidato não se torna autoridade; leitura antiga permanece estável.
- Lock entre processos e liberação após término; falha de auditoria depois do commit não desfaz publicação visível.
- Argumentos inválidos e saída de geração ocupada recusados antes do Spark; dados extremos de contrato e formato sem exceções de conversão.
- Publicação sem vendas com ticket indisponível; venda gratuita com ticket zero; mesmo sale_id em origens distintas; datas históricas e limite monetário gravados em Delta.
- HTML sem execução de conteúdo de origem; ausência de publicação distinta de zero; indicadores associados a versões fixadas; gráfico com tabela equivalente.
- Aliases de caminho com .. não permitem copiar a entrada recursivamente para dentro dela mesma.

## Verificação visual opcional

O HTML não depende de Node. Para repetir apenas as capturas, instale Playwright em um diretório de ferramentas ignorado:

~~~powershell
npm install --prefix .visual-tools --no-save --package-lock=false playwright@1.62.1
.\.visual-tools\node_modules\.bin\playwright.cmd install chromium
$env:NODE_PATH = (Join-Path (Get-Location) '.visual-tools/node_modules')
node scripts/visual-review.cjs
~~~

Execute primeiro demo e benchmark. O script verifica largura de página em 1440, 1366, 768, 390 e 320 CSS px, foco de âncoras, expansão por teclado, 30 totais diários equivalentes ao gráfico e 360 linhas loja/dia preservadas em detalhe. Também mede corpo de 16 px, navegação de 15 px e células de dados de 14 px; valida ausência de semântica falsa de tabs. A cópia é testada com Clipboard API interceptada e fallback indisponível, sem escrever no clipboard real. Uma sessão sem JavaScript verifica leitura e expansão nativa. As capturas ficam em docs/images/round-2 e as medições em docs/evidence/round-2. O próprio comando demo também produz quality-review.html com uma tentativa real inválida sem publicação anterior.

## Limites

Não há VACUUM automático, backup ou política de retenção. Fabric ainda não foi executado. Duração e memória estão registradas por execução.

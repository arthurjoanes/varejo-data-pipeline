# Atualização do runtime — 22/09/2026

O batch passou de Spark 3.5.9/Delta 3.2.1 para Spark 4.2.0/Delta 4.4.0, Scala 2.13 e Java 17. A combinação é publicada nas [notas oficiais Delta 4.4.0](https://github.com/delta-io/delta/releases/tag/v4.4.0). O artefato Java usado é `delta-spark_4.2_2.13`, específico para Spark 4.2. Nenhuma tabela é convertida ou apagada pelo build. A fixture de migração também foi exercitada: Spark 3.5.9/Delta 3.2.1 publicou R$ 64,00; o runtime novo releu esses arquivos, respondeu NO_CHANGE ao reenvio e publicou a correção de R$ 77,00, preservando leitura por versão anterior de R$ 64,00 e gerando HTML. [Resultado](evidence/runtime-migration.json) · [script reproduzível em duas fases](../scripts/verify_runtime_migration.py).

## O que mudou fisicamente

- Os locks Python e os dois JARs Delta foram atualizados com SHA-256.
- `runtime-jars.lock.json` fixa 45 substituições completas: famílias Netty 4.2.18, Jackson 2.21.7, Log4j 2.25.5, Vert.x 4.5.34, Parquet 1.18.1 e LZ4 1.11.3. Artefatos da mesma família são atualizados juntos. Os metadados Maven permanecem dentro dos JARs.
- 22 artefatos opcionais foram removidos integralmente: cliente REPL remoto Spark Connect, Derby, Hive/Thrift e shell JLine. Nome, hash anterior e motivo constam no mesmo lock. O build falha se encontrar um binário de origem diferente do esperado.
- A aplicação continua com Spark SQL, catálogo em memória, Delta por caminho, CLI Python, relatório, reprocessamento, cancelamento e recuperação. Hive metastore, servidor Thrift, Spark Connect REPL, Derby SQL/LDAP e shell Telnet não fazem parte desse runtime. Não use esta imagem como distribuição Spark genérica.
- A ingestão ganhou orçamento configurável por arquivo/JSON/entrega e número de arquivos, contado durante a cópia. A evidência parcial é identificada explicitamente; veja [contrato](data-contract.md).

## Resultado do scan

Trivy 0.74.0, sistema operacional + Python + JVM, sem filtro de severidade, exclusões de achados ou `ignore-unfixed`:

| Imagem | Ocorrências JVM | IDs distintos | Critical | High | Medium | Low |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Anterior, Spark 3.5.9 | 145 | 111 | 5 | 61 | 69 | 10 |
| Candidata Spark 4.2.0 sem os ajustes JVM | 94 | 54 | 3 | 35 | 56 | 0 |
| Revisão anterior, antes dos rebuilds | 18 | 18 | 0 | 7 | 11 | 0 |
| Imagem integrada atual, após os três rebuilds | 1 | 1 | 0 | 0 | 1 | 0 |

As três primeiras linhas são históricas: o runtime Spark 3.5.9 foi medido em 21/09, e os candidatos Spark 4.2.0, em 22/09. A [comparação histórica dos scans](evidence/runtime-upgrade-scans.json), a [verificação anterior de hashes/remoções](evidence/runtime-jar-verification.json) e a [triagem antes dos rebuilds](evidence/security-triage-before-rebuild.json) preservam esse estado, quando os 18 achados ainda estavam presentes.

A última linha corresponde ao [scan integral atual](evidence/security-scan.json), concluído em 22/09/2026 às 03:52:56 UTC, da imagem `sha256:3cc3b95c1985397f1a3601a1c66531180ba0b8ef8738e5901dd400e805c719f3`. Foram inventariados 441 pacotes JVM, 52 pacotes Alpine e 28 pacotes Python; OS e Python tiveram zero achados. O JSON do scan tem SHA-256 `407549ed22a8e964d587edd6359562989c1c9cc84d769228eeeb839da8d47143`.

A [triagem atual](evidence/security-triage.json) acompanha individualmente os **18 achados originais**: 15 tratados por atualização de dependências, dois pela remoção integral de Jetty 9 do Hadoop e um pelo backport oficial de Commons Lang. Dezessete não aparecem no scan atual. **CVE-2025-48924/MEDIUM permanece visível** porque Commons Lang conserva os metadados 2.6; sua correção é sustentada pelo patch, hash e regressão comparativa descritos abaixo. Não é um resultado de zero achados, nem prova de ausência de vulnerabilidades.

A suíte completa Spark/Delta passou na mesma imagem: **188 testes, zero falhas, erros ou testes ignorados**, em 1.003,963 segundos no JUnit. O executor registrou 1.005,949 segundos e confirmou que as fontes não mudaram durante a execução. [Resultado e hashes do snapshot](evidence/jvm-rebuild-full-suite.json) · [JUnit integral](evidence/jvm-rebuild-tests.xml). Essa prova corresponde à fonte **anterior à integração da UI `899c9f368aab100f0f41c1327161992149cfd2a3`**. Os 182 unitários, a demo e a migração da fonte combinada passaram; o CI integral do commit publicado é acompanhado separadamente. Não se atribuem os 188 testes à fonte posterior.

## Reconstruções identificadas

As cópias sombreadas exigiram trabalhar nos próprios artefatos que incorporam as classes. [Spark core](../vendor/spark-core/README.md) foi recompilado a partir da distribuição fonte fixada, mantendo o shading oficial e os 14 módulos Jetty em 12.1.13. As 2.981 classes Spark e os metadados 4.2.0 foram preservados. Passaram três regressões de URI e três casos HTTP em memória; o original reproduziu os três problemas de URI. A reconstrução limpa, sem rede e com os 1.630 materiais Maven conferidos, produziu o mesmo JAR.

O [assembly Hadoop](../vendor/hadoop-runtime/README.md) usa Jackson 2.18.11, JLine 3.30.17 e Commons Configuration 2.15.1, com suas dependências e ferramentas fixadas. Preserva a API Hadoop 3.5.0 original. Quatro descritores JLine precisaram acompanhar a relocação dos nomes de classe; foram verificados em um terminal local. Oito checks incluem arquivo local/SequenceFile, JSON, rejeição de número fragmentado, hierarquia de configuração, terminal e ausência de Jetty. A repetição limpa com os 666 materiais Maven fixados, sem rede, reproduziu o hash aprovado.

Esses checks não reproduzem todos os CVEs. O teste Jackson confirma rejeição eventual do número fragmentado, mas não distingue rejeição durante os dígitos de rejeição no terminador. O teste de configuração usa um mapa autocíclico no mecanismo interno, sem parsing de YAML textual. O terminal JLine não exercita os ataques Telnet. No Spark, os três casos HTTP usam HTTP/1.1 e não reproduzem o CVE-2026-6790 de HTTP/2 e HTTP/3. A [matriz de evidências](evidence/security-triage.json) separa esses limites das versões corrigidas, hashes e regressões efetivamente comparadas.

Os artefatos completos Jetty 9 e websocket de Hadoop ficam fora desse assembly. O perfil local de arquivos/Delta já era o produto suportado antes da revisão. A imagem não oferece clientes/servidores HTTP Hadoop nem se apresenta como uma distribuição Hadoop genérica. Não foram removidos apenas metadados ou classes selecionadas para alterar o scanner. Para CVE-2024-6763, a correção agora é essa remoção integral: desabilitar a UI não cobria o uso direto de `HttpURI` como utilitário. O Jetty do Spark permanece no inventário, atualizado. [Escopo e isolamento](security.md).

[Commons Lang 2.6](../vendor/commons-lang/README.md) recebe o patch oficial Apache `904afa78`, aplicado ao tag `LANG_2_6`. A afirmação anterior de inexistência de correção compatível na linha 2.x estava incorreta. Somente `ClassUtils.class` é recompilada; as APIs públicas/protegidas e os outros 154 membros permanecem. Os 44 casos de `ClassUtils` passam, com controle negativo da regressão no original. A suíte completa de 1.974 casos continua com 29 problemas de compatibilidade/expectativas no Java 17, presentes também no original; não é apresentada como aprovada. O scanner mantém CVE-2025-48924/MEDIUM por versão porque os metadados 2.6 permanecem íntegros.

Os três artefatos têm nome e manifesto próprios. Nenhum é apresentado como um release oficial Apache. O instalador confere os hashes dos originais, candidatos e proveniências antes de substituir qualquer componente; erros no último candidato deixam os três originais intactos. Fontes upstream, compiladores e caches ficam nos stages de build. O runtime recebe os JARs e as proveniências verificadas. As receitas foram validadas em Linux/amd64; outra arquitetura/toolchain exige revisão dos hashes.

O primeiro build exige mais tempo, rede e espaço, pois recompila componentes. A manutenção dessas receitas é responsabilidade do projeto: cada atualização demanda revisar locks, repetir controles dirigidos e validar Spark/Delta, migração, demo, recuperação e scan integral. O CI reprova qualquer HIGH/CRITICAL, sem as exceções anteriores de perfil. O scan da imagem combinada passou esse gate e manteve o MEDIUM documentado. A suíte integrada passou em 188 casos antes de incorporar a interface. Depois da integração, passaram 182 unitários, demo completa e migração da imagem anterior, com publicação e leitura por versão preservadas. O CI repete a suíte integral do commit publicado. [Provas da fonte combinada](evidence/jvm-rebuild.json).

## Operação e verificação

`setup` recompila o runtime e roda o smoke; `check` e `test` repetem as verificações do repositório. O scan e o gate de segurança continuam no CI. A comparação de hashes também garante que uma mudança futura do pacote PySpark interrompa os overrides em vez de misturar famílias silenciosamente.

Faça backup do volume de estado antes de atualizar uma instalação existente. A alternativa mais simples para esta demonstração é um volume novo e reprocessamento das entradas originais. Não faça downgrade sobre arquivos escritos pelo runtime novo sem verificar os protocolos/features Delta e restaurar uma cópia consistente. Os testes de estado novo e de recuperação não equivalem a uma certificação de migração de qualquer tabela externa.

As evidências históricas constam em [verificação](verification.md), incluindo a suíte de 166 testes e o reteste focal após a preservação da referência aprovada em tentativas bloqueadas por orçamento. Esses resultados precedem os três rebuilds; os 188 testes vinculados acima validam as reconstruções no snapshot pré-UI. O [ensaio funcional de 30 mil linhas](evidence/remediation-benchmark.json) manteve os totais esperados; sua execução concorrente não permite comparar desempenho diretamente. As medições de benchmark e capturas de 21/09 também continuam históricas.

## Quando retirar uma reconstrução própria

O objetivo de manutenção é voltar a um artefato oficial compatível quando ele carregar as correções necessárias. A existência de uma versão mais nova, isoladamente, não basta para substituir os JARs: é preciso conferir compatibilidade Spark/Delta/Hadoop, classes sombreadas e o perfil local suportado.

Para cada candidata, registrar origem e hash; comparar inventário/classes/APIs contra o contrato do componente; repetir suas regressões dirigidas e os controles negativos pertinentes; depois validar leitura das publicações anteriores, demo, migração, recuperação e suíte Spark/Delta. O scan integral precisa conservar os metadados e os achados, com o gate HIGH/CRITICAL existente. Somente após esses resultados o lock e a receita podem adotar a candidata e retirar a substituição local correspondente.

Essa é uma condição de evolução, não uma nova release encontrada ou validada nesta rodada. A manutenção custa revisão de dependências, build, armazenamento e testes; não há tempo de atualização comercial medido. O MEDIUM por versão de Commons Lang continua visível no scan identificado acima, sustentado separadamente por patch e regressão. “Zero HIGH/CRITICAL” não significa “zero vulnerabilidades”.

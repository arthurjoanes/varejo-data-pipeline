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
| Runtime local ajustado | 18 | 18 | 0 | 7 | 11 | 0 |

O resultado anterior é a evidência de 21/09; os dois posteriores foram medidos na revisão de 22/09. OS e Python tiveram zero achados na imagem final. São resultados do banco público do scanner, não prova de ausência de vulnerabilidades. A [comparação dos scans e imagens](evidence/runtime-upgrade-scans.json) e a [verificação de hashes/remoções](evidence/runtime-jar-verification.json) registram as alterações físicas. O [scan integral](evidence/security-scan.json) registra a identidade da imagem e os pacotes; a [triagem](evidence/security-triage.json) lista **todos os 18 residuais**, individualmente, com condições de exposição. Os 18 não foram corrigidos.

## Pendências de upstream

Hadoop 3.5.0 incorpora Jackson 2.18.6, Jetty HTTP 9.4.58, JLine 3.9 e Commons Configuration 2.10.1 em um JAR sombreado. Spark core 4.2.0 incorpora Jetty 12.1.8. Substituir o Jackson/Jetty externo no classpath não altera essas classes internas; por isso os achados continuam visíveis no scan. Commons Lang 2.6 também permanece e não tem uma atualização compatível na linha 2.x.

O [POM Hadoop 3.5.0](https://github.com/apache/hadoop/blob/rel/release-3.5.0/hadoop-client-modules/hadoop-client-runtime/pom.xml) permite reconstruir o runtime por Maven shading; o módulo não contém fonte própria. Um fork poderia atualizar Jackson/JLine e refazer as relocações. Isso exigiria fixar todo o grafo de dependências/plugins, preservar serviços e licenças, identificar o artefato customizado e repetir testes de compatibilidade Hadoop/Spark/Delta. Não foi produzido nem validado um fork nesta entrega.

Além disso, o [Maven Central de Jetty HTTP](https://repo.maven.apache.org/maven2/org/eclipse/jetty/jetty-http/maven-metadata.xml) consultado em 22/09 ainda lista 9.4.58 como último artefato público da linha 9.4. As versões 9.4.60/9.4.63 mencionadas por advisories não estavam disponíveis nesse repositório. Atualizar a cópia sombreada para Jetty 10/12 envolve compatibilidade de API, não somente uma troca de versão. Jetty 12.1.10 existe para corrigir o componente incorporado em Spark core, mas requer reconstrução do artefato Spark que o incorpora ou novo release upstream.

Enquanto essas pendências existirem, o modo suportado permanece local e sem rede, sem UI/serviços Java, com somente CSV/JSON de entrada e tabelas Delta produzidas pelo próprio pipeline. Isso retira as precondições identificadas na triagem; **não corrige as bibliotecas**. Expor UI, cluster, serviços, plugins, configuração ou tabelas de terceiros invalida a avaliação. Não transportar esta lista de exceções para outro perfil de implantação.

## Operação e verificação

`setup` recompila o runtime e roda o smoke; `check` e `test` repetem as verificações do repositório. O scan e o gate de segurança continuam no CI. A comparação de hashes também garante que uma mudança futura do pacote PySpark interrompa os overrides em vez de misturar famílias silenciosamente.

Faça backup do volume de estado antes de atualizar uma instalação existente. A alternativa mais simples para esta demonstração é um volume novo e reprocessamento das entradas originais. Não faça downgrade sobre arquivos escritos pelo runtime novo sem verificar os protocolos/features Delta e restaurar uma cópia consistente. Os testes de estado novo e de recuperação não equivalem a uma certificação de migração de qualquer tabela externa.

As evidências de testes da revisão constam em [verificação](verification.md), incluindo a suíte de 166 testes e o reteste focal após a preservação da referência aprovada em tentativas bloqueadas por orçamento. O [novo ensaio funcional de 30 mil linhas](evidence/remediation-benchmark.json) manteve os totais esperados; sua execução concorrente não permite comparar desempenho diretamente. As medições de benchmark e capturas de 21/09 continuam históricas.

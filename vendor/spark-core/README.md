# Spark core 4.2.0 com Jetty 12.1.13

Este candidato recompila o módulo core da distribuição fonte oficial, fixada por SHA-256/SHA-512. As dependências Spark irmãs continuam sendo os artefatos oficiais 4.2.0 publicados. A propriedade Maven `jetty.version` atualiza a família inteira antes da compilação e do shading oficial para `org.sparkproject.jetty`; nenhum pacote ou metadado é retirado para reduzir achados.

O JAR final conserva os metadados Maven `org.apache.spark:spark-core_2.13:4.2.0`, versões reais Jetty e licenças upstream. O nome `spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar` e `META-INF/varejo-spark-core.json` identificam o build modificado. Ele não é um release oficial Apache.

`provenance.json` fixa fonte, commit, builder e dependência. `build.sh` reduz somente a reserva de memória do compilador e fixa `project.build.outputTimestamp`/`SOURCE_DATE_EPOCH`. A substituição de `build/spark-build-info` declara commit/tag upstream com sufixo local e o timestamp da fonte para reprodução; o campo `date` não representa a hora real da execução. Tempos reais de teste/build pertencem ao relatório externo.

`inputs.sha256` fixa 1.630 materiais Maven (JARs, POMs e executável protoc), cerca de 1,15 GB de dependências de compilação. `fetch-inputs.sh` baixa esses caminhos de Maven Central e verifica cada SHA-256 antes de executar Maven em modo offline. A lista inclui dependências de compilação e testes do módulo upstream, não apenas o conteúdo do JAR final. O runtime recebe somente o resultado do shading e conserva o inventário Maven das dependências incorporadas. O builder é Maven 3.9.15 com Temurin 17.0.19+10; o compilador Scala é 2.13.18.

Para construir localmente, com Docker e Python no host:

```sh
python scripts/build_spark_core.py
python scripts/verify_spark_core.py
```

O builder usa uma CPU, até 4 GiB de memória, heap Scala 2 GiB e heap Maven 768 MiB. Fontes, classes e cache Maven ficam no volume `fix-varejo-spark-build`; saídas ficam em `artifacts/spark-core`. Não executar uma suíte Spark geral em paralelo à compilação.

O Dockerfile desta pasta fornece o estágio reutilizável para CI. Na raiz:

```sh
docker build -f vendor/spark-core/Dockerfile --target artifacts --output type=local,dest=artifacts/spark-core .
```

O estágio final de runtime deve copiar somente o JAR aprovado e a evidência necessária, nunca o cache Maven ou o diretório de fontes. O instalador global confere hashes do JAR original/candidato e do manifesto interno.

`verify_spark_core.py` verifica versões Maven internas, bytes alterados em classes ligadas aos quatro advisories anteriores e preservação de identidade/licenças. O teste Java carrega essas classes sombreadas do próprio JAR. Três regressões de canonicalização de URI falham no original e devem passar no candidato; também há três casos HTTP por conector em memória, sem socket de rede. Esses checks não substituem os 166 testes Spark/Delta, migração, demo, recuperação nem scan integral da imagem combinada.

A comparação de bytecode inclui `HttpConnection$RequestHandler`, onde mudou a validação de requisições; a classe externa `HttpConnection` permaneceu idêntica. Alteração de hash é evidência de substituição do código e não demonstra, isoladamente, a correção de todos os advisories. A conclusão depende das versões upstream, dos testes direcionados e da validação integrada.

Fontes: [Spark build](https://spark.apache.org/docs/4.2.0/building-spark.html), [POM core/shading 4.2.0](https://github.com/apache/spark/blob/v4.2.0/core/pom.xml), [regressão URI upstream](https://github.com/jetty/jetty.project/commit/82969c77f6da46e27008b10b3c14840cd31db084), [advisories Jetty](https://jetty.org/security.html).

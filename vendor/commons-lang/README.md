# Backport restrito de Commons Lang 2.6

Este componente aplica o [patch oficial Apache 904afa78](https://github.com/apache/commons-lang/commit/904afa78cc58e2897f47eeac0781c3ba6f95b5e6) para CVE-2025-48924 ao código de `LANG_2_6`. A alteração troca a recursão de `ClassUtils.getClass` por iteração. O [lock de fontes](source-lock.json) fixa o commit, os downloads, o patch, os arquivos Java resultantes e os hashes do compilador. O [script de build](../../scripts/build_commons_lang.py) verifica esses dados antes de produzir o JAR.

Somente `ClassUtils.class` é recompilada, com JDK 17.0.20 e `javac --release 8`. Os outros 154 membros do JAR original conservam seus bytes comprimidos e metadados ZIP; somente os offsets necessários da tabela central mudam. A comparação de API pública/protegida por `javap` permanece idêntica. A classe recompilada requer Java 8 ou posterior; a execução foi verificada no Java 17 usado pelo projeto. Os hashes do toolchain foram verificados em `linux/amd64`; outra arquitetura exige validação e revisão explícita desses hashes.

O resultado se chama `commons-lang-2.6-retail-classutils-v1.jar`. Mantém `commons-lang:commons-lang:2.6`, manifesto upstream, `LICENSE.txt` e `NOTICE.txt`; acrescenta `META-INF/varejo-commons-lang.json` e uma cópia do patch oficial. A identificação própria não se apresenta como uma versão nova do Apache. As entradas novas usam data fixa, e os horários reais de execução ficam apenas nos relatórios externos.

- SHA-256 do JAR original: `50f11b09f877c294d56f24463f47d28f929cf5044f648661c0f0cfbae9a2f49c`.
- SHA-256 do JAR corrigido: `126c5be1f710dd2f4336867e24df864ecb1896bde68e9204a9ba31c3f58dbf05`.
- SHA-256 de `META-INF/varejo-commons-lang.json`: `cde6bb4d78ceddc14812dcee5a8064815b45366cdfcff1dc3fd9fae515dbe07d`.

## Verificação e limites

Em 22/09/2026, os 44 casos upstream de `ClassUtils` passaram no JAR corrigido. Eles incluem nomes de classes internas, primitivos, arrays de uma e duas dimensões, argumentos inválidos e classes inexistentes. No JAR original, a mesma classe de testes tem somente o erro `StackOverflowError` da regressão oficial acrescentada pelo patch. Essa regressão também foi executada isoladamente como controle negativo. Ela já integra os 44 casos e não aumenta a contagem de cobertura.

A suíte upstream completa **não passou** no JDK 17. Com ordem alfabética estável dos testes, o original executou 1.974 casos e apresentou 21 falhas de asserção e 9 erros; o corrigido executou os mesmos 1.974 casos e apresentou 21 falhas e 8 erros. Os 29 problemas remanescentes coincidem exatamente por caso/tipo com o original: incluem reflexão bloqueada pelos módulos do JDK, expectativas antigas de representação de objetos, carregadores de classes e formatação de datas. O único problema eliminado é a regressão oficial. Isso sustenta o backport restrito, sem afirmar compatibilidade total dessa biblioteca antiga com Java 17.

Uma primeira execução sem ordenar a reflexão do JUnit apresentou 37 problemas no original e 35 no corrigido, com diferenças adicionais dependentes da ordem. Seus relatórios foram preservados. O executor atual ordena os mesmos testes antes de executar os dois JARs; não altera as asserções, não adiciona exclusões e não marca falhas como aprovadas. Compila os 149 arquivos de teste upstream e mantém somente as duas exclusões do POM original, `EntitiesPerformanceTest` e `RandomUtilsFreqTest`. O pacote legado chamado `enum` exige sintaxe anterior ao Java 5: os testes usam ECJ 3.33.0 fixado, com source/target 1.4. A classe de produção continua sendo compilada pelo `javac` fixado.

O modo padrão do build exige os controles negativos, os 44 casos de `ClassUtils`, identidade das fontes, preservação do arquivo e API igual. Registra `validation_scope=patched-class-and-official-regression` e `upstream_full_suite_status=not-run`. O modo `--upstream-suite` executa adicionalmente todos os casos e retorna código 1 diante de qualquer falha; na prova registrada retornou `requires-review` e `upstream_full_suite_status=failed`. O [resumo de evidência](verification.json) identifica os resultados, hashes dos relatórios completos e tentativas anteriores. Os XML e logs completos são gerados em cada execução no diretório de saída.

Compilações independentes produziram o mesmo SHA-256 acima. O scan comparativo Trivy ainda reconhece ambos os JARs como `commons-lang:commons-lang@2.6` e aponta CVE-2025-48924, severidade MEDIUM, nos dois. O backport corrige o mecanismo comprovado pela regressão; a correspondência por versão do scanner permanece registrada. Esta receita não altera a base de vulnerabilidades, não esconde coordenadas Maven e não afirma zero achados. O gate e os testes de integração do pipeline continuam sendo verificações separadas da biblioteca.

## Reprodução

No Dockerfile principal, o stage `commons-lang-build` instala o JDK fixado, copia esta receita e executa diretamente Python. Não usa Docker dentro do container. Seu contrato de saída é `/output/commons-lang/commons-lang-2.6-retail-classutils-v1.jar`; apenas o JAR e sua proveniência verificada precisam chegar ao runtime.

Para repetir isoladamente, a partir da raiz do repositório em um shell POSIX:

```sh
docker build -f vendor/commons-lang/Builder.Dockerfile -t commons-lang-builder .
mkdir -p artifacts/commons-lang/downloads artifacts/commons-lang/output
docker run --rm --cpus 1 --memory 1g --pids-limit 128 \
  --cap-drop ALL --security-opt no-new-privileges --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=512m \
  --mount "type=bind,src=$PWD,dst=/work,readonly" \
  --mount "type=bind,src=$PWD/artifacts/commons-lang/downloads,dst=/downloads" \
  --mount "type=bind,src=$PWD/artifacts/commons-lang/output,dst=/output/commons-lang" \
  commons-lang-builder python /work/scripts/build_commons_lang.py \
  --downloads /downloads --output /output/commons-lang --fetch
```

Após preencher o diretório de downloads, retire `--fetch` e acrescente `--network none` ao `docker run` para repetir offline. Para a suíte histórica completa, acrescente `--upstream-suite` ao comando Python e use outro diretório de saída para preservar a primeira execução. O código de saída não zero nesse perfil deve ser mantido e analisado, junto dos XML, em vez de convertido em aprovação. Os limites de CPU/memória se aplicam à execução acima; o Dockerfile principal depende também dos limites configurados no builder Docker.

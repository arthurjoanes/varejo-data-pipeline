# Assembly Hadoop para o batch local

Este diretório reconstrói `org.apache.hadoop:hadoop-client-runtime:3.5.0` a partir dos artefatos publicados e das regras de shading oficiais. Não recompila nem modifica `hadoop-client-api:3.5.0`. O resultado tem nome `hadoop-client-runtime-3.5.0-retail-security.1.jar`, manifesto `META-INF/varejo-hadoop-runtime.json` e título que identifica o build customizado; **não é um release Apache**. O projeto de assembly usa `local.retail.pipeline:hadoop-client-runtime-retail:3.5.0-security.1`. Os metadados Maven originais Hadoop 3.5.0 também são preservados no JAR para manter a identificação de origem por ferramentas de inventário. Usar as coordenadas Hadoop no projeto principal faria o filtro upstream `org.apache.hadoop:*` excluir também seus recursos e metadados.

Mudanças no assembly:

- Jackson core/databind/annotations/JAXB/JAX-RS 2.18.11, JLine 3.30.17 e Commons Configuration 2.15.1.
- Os quatro descritores `META-INF/jline/providers/*` recebem os nomes de classes relocados; `jline-resource-relocations.json` registra os hashes antes/depois. Esse formato novo não é tratado pelo transformer padrão de serviços. Os descritores completos e seus avisos permanecem.
- Commons Lang3 3.20.0, Text 1.15.0 e IO 2.22.0 acompanham o grafo de Configuration. O grafo de build declara Logging 1.3.6, mas a regra upstream mantém logging externo; o produto usa a ponte JCL/SLF4J do Spark.
- Os artefatos completos `org.eclipse.jetty:*` e `org.eclipse.jetty.websocket:*` ficam fora do assembly. Essa imagem é destinada ao batch local. Clientes/servidores HTTP Hadoop e outras capacidades que dependem de Jetty não são cobertos por este perfil.
- As demais regras oficiais de exclusão, filtros, relocação e combinação de serviços são preservadas. Os metadados Maven dos componentes incluídos permanecem. Licenças/avisos de todo o grafo resolvido também são preservados individualmente em `META-INF/third-party`; esse diretório pode listar componentes que foram excluídos fisicamente do assembly.

Os POMs e documentos upstream estão em `upstream/`, com URLs e hashes em `upstream-sources.json`. `pom.xml` é a receita revisável derivada desses arquivos. `inputs.lock.json` fixa por SHA-256 os artefatos e POMs Maven, inclusive plugins. O build usa uma imagem Maven/JDK por digest, `SOURCE_DATE_EPOCH=1790035200` e `project.build.outputTimestamp=2026-09-22T00:00:00Z`.

Na raiz do repositório:

```powershell
python scripts/hadoop_build_runtime.py
python scripts/hadoop_verify_runtime.py
```

O primeiro comando obtém arquivos ausentes pelas URLs fixas, confere os hashes e roda Maven com rede desligada. `--bootstrap-lock` existe somente para regeneração explícita e revisão do lock após mudanças. Não é usado na reprodução de uma entrega já fixada.

Para integração em Docker, copie este diretório para um stage baseado na imagem de `toolchain.json` e execute `HADOOP_OUT=/out/hadoop-runtime sh build-stage.sh`. Execute em seguida `HADOOP_OUT=/out/hadoop-runtime sh test-stage.sh` para compilar e executar os oito checks do componente; as quatro dependências externas são verificadas por `probe-inputs.sha256`, com reaproveitamento do cache Maven. `probe-definition.sha256` fixa separadamente o teste, sem mudar a receita do JAR; uma falha interrompe o stage e o resultado fica em `component-stage.log`. Esse caminho usa somente shell, curl, SHA-256 e Maven; não depende de Python nem de Docker dentro do stage. `definition.sha256` protege os recursos congelados, `inputs.sha256` protege os downloads Maven e `output.sha256` exige o JAR revisado byte a byte. Os recursos de origem/licença preservam seus bytes por `.gitattributes`, inclusive quando o checkout é feito no Windows.

O segundo comando verifica inventário, presença dos avisos/licenças/serviços, ausência de componentes Jetty e executa um teste Java limitado a 512 MiB, sem rede. Ele cobre arquivo local/SequenceFile, JSON comum, limite numérico Jackson com entrada fragmentada, hierarquia YAML normal/cíclica e terminal JLine local. A hierarquia YAML é exercitada diretamente, sem adicionar SnakeYAML ao produto. As bibliotecas externas do probe têm hashes iguais às da imagem Spark auditada e são fixadas em `probe-dependencies.lock.json`.

Os resultados ficam em `artifacts/hadoop-runtime/out/`: JAR, `manifest.json`, `component-tests.json`, log e árvore de dependências. A aprovação desse componente não substitui os testes completos Spark/Delta, migração, publicação, recuperação e scan da imagem integrada. Nenhum cache Maven, `target/dependency` ou fonte de build deve ser copiado para a imagem de execução.

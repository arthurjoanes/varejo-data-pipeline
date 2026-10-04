# Parquet Jackson 1.18.1 com Jackson 2.22.3

O scan de 03/10/2026 encontrou quatro ocorrências HIGH no Jackson 2.22.2 incorporado ao `parquet-jackson-1.18.1.jar`. As demais cópias Jackson do runtime já estavam em linhas corrigidas. Esta receita reconstrói o módulo completo da fonte Apache Parquet 1.18.1 com `jackson.version` e `jackson-databind.version` em 2.22.3. Conserva a configuração oficial de shading para `shaded.parquet.com.fasterxml.jackson`, inclusive classes de JDKs adicionais e descritores de serviços.

O arquivo resultante tem nome próprio, `parquet-jackson-1.18.1-retail-jackson-2.22.3.jar`, e contém `META-INF/varejo-parquet-jackson.json`. É um build local, identificado separadamente do release Apache. As coordenadas Parquet 1.18.1, as versões reais Jackson, os metadados Maven e as licenças upstream permanecem no JAR. Nenhuma classe ou metadado foi removido para reduzir o resultado do scan.

`provenance.json` fixa fonte, commit, builder e alterações de dependência. `inputs.sha256` fixa os materiais Maven; a receita verifica esses bytes antes de executar Maven offline. O Enforcer do upstream verifica versões Java/Maven, dependências proibidas e imports de JUnit. O timestamp do JAR é fixo para reprodução e não representa o horário real do build. `definition.sha256` verifica a receita, e `output.sha256` confere o resultado. O Dockerfile da raiz executa essa receita e o instalador valida o JAR original, o candidato e a proveniência antes da substituição.

O check Java carrega as classes relocadas do próprio JAR, confere as versões 2.22.3, faz roundtrip JSON e verifica limites de número e profundidade. Esses controles não reproduzem os quatro CVEs; a conclusão também depende das versões corrigidas upstream, do scan integral e das integrações Spark/Delta. O módulo oficial é apenas um agregador de dependências sombreadas e não contém testes Java próprios.

A receita foi validada em Linux/amd64 com Maven 3.9.15 e Temurin 17.0.19+10. Outra arquitetura ou toolchain exige revisar os hashes. A atualização deve voltar a um artefato oficial quando houver uma versão compatível com os componentes corrigidos, após repetir os testes e o scan.

Fontes: [módulo oficial Parquet](https://github.com/apache/parquet-java/tree/apache-parquet-1.18.1/parquet-jackson), [release Jackson 2.22.3](https://github.com/FasterXML/jackson/wiki/Jackson-Release-2.22.3).

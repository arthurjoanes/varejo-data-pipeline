# Segurança do runtime local

O escopo suportado é o batch Docker local com o Compose deste repositório. A entrega contém CSV e três documentos JSON; a leitura oficial usa somente tabelas Delta geradas pelo próprio pipeline. O volume de estado, a configuração do operador e o código precisam permanecer sob controle do operador. Este projeto não é uma sandbox para executar código, abrir tabelas arbitrárias ou receber tráfego de clientes remotos.

## Isolamento

- O batch usa `network_mode: none`, Spark `local[2]`, driver em `127.0.0.1` e UI desabilitada. Não inicia serviços Mesos, ZooKeeper, Hive, Thrift ou Telnet.
- A raiz do container e o código são somente leitura, e novos privilégios são proibidos. O batch mantém somente `DAC_OVERRIDE`, necessária para exportar no bind `artifacts` pertencente ao usuário Linux sem mudar os donos ou permissões no host. As áreas graváveis são o volume `/data` e a pasta `artifacts`; o diretório temporário da JVM é `/data/tmp`. O servidor de relatório remove todas as capabilities.
- O servidor opcional entrega somente `artifacts`, como usuário sem privilégios, na interface `127.0.0.1`. Ele não monta o volume Delta. Não é um servidor público de produção.
- A ingestão recusa links simbólicos, FIFOs, caminhos que escapam da entrada e arquivos inesperados. Os bytes são copiados antes da validação. Arquivos Avro e Parquet enviados como entrega bloqueiam o lote; não são interpretados por esses leitores.
- JSON externo é processado por Python. Spark recebe NDJSON produzido por `json.dumps`, com schema explícito; campos do CSV são dados escapados. As configurações não habilitam desserialização polimórfica Java. Parquet e logs Delta lidos pelo pipeline foram escritos pelo próprio runtime.

Os testes de contrato verificam arquivos externos, symlinks, FIFO, caminhos e JSON profundamente aninhado. O smoke real verifica master local, driver loopback, ausência de UI, catálogo em memória, MERGE e leitura por versão. A suíte também cobre escape do conteúdo no HTML. Esses controles reduzem a superfície de entrada; não corrigem bibliotecas de terceiros.

## Dependências e builds identificados

A revisão anterior passou de 145 para 18 ocorrências JVM, incluindo sete HIGH. Os resultados continuam no histórico Git. A revisão atual reconstrói as cópias incorporadas aos JARs: Spark core usa Jetty 12.1.13; o assembly Hadoop atualiza Jackson, JLine e Commons Configuration e exclui os artefatos completos Jetty 9/websocket. Esses componentes HTTP não pertenciam ao batch local originalmente suportado. Os testes de publicação, correção, cancelamento e recuperação continuam obrigatórios. Os builds têm nomes próprios, versões reais, licenças e proveniência; não são releases oficiais Apache. [Decisões e receitas](runtime-upgrade.md).

Commons Lang 2.6 recebe o [patch oficial Apache 904afa78](https://github.com/apache/commons-lang/commit/904afa78cc58e2897f47eeac0781c3ba6f95b5e6) para trocar a recursão de `ClassUtils.getClass` por iteração. A frase da revisão anterior sobre inexistência de correção compatível na linha 2.x estava incorreta: esse patch se aplica a `LANG_2_6`. Mantêm-se as coordenadas `commons-lang:commons-lang:2.6`, com nome e manifesto próprios para identificar o backport.

O scan comparativo continua apontando CVE-2025-48924/MEDIUM por versão no original e no corrigido. O achado bruto permanece visível. Os 44 testes upstream de `ClassUtils` passam no corrigido; no original, a regressão oficial lança `StackOverflowError`. A API pública/protegida e os outros 154 membros do JAR foram preservados. A suíte histórica completa **não passou**: entre 1.974 casos, ainda existem 21 falhas e oito erros no Java 17, iguais aos do original além da regressão corrigida. O comando dessa suíte continua retornando erro. [Receita e limites do backport](../vendor/commons-lang/README.md).

O [scan integral da imagem](evidence/security-scan.json) `sha256:3cc3b95c1985397f1a3601a1c66531180ba0b8ef8738e5901dd400e805c719f3`, em 22/09/2026, identificou 441 pacotes JVM e manteve somente CVE-2025-48924/MEDIUM no JAR corrigido de Commons Lang: zero HIGH/CRITICAL. Os 52 pacotes Alpine e 28 Python tiveram zero achados. Trivy 0.74.0 usou a base de vulnerabilidades atualizada em 21/09/2026 às 19:11 UTC; não houve filtro de severidade, exclusão de achados ou `ignore-unfixed`. Os 18 achados anteriores estão preservados na [triagem histórica](evidence/security-triage-before-rebuild.json), com [tratamento individual e limites de cobertura](evidence/security-triage.json). A suíte dessa imagem passou em 188 testes, incluindo 15 integrações Spark/Delta, sem falhas ou casos pulados; a fonte ficou inalterada durante a execução. [Resultado e hashes da fonte](evidence/jvm-rebuild-full-suite.json) · [JUnit](evidence/jvm-rebuild-tests.xml).

## Orçamento de entrada

Por padrão: 1 MiB por JSON, 64 MiB por arquivo, 256 MiB por tentativa e 1.000 arquivos. Os bytes são contados enquanto são copiados, e JSON é limitado antes de parsing. `snapshot.json` marca a evidência parcial e a tentativa é bloqueada sem mudar a publicação anterior. [Configuração, códigos e retenção](data-contract.md). O orçamento por tentativa não é quota acumulada do disco.

## Reprodução e CI

Depois de `setup`, execute na raiz em Linux:

```sh
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD/artifacts:/out" \
  aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969 \
  image --scanners vuln --ignorefile /dev/null --format json \
  --output /out/security-scan.json pf-varejo-data:local
python3 scripts/check_image_scan.py artifacts/security-scan.json
```

O CI preserva o relatório integral e reprova qualquer HIGH/CRITICAL, inclusive conhecido ou sem atualização disponível. Não aceita exceções baseadas no perfil local. Uma ocorrência MEDIUM permanece visível mesmo quando não dispara esse limiar; o backport de Commons Lang é comprovado separadamente por hash e regressão. O workflow separado de Gitleaks verifica segredos no histórico Git.

A configuração Gitleaks mantém todas as regras padrão e uma exceção por caminho **e valor exatos**: o fingerprint público de assinatura das versões Python, presente no histórico/ambiente da imagem em `docs/evidence/security-scan.json`. O valor foi conferido com o [Dockerfile oficial Python 3.11/Alpine](https://github.com/docker-library/python/blob/master/3.11/alpine3.24/Dockerfile); não é uma chave privada nem uma credencial. Outro valor nesse arquivo ou o mesmo valor em outro caminho continua sendo verificado. Essa exceção não altera a varredura de vulnerabilidades Trivy.

A cobertura depende das bases públicas do scanner. O aviso de Trivy sobre a versão Alpine não constar na tabela de EOL não impede a análise de pacotes; ele não é uma prova de suporte nem de ausência de vulnerabilidades desconhecidas.

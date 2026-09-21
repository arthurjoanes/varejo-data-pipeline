# Segurança do runtime local

O escopo suportado é o batch Docker local com o Compose deste repositório. A entrega contém CSV e três documentos JSON; a leitura oficial usa somente tabelas Delta geradas pelo próprio pipeline. O volume de estado, a configuração do operador e o código precisam permanecer sob controle do operador. Este projeto não é uma sandbox para executar código, abrir tabelas arbitrárias ou receber tráfego de clientes remotos.

## Isolamento

- O batch usa `network_mode: none`, Spark `local[2]`, driver em `127.0.0.1` e UI desabilitada. Não inicia serviços Mesos, ZooKeeper, Hive, Thrift ou Telnet.
- A raiz do container e o código são somente leitura, e novos privilégios são proibidos. O batch mantém somente `DAC_OVERRIDE`, necessária para exportar no bind `artifacts` pertencente ao usuário Linux sem mudar os donos ou permissões no host. As áreas graváveis são o volume `/data` e a pasta `artifacts`; o diretório temporário da JVM é `/data/tmp`. O servidor de relatório remove todas as capabilities.
- O servidor opcional entrega somente `artifacts`, como usuário sem privilégios, na interface `127.0.0.1`. Ele não monta o volume Delta. Não é um servidor público de produção.
- A ingestão recusa links simbólicos, FIFOs, caminhos que escapam da entrada e arquivos inesperados. Os bytes são copiados antes da validação. Arquivos Avro e Parquet enviados como entrega bloqueiam o lote; não são interpretados por esses leitores.
- JSON externo é processado por Python. Spark recebe NDJSON produzido por `json.dumps`, com schema explícito; campos do CSV são dados escapados. As configurações não habilitam desserialização polimórfica Java. Parquet e logs Delta lidos pelo pipeline foram escritos pelo próprio runtime.

Os testes de contrato verificam arquivos externos, symlinks, FIFO, caminhos e JSON profundamente aninhado. O smoke real verifica master local, driver loopback, ausência de UI, catálogo em memória, MERGE e leitura por versão. A suíte também cobre escape do conteúdo no HTML. Esses controles reduzem a superfície de entrada; não corrigem bibliotecas de terceiros.

## Achados de dependências

A varredura de 21/09/2026 com Trivy 0.74.0 incluiu sistema operacional, Python e todos os JARs, sem `ignore-unfixed`, filtro de severidade ou arquivo de exclusão. A base foi atualizada para Alpine 3.24 e OpenJDK 17.0.20; pip e ensurepip foram removidos depois da instalação com hashes. Resultado e identidade da imagem estão em [security-scan.json](evidence/security-scan.json).

O runtime Spark 3.5.9 ainda distribui bibliotecas Java com vulnerabilidades conhecidas, inclusive cópias embutidas em Hadoop e Spark. Não há alegação de zero vulnerabilidades. Os achados HIGH e CRITICAL foram examinados por pacote, versão, caminho do JAR e identificador em [security-triage.json](evidence/security-triage.json). A conclusão de ausência de caminho de exploração no batch suportado é uma inferência da leitura e dos testes de restrição; não é uma reprodução de exploit de cada CVE.

| Família | Precondição ausente no fluxo suportado |
| --- | --- |
| Netty e Jetty | Entrada HTTP, HTTP/2, SPDY ou TLS de clientes externos; UI e rede do batch estão desabilitadas. |
| Mesos, ZooKeeper, Derby, Thrift e Telnet | Serviços distribuídos, servidor SQL/Thrift, LDAP ou terminal remoto; o processo é local e usa catálogo em memória. |
| Jackson, Gson, JSON-Smart e BeanUtils | Desserialização Java arbitrária, seleção de classes ou binding reflexivo de propriedades da entrega. |
| Avro, Aircompressor e LZ4 | Schemas Avro e blocos comprimidos produzidos por terceiros; somente CSV/JSON são aceitos como entrega. |
| Protobuf, Nimbus JWT, OkHttp e DNSJava | Protocolos remotos, tokens ou respostas de serviços externos processados pelo batch. |
| Commons IO | XML fornecido pelo remetente para `XmlStreamReader`. |

Essa análise deixa de valer se forem adicionados notebooks, cluster remoto, leitura de tabelas externas, serviços de rede, plugins ou alterações diretas do volume por terceiros. Migrar Spark/Delta ou substituir JARs sombreados exige testes de compatibilidade próprios; remover metadados para silenciar o scanner não é uma correção.

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

O CI preserva o relatório integral e bloqueia HIGH/CRITICAL novos ou cuja versão, caminho, pacote ou severidade tenha mudado. A triagem reconhece somente as entradas Java listadas nominalmente; não aceita vulnerabilidades do sistema ou de Python. Mudanças nas condições de isolamento exigem nova análise, mesmo se os identificadores de CVE permanecerem iguais. O workflow separado de Gitleaks verifica segredos no histórico Git.

A cobertura depende das bases públicas do scanner. O aviso de Trivy sobre a versão Alpine não constar na tabela de EOL não impede a análise de pacotes; ele não é uma prova de suporte nem de ausência de vulnerabilidades desconhecidas.

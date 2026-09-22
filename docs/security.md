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

A varredura de 22/09/2026 com Trivy 0.74.0 incluiu sistema operacional, Python e todos os JARs presentes, sem `ignore-unfixed`, filtro de severidade ou exclusão de achados. A imagem usa Alpine 3.24, OpenJDK 17.0.20, Spark 4.2.0 e Delta 4.4.0. O resultado integral e a identidade da imagem estão em [security-scan.json](evidence/security-scan.json).

O upgrade, 45 substituições coordenadas de artefatos completos e a remoção de 22 componentes opcionais reduziram 145 ocorrências JVM (5 críticas, 61 altas) para **18 ocorrências/18 IDs: zero críticas, 7 altas e 11 médias**. OS e Python não tiveram achados no scanner. Os binários removidos e os hashes anteriores/novos constam em `runtime-jars.lock.json`; nenhum metadado de vulnerabilidade foi apagado para esconder bibliotecas presentes. [Escopo exato e decisões do upgrade](runtime-upgrade.md).

**Os 18 achados residuais não estão corrigidos.** A [triagem individual](evidence/security-triage.json) inclui versão, caminho, identificador, severidade, referência e a precondição ausente no batch suportado. A conclusão de ausência desse caminho é uma inferência de arquitetura e configuração, apoiada pelos testes de isolamento; não é reprodução de cada CVE.

| Componente residual | Precondição ausente e limite da mitigação |
| --- | --- |
| Jackson sombreado em Hadoop | Parser assíncrono remoto ou binding Java com polimorfismo, endereços, views/records controlados pelo remetente. JSON de entrada é limitado e lido por Python; estado Delta não vem de terceiros. |
| Jetty sombreado em Hadoop/Spark | Servidor HTTP, Digest, proxy ou UI acessível. Rede do batch e UI Spark estão desabilitadas; servidor opcional de relatório é Python, separado e em loopback. |
| JLine sombreado em Hadoop | Servidor Telnet remoto. Nenhum terminal/serviço Telnet é iniciado. |
| Commons Configuration sombreado em Hadoop | YAML externo cíclico. O contrato aceita somente CSV/JSON; configuração do runtime pertence ao operador. |
| Commons Lang 2.6 | Nome arbitrário de classe passado a `ClassUtils.getClass`. A entrega não possui esse recurso. Não existe correção compatível na linha 2.x; migrar para Lang 3 requer atualizar consumidores. |

Essa análise deixa de valer com notebooks, cluster remoto, leitura de tabelas externas, serviços de rede, plugins ou alterações diretas do volume por terceiros. Hadoop 3.5.0 e Spark core 4.2.0 ainda incorporam classes vulneráveis sombreadas; um JAR externo corrigido não as substitui. Um rebuild customizado demanda identificação, dependências fixadas e validação upstream adicional; essa pendência está registrada no documento de atualização, sem alegação de correção.

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

O CI preserva o relatório integral e bloqueia HIGH/CRITICAL novos ou cuja versão, caminho, pacote ou severidade tenha mudado. A triagem reconhece somente as entradas Java listadas nominalmente; não aceita vulnerabilidades do sistema ou de Python. Mudanças nas condições de isolamento exigem nova análise, mesmo se os identificadores de CVE permanecerem iguais. O workflow separado de Gitleaks verifica segredos no histórico Git.

A cobertura depende das bases públicas do scanner. O aviso de Trivy sobre a versão Alpine não constar na tabela de EOL não impede a análise de pacotes; ele não é uma prova de suporte nem de ausência de vulnerabilidades desconhecidas.

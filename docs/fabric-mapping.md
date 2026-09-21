# Proposta para Microsoft Fabric

Proposta de adaptação para Fabric, ainda não executada.

## O que seria reaproveitado

O contrato de entrada, geração sintética, hashes canônicos, regras de qualidade, projeção de revisões, expressões Spark SQL, fórmulas gold e fixtures com resultados manuais são candidatos a reutilização. Um notebook pequeno ou job chamaria o pacote; ele não passaria a ser a fonte principal das regras. O Fabric permite executar notebooks com Spark e acioná-los por atividades de pipeline. [Documentação de notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook).

| Responsabilidade local | Adaptação proposta |
|---|---|
| CSV, manifestos e cópias físicas no volume | Área de arquivos do Lakehouse/OneLake com entrada imutável por lote e tentativa. |
| Bronze, histórico, silver e gold Delta por caminho | Tabelas/áreas Delta identificadas explicitamente, com separação entre candidatos e dados liberados. |
| Configuração de catálogo e janelas | Configuração versionada por ambiente, carregada antes da entrega; expectativa continua independente do manifesto. |
| Processo CLI local | Job ou notebook fino, com parâmetros de lote, entrada e ambiente, acionado por pipeline. |
| `attempt.json` e logs estruturados | Registro durável de execução, ligado aos identificadores da orquestração. |
| HTML e `explain` por snapshot | Consumidores adaptados à publicação escolhida; Power BI exige um contrato de exposição próprio. |

Delta é o formato principal de tabelas do Lakehouse e oferece integração com Spark. Isso reduz mudanças no modelo de dados, mas não torna configurações, versões de bibliotecas ou publicação automaticamente portáveis. [Lakehouse e tabelas Delta](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-and-delta-tables).

## O que precisa ser redesenhado

### Coordenação de escritores

`fcntl.flock` protege processos que compartilham o filesystem Linux local. Ele não é uma estratégia de exclusão distribuída entre jobs Fabric. A orquestração deve limitar concorrência, mas também precisa tratar disparos manuais, retries e escritores externos. A proposta exige uma autoridade única para publicação e um mecanismo transacional de posse ou atualização condicional a validar no ambiente escolhido.

### Publicação de múltiplas tabelas

`os.replace` e `fsync` no mesmo volume são decisões locais; não devem ser reproduzidos como se o rename de um arquivo em OneLake herdasse as mesmas garantias. Também não há transação única automática entre várias tabelas de um Lakehouse. A documentação distingue Lakehouse e Warehouse justamente nessa capacidade. [Visão geral de Lakehouse](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-overview).

Uma alternativa a investigar é gravar saídas imutáveis por `publication_id` e manter um registro de controle transacional que selecione a publicação completa. O leitor captura o identificador uma vez e filtra todas as saídas por ele. Isso depende de testar atualização concorrente do registro, isolamento da leitura, retenção e recuperação. Outro desenho seria promover o conjunto a uma camada de consumo que possua transação adequada.

### Power BI e endpoint SQL

Um consumidor que consulta tabelas correntes por nome pode enxergar candidatos ou momentos distintos de atualização. Ele não herda o `versionAsOf` do relatório Python. Antes de conectar um modelo semântico, seria necessário definir uma publicação materializada/filtrada e um processo de refresh que mantenha o recorte consistente. A exposição de uma tabela no endpoint SQL não demonstra atomicidade entre todas as tabelas usadas pelo modelo.

### Runtime e armazenamento

O Fabric gerencia o runtime Spark; a imagem Docker local não é enviada como se fosse seu runtime nativo. Será necessário escolher uma versão suportada, verificar precisão decimal, timezone, formatos de timestamp, recursos Delta e repetir smoke/integridade. Caminhos relativos dependem do Lakehouse padrão do notebook, portanto a configuração deverá explicitar o destino para evitar leituras em ambientes incorretos. [Explorar Lakehouse com notebook](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-notebook-explore).

### Permissões e retenção

Operadores precisam de diagnóstico e quarentena; consumidores precisam apenas das publicações aprovadas. Contas, identidades, acesso entre workspaces e retenção serão definidos por ambiente. Uma rotina de manutenção não pode remover versões/arquivos referenciados por leitores ativos ou publicações retidas.

## Testes para a migração

1. Executar smoke e fixtures manuais com o runtime Fabric selecionado e dependências registradas.
2. Repetir correção de data, cancelamento tardio, lote incompleto, conflito e reentrega.
3. Demonstrar exclusão entre dois escritores reais, incluindo execução manual concorrente com a orquestração.
4. Injetar falhas depois de cada saída e antes/depois da promoção; os consumidores precisam continuar vendo um conjunto completo.
5. Consultar simultaneamente durante a promoção por todos os canais oficiais, incluindo modelo semântico se existir.
6. Validar retenção e recuperação sem depender de arquivos locais da sessão Spark.
7. Medir custos, duração, limites de capacidade e consumo do workload real antes de otimizar recomputação ou ampliar escala.

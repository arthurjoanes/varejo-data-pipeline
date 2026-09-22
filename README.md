# Varejo Data Pipeline

Desenvolvi este laboratório para conferir entregas e revisões de vendas antes de publicar um fechamento. Ele é útil para quem precisa explicar **se o total está completo, quais revisões foram aceitas e a qual publicação cada indicador pertence**.

Uma soma correta pode esconder uma loja ausente ou contar uma venda duas vezes. Por isso, o relatório separa a tentativa mais recente da publicação que continua disponível quando uma entrega é bloqueada.

![Página principal do Varejo Data Pipeline](docs/readme/home.png)

*Página principal da demonstração.*

[Na prática](#na-prática) · [Implementação](#implementação) · [Executar e verificar](#executar-e-verificar) · [Limites e manutenção](#limites-e-manutenção)

<p><img src="docs/readme/uso.svg" width="800" height="8" alt=""></p>

## Na prática

![Recorte da cobertura: S01 confirmada, S02 pendente e S03 com zero movimento confirmado](docs/images/current-20260922/coverage-focus.png)

O recorte usa o renderer atual e um snapshot histórico sintético de entrega ausente: duas de três lojas confirmadas, com S02 pendente. É um replay visual, sem nova execução do pipeline.

Na demonstração editorial separada, o remetente omite S02, mas o calendário aprovado pelo operador ainda espera três lojas. O lote é bloqueado e os **R$ 64,00 anteriores permanecem publicados**. As leituras Delta e as asserções do [caso executado](docs/demo.md#demonstração-editorial-executada) verificam a preservação dos dados. [Captura completa dessa execução, com bytes preservados](docs/images/editorial-20260922/coverage-blocked.png). A [conferência das imagens](docs/image-review.md) distingue o layout atual dos dados históricos e das provas de versões anteriores.

**Exemplo curto:** A1 tem dois itens: `2 × R$ 10 − R$ 1 = R$ 19` e `1 × R$ 5 = R$ 5`. Mover somente o primeiro para o dia seguinte conserva os R$ 24, mas faz A1 aparecer em dois dias. Implementei uma validação que bloqueia essa revisão parcial. Mover os dois itens juntos conserva uma venda e leva os R$ 24 ao dia correto. [Entrada, resultado, código e limite](docs/problem-solution.md#exemplo-uma-soma-certa-com-a-contagem-errada).

Os dados são sintéticos. Este é um laboratório local, sem clientes, operação comercial ou capacidade de produção demonstrada.

### Como uma falha aparece para quem consulta

A demonstração pequena usa quatro itens: `19 + 5 + 20 + 20 = R$ 64`, sete unidades e três vendas. Depois da correção integral de data, a receita continua em R$ 64. Uma nova revisão aumenta a quantidade do primeiro item de dois para três: o esperado passa a **R$ 74**.

| Situação executada | O que precisa permanecer verdadeiro |
| --- | --- |
| S02 ausente | Bloqueio e publicação anterior de R$ 64 |
| Só um item de A1 muda de dia | `SALE_DATE_CONFLICT`; a soma não basta para aprovar |
| Os dois itens de A1 mudam juntos | R$ 64 e três vendas; a revisão 99 rejeitada não bloqueia a revisão 2 válida |
| Processo falha entre as duas tabelas finais | Versões físicas mais recentes de R$ 74/R$ 64; leitores oficiais continuam em R$ 64/R$ 64 |
| Retomada e repetição | Publicação de R$ 74; repetir retorna `NO_CHANGE`, com a mesma publicação |

A [demonstração executada](docs/demo.md#demonstração-editorial-executada) reúne capturas junto dos casos, comandos, dados de origem e resultados. A [explicação das decisões](docs/decisoes-tecnicas.md) liga cada mecanismo ao código, à verificação e ao custo da escolha. A demo histórica de cancelamento/reativação, que termina em R$ 77, permanece separada.

<p><img src="docs/readme/implementacao.svg" width="800" height="8" alt=""></p>

## Implementação

### O que eu implementei

- Separei o cadastro e o calendário aprovados dos arquivos enviados pelas lojas. A origem não pode reduzir a expectativa para fazer uma entrega incompleta parecer válida.
- Implementei identidade por item e revisão, bloqueio de conflito, cancelamento e reativação. Repetir uma operação sem repetir seu efeito é a **idempotência** verificada na jornada.
- Organizei a publicação em um manifesto com versões fixas das tabelas. Um candidato interrompido pode existir fisicamente sem aparecer nos indicadores oficiais.
- Construí a CLI, a rastreabilidade por arquivo/linha/revisão, os cenários verificáveis e o relatório HTML offline. Configurei Spark e Delta para processamento e armazenamento versionado; essas ferramentas são dependências do projeto, não produtos de minha autoria.
- Acrescentei o contrato e a prova de cópia/restauração do estado completo, com recusa de cópia adulterada e destino ocupado. O limite atual é recuperação local no mesmo computador.

### Stack

<p>
  <img src="docs/stack/python.svg" alt="Python" width="72" height="72">
  <img src="docs/stack/apachespark.svg" alt="Apache Spark" width="72" height="72">
  <img src="docs/stack/java.svg" alt="Java" width="72" height="72">
  <img src="docs/stack/docker.svg" alt="Docker" width="72" height="72">
</p>

Python/PySpark processa os lotes e Delta Lake mantém as tabelas versionadas. Java fornece o runtime do Spark; Docker fixa o ambiente. O relatório usa HTML, CSS e JavaScript locais, sem serviço de frontend.

### Como protejo a publicação

Spark calcula o estado dos itens e os dois recortes finais: loja/dia e produto/dia. Delta fornece transações por tabela; gravar ambos em sequência não cria uma transação entre eles. Para este escopo local, escolhi validar o candidato, reconciliar seus totais e só então trocar um **manifesto**, o arquivo que aponta para as versões oficiais.

O leitor captura esse manifesto uma vez e consulta as versões indicadas. Isso impede misturar uma tabela nova com outra antiga se o processo parar entre as gravações. Recalcular a projeção do histórico aceito simplifica correções de data, cancelamentos e retomadas; o custo cresce com esse histórico. [Arquitetura](docs/architecture.md) · [Contrato](docs/data-contract.md) · [Código de publicação](src/retail_pipeline/publication.py).

<p><img src="docs/readme/execucao.svg" width="800" height="8" alt=""></p>

## Executar e verificar

### Executar no Windows

Requer Docker Desktop em modo Linux, Compose v2 e PowerShell. Java e Python do batch ficam na imagem. O primeiro build baixa e compila dependências fixadas, portanto precisa de rede, espaço e tempo; a execução posterior não usa rede.

```powershell
.\scripts\pipeline.ps1 setup
.\scripts\pipeline.ps1 demo
.\scripts\pipeline.ps1 serve
```

Abra [o relatório local](http://localhost:3103/report.html). No Linux, use `sh scripts/pipeline.sh` com os mesmos comandos. `demo` cria um novo estado UUID, sem apagar demos anteriores; seus arquivos exportados em `artifacts/` representam a última execução do comando. Para conservar uma prova com nome próprio, use o [roteiro de verificação](docs/demo.md).

### Ler e verificar o fechamento

- **Execução:** decisão, lote, arquivo/regra, cobertura e próximo destino. Zero movimento confirmado é diferente de ausência de entrega.
- **Indicadores:** identidade e período da publicação, receita, unidades, vendas, ticket, matriz loja/dia e ranking. Valores exatos continuam nas tabelas; ausência não vira zero.
- **Arquivos:** IDs completos, versões Delta, fontes bronze e hashes das referências aprovadas.

O HTML é um snapshot: abrir a página não consulta o pipeline nem acompanha a execução ao vivo. Ele abre como arquivo local, mantém os dados sem JavaScript e inclui a fonte e sua licença. [Interface](docs/interface.md) · [Capturas e qualidade visual](docs/frontend-quality.md).

Para executar o contraexemplo de negócio em estado temporário novo:

```powershell
docker compose run --rm --entrypoint python pipeline scripts/verify_problem.py --thesis-only --output /app/artifacts/thesis
```

Esse comando executa Spark/Delta e verifica os resultados antes de exportar o registro; não é apenas um replay visual. O [registro de verificação](docs/verification.md) distingue esta execução, testes anteriores, CI, medição e scans. O CI do baseline `93d80c0` aprovou 249 testes e registrou zero achados HIGH/CRITICAL; isso não substitui o CI de futuras alterações.

<p><img src="docs/readme/limites.svg" width="800" height="8" alt=""></p>

## Limites e manutenção

### Limites que mantive explícitos

O escritor é único, protegido por lock no filesystem Linux local. Não há transação distribuída, autenticação multiusuário, streaming, cloud provisionada ou estorno parcial. O relatório mostra até 500 linhas, 20 produtos e 366 dias, com totais do conjunto publicado; não é histórico completo de todas as execuções.

Não há limpeza automática de versões Delta. A [prova anterior de restauração](docs/state-recovery.md) recuperou 187 arquivos e três publicações em volume novo, mas não demonstra recuperação fora do computador. A [medição de recomputação](docs/state-recovery.md) é local e separada das fixtures pequenas; não a apresento como capacidade de produção.

Spark 4.2.0 e Delta 4.4.0 têm dependências JVM fixadas por hash e builds locais identificados para componentes específicos. Receitas, correções, licenças e condições de isolamento estão em [segurança](docs/security.md) e [runtime](docs/runtime-upgrade.md). Licença MIT do projeto; licenças de terceiros preservadas.

Ícones da stack: [Devicon — licença MIT](docs/stack/LICENSE.devicon).

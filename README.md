# Varejo Data Pipeline

Fiz um pipeline local de fechamento de vendas com PySpark, Delta Lake e Spark SQL. Ele valida os arquivos e as revisões antes de publicar os indicadores, porque o erro que eu queria evitar é sutil: uma soma certa pode esconder uma loja faltando ou contar a mesma venda em dois dias.

![Relatório de vendas](docs/images/round-2/report.png)

O operador aprova um calendário de lojas esperadas, e eu valido as revisões por inteiro antes de fechar. Falha ou lote bloqueado mantém a publicação anterior. [Problema e solução](docs/problem-solution.md).

## O que garanti

- Recalculo as 30 mil linhas a cada lote. É mais simples de testar correção e recuperação do que aplicar deltas.
- Um lote novo não pode diminuir as lojas esperadas; mudar isso exige estado novo.
- CANCEL guarda o histórico, então uma revisão maior não reativa um item cancelado por engano.
- Erro financeiro ou de cobertura bloqueia o lote inteiro.

Os 150 testes (15 deles de integração com Spark e Delta reais) cobrem falha entre tabelas, retomada sem duplicação e lock entre processos. [Verificação](docs/verification.md).

## Rodar no Windows

Docker Desktop em modo Linux, Compose v2 e PowerShell. Não precisa de Java nem Python no host.

```powershell
.\scripts\pipeline.ps1 setup
.\scripts\pipeline.ps1 demo
.\scripts\pipeline.ps1 serve
```

Abra http://localhost:3103/report.html. No Linux, os comandos estão no [ci.yml](.github/workflows/ci.yml).

## A demo mostra o caso difícil

`demo` roda a sequência num estado isolado: lote válido, repetição, loja ausente, reposição, correção, cancelamento, falha antes de publicar e retomada. As receitas conferidas à mão são 64,00 → 64,00 → 64,00 → 64,00 → 77,00 → 57,00 → 57,00 → 77,00, com assert em cada passo. Comparo `artifacts/report.html`, `blocked-report.html` e `failure-report.html` pra ver a consequência de cada caso. [Roteiro](docs/demo.md).

A CLI devolve 0 para publicação ou lote sem mudança, 2 para bloqueio de qualidade ou argumento inválido e 3 para falha técnica. [Comandos e contrato](docs/data-contract.md).

## Limites

Delta faz transação por tabela; o manifesto e o lock do volume mantêm a consistência entre as tabelas. Não há VACUUM automático. O relatório mostra até 500 linhas e 20 produtos, com os totais do conjunto inteiro. Não fiz estorno parcial, orquestrador nem monitoramento contínuo. [Código](src/retail_pipeline/pipeline.py) · [arquitetura](docs/architecture.md) · [decisões técnicas](docs/decisoes-tecnicas.md) · [proposta pra Fabric](docs/fabric-mapping.md).

Python, PySpark, Delta Lake, Spark SQL e Docker. Licença MIT.

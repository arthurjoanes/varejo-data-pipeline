# Problema e solução

Uma rede precisa fechar vendas sem transformar uma entrega incompleta ou uma correção rejeitada em indicador oficial. O erro difícil não é somar CSV: é preservar a última publicação coerente quando chegam revisões, faltam lojas ou o processo falha entre tabelas.

O operador aprova cadastro/calendário separadamente da entrega; o pipeline aceita apenas revisões de lotes publicados mais o candidato integralmente aprovado, mantém os itens ativos da mesma venda no mesmo dia comercial e publica um manifesto com versões Delta fixas. O consumidor captura esse manifesto uma vez. A decisão observável é publicar o fechamento ou bloquear e continuar servindo o anterior, com motivo e origem de cada indicador.

## Regras adotadas

| Situação | Regra | Resultado esperado |
|---|---|---|
| Remetente omite S02 nos arquivos e no próprio calendário | Configuração do operador fixada fora da entrada; cópia e hash em cada tentativa | Esperadas S01/S02/S03; S02 ausente; BLOCKED; publicação anterior idêntica |
| Venda A1 tem dois itens; só um muda de dia | Estado candidato validado por origem/loja/venda antes de gravar tabelas candidatas | Mudança parcial BLOCKED; mudança completa move todos os itens e preserva receita e quantidade de vendas |
| Revisão 99 rejeitada seguida de revisão válida menor | Histórico elegível vem do manifesto publicado | Revisão 99 ausente do histórico; revisão menor aceita |
| Falha depois do primeiro Gold e antes do ponteiro | Manifesto com versionAsOf; retomada reconstrói o candidato | Snapshot anterior estável; retry publica uma vez sem duplicação |
| Outro processo mantém o lock | Lock na fronteira de `process_batch`, antes de criar tentativa | WriterBusy antes da tentativa; kernel libera o lock após saída |

Os dois primeiros casos estão no [teste de negócio](../tests/integration/test_business_thesis.py). Os demais estão na suíte de 156 testes. O teste de lock cobre admissão de escritores antes do Spark e liberação pelo kernel; não exercita duas JVMs nem commits simultâneos.

## Como reproduzir

```powershell
docker compose run --rm --entrypoint python pipeline scripts/verify_problem.py --thesis-only --output /app/artifacts/thesis
```

O comando cria estado temporário novo, roda o teste de negócio com Spark/Delta real e grava `business-thesis.json`, `report.html`, `tests.xml` e `verification.json` em `artifacts/thesis`. Sem `--thesis-only`, roda a suíte inteira. Passos e valores em [demo.md](demo.md).

## Limites

Azure/Fabric não estão provisionados; a medição local não representa desempenho de produção. O calendário é aprovado pelo operador local; não há autenticação multiusuário. A atomicidade é um protocolo de publicação sobre filesystem local Linux, não uma transação Delta multitabela ou lock distribuído. Sem VACUUM automático: leitores antigos dependem da retenção das versões referenciadas.

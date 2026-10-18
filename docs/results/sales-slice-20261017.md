# Consulta de vendas por loja e dia

Acrescentei um recorte local para responder quais lojas e dias compõem a receita. A área fica separada dos totais da publicação e do mix de produtos, que têm outro escopo. O HTML continua sendo um snapshot, sem consulta a serviços e sem novas entregas Spark.

De e Até incluem os dias comerciais escolhidos. Os atalhos de 7 e 14 dias terminam na última data disponível, indicada junto aos controles. A loja é opcional, e o endereço conserva a seleção. A receita diária tem tabela exata; valores negativos mantêm o sinal e datas sem observação não recebem barras artificiais.

Dinheiro é somado em centavos inteiros, e contagens mantêm precisão de inteiro. Valor ausente continua indisponível. Um filtro sem linhas não significa venda zero. Relatórios truncados ou sem publicação não oferecem esse recorte.

## Capturas e verificações

As imagens em `docs/readme/sales-slice-desktop.png` e `sales-slice-mobile.png` foram capturadas em Edge local, em 1440 × 1000 e 390 × 844. A fonte é `historical-demo30k-report.json`: dados sintéticos capturados anteriormente, com 30 mil linhas entre 01 e 30/01/2026. Não executei novos lotes. A publicação completa conserva R$ 1.141.858,51; S01 entre 24 e 30/01 soma R$ 21.758,48, 190 vendas e 1.670 unidades.

Foram executados 147 testes de relatório (5 skips específicos do host Windows), 11 verificações Node de precisão/ausência/período, Ruff e formato em 69 arquivos, mypy no renderer e build do wheel com o novo recurso JavaScript. O harness do projeto verificou quatro estados em cinco larguras (320–1440 px): 613 checks, nenhuma falha e quatro scans Axe sem violações. A conferência adicional cobriu os filtros, restauração na URL, vazio, datas invertidas, movimento reduzido e leitura sem JavaScript. As barras entram em 220 ms; a preferência por movimento reduzido desativa a animação.

A suíte unitária inteira não foi executada neste ambiente: a coleta depende de PySpark e jsonschema, ausentes no venv local. A validação desta mudança ficou nos testes de relatório; Spark/Delta e permissões POSIX não foram reexecutados sem Docker. O workflow existente passa a executar também as verificações Node e a navegação de Recortar vendas.

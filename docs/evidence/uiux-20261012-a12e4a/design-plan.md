# Direção da revisão

Público: quem confere entregas de lojas e o fechamento publicado. Tarefa: reconhecer a decisão registrada, investigar uma pendência ou variação e conferir valores e origem. O relatório continua sendo um snapshot somente leitura.

## Duas composições

A: fechamento, comparação, análise. A identidade e os totais publicados abrem Indicadores. A comparação fica junto desses valores, com recorte e mudanças de contexto antes das regras. A matriz e os gráficos vêm depois. Distribuições, lote recebido e versões permanecem em detalhes nativos.

```text
Publicação e totais
Comparação: estado e avisos
Recorte e contexto / publicação anterior
Preço e quantidade: anterior, atual, diferença, motivo
Matriz / série / produtos
```

B: panorama e chamada de perfil. Mantém matriz, série e produtos como entrada e acrescenta uma chamada de avisos acima deles. Requer um salto para investigar a comparação no fim da página.

```text
Publicação e totais + link de aviso
Matriz / série / produtos
Comparação e seus detalhes
```

A foi escolhida porque a captura atual mostra o WARNING de preço fora da leitura inicial, numa tabela de oito colunas após os gráficos. Em 390 px, a primeira tela do perfil mostra contexto repetido e o ID, mas não mostra a regra. Não houve teste com usuários; a prioridade decorre desse percurso e do objetivo da entrega.

## Tokens e composição

Conservar Source Sans 3 local, com licença OFL, e a marca existente. Corpo de 16 px, metadados de 13 px, títulos de seção de 21 px. Valores usam algarismos tabulares; moeda mantém centavos e médias mantêm suas casas decimais.

Cores por função: texto #263248, apoio #596274, navegação/foco #49488f, papel #ffffff, fundo #f2f3f5, aviso #76550e. Bloqueio conserva #923b35. Espaçamento de 4/8/12/16/24 px nas novas estruturas; alinhamento à esquerda para leitura e à direita para números.

A comparação usa uma lista de regras, com o aviso primeiro. Anterior, atual e diferença permanecem visíveis sem percorrer oito colunas em telas estreitas; a tabela completa continua disponível. Contexto conhecido, parcial ou ausente aparece por texto antes da variação. A identidade da baseline pode abrir o registro completo e sua cópia, sem ocupar uma linha extensa na decisão inicial.

Navegação nativa, hashes e detalhes funcionam sem JavaScript. Não há ação de publicar, atualizar o pipeline ou executar Spark no HTML. A cor acompanha estado escrito; fontes, dados e segurança permanecem no contrato existente.

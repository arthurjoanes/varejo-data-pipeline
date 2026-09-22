# Evidências da interface v3

Esta pasta registra renderização offline e verificações de apresentação em 22/09/2026. Não contém nova execução de lote, benchmark, recuperação ou serviço. O ponto de partida foi `bff7a4ac5e9563c0a94fa81def27f3f4c7250853`.

- [Matriz, jornadas e crítica visual](../../frontend-quality.md).
- [Manifesto de fontes, entradas e capturas](review-manifest.json): SHA-256 dos bytes locais e normalização CRLF→LF para fontes textuais. PNGs têm hash binário. Hashes LF permitem comparar com blobs Git em clones com outro fim de linha.
- [Checks de Python e wheel](checks.json), [193 unitários](unit-tests.xml), [43 do renderer](reporting-tests.xml). O wheel é um artefato de build local sem rede; suas cópias de CSS/JS foram comparadas byte a byte com a fonte.
- [Browser](visual-review.json): 28 capturas, 15 combinações principais, estados adicionais, teclado, reflow, impressão, no-JS e equivalência de cinco snapshots.
- [Axe](accessibility.json): dez vistas, zero violações automáticas; itens incompletos de contraste SVG demandam inspeção. Não é certificação de acessibilidade.
- [Antes/depois](comparison.json): 14 pares com o mesmo payload, vista e dimensão. Seis baselines portáteis em [before](../../images/interface-v3/before). Os demais caminhos absolutos registram a estação de captura; não são URLs públicas. Medições `file://` não são benchmark de produção.

`initial-checks.json`, `initial-unit.txt` e `initial-unit-tests.xml` preservam a primeira rodada: três assertions ligadas ao h1 antigo falharam, enquanto 189 passaram. Os testes foram ajustados para o h2 de estado com a mesma expectativa de texto. As provas finais acima se referem à fonte final.

Os payloads de [interface/payloads](../interface/payloads) não foram alterados. `*-fixture` identifica cenários artificiais de apresentação, incluindo desconhecido, validado, zero, ausência, lacunas e stress de texto/número; esses cenários não são provas de operações. As pastas de interface v2 e jornadas anteriores permanecem intactas.

Limites: não houve novo Spark; não foram auditados leitor de tela, zoom nativo, outros navegadores, paginação completa de PDF, CI remoto ou performance de produção. Consulte os detalhes na matriz antes de generalizar um resultado.

# Evidências da evolução de 12/10/2026

Cada fase identifica seus arquivos e imagem. As execuções dirigidas complementam a suíte integral; seus números não são somados como uma nova suíte completa. O [índice de bytes e SHA-256](index.json) permite conferir estes arquivos. Os diretórios históricos anteriores permanecem intactos.

| Fase | Fonte e resultado | Recibo |
| --- | --- | --- |
| Suíte integral | `0ddab5e`, imagem `d510a4c9`: 369 aprovados, zero falhas, erros ou skips. | [Resumo](tests-final-summary.json), [JUnit](tests-final.xml), [fontes antes](source-before.json) e [depois](source-after.json). |
| Rótulos da interface | Conteúdo persistido em `bc66968`, testado no bind antes do commit: 352 unitários aprovados. | [Associação e limite de identidade](unit-labels-association.json), [JUnit](unit-labels.xml). |
| Comparação e reexportação | `bc66968`, imagem `8165ad96`: três publicações, R$ 64 → 104 → 64; COMPLETE recuperado e bytes preservados. | [Execução](evolution-demo/execution.json), [reexportação](evolution-demo/reexport.json), [fontes](demo-source-confirmation.json). |
| Interface real | Três HTMLs gerados pelo Spark, quatro larguras no Edge 155. | [Índice dos controles e capturas](browser-index.json). |
| Restauração | `bc66968`, imagem `8165ad96`: três publicações e perfis preservados, tar adulterado e destino ocupado recusados. | [Recibo público](restore/result.public.json), [inventário](restore/backup-manifest.json). |
| Loja nova e runtime | `6c96833`, imagem `e5403499`: três integrações aprovadas; o recorte comum conserva R$ 64 apesar da nova receita de S04. | [Resumo](delivery-directed-summary.json), [JUnit](delivery-directed.xml), [fontes](source-delivery-before.json). |
| Segurança da imagem de entrega | OS/JVM/Python: zero HIGH/CRITICAL, dois MEDIUM, sem exclusões adicionais. | [Scan integral](security-delivery-scan.json), [identidade e inventário](security-delivery-summary.json). |
| Segredos do histórico Git | Gitleaks 8.30.1: zero achados após incluir a mesma fingerprint pública em três caminhos exatos; dois controles continuam detectados. | [Resumo](secrets-summary.json), [histórico aprovado](secrets-history-final.json), [controles](secrets-controls.json). |

O [scan inicial e a correção do LZ4](security-index.json) conservam também a primeira falha do gate e os controles de API/interoperabilidade. A falha inicial de coleta por nomes de testes duplicados e a execução interrompida para corrigir o HIGH têm logs e fontes separados. Um probe nativo chegou ao resultado funcional, mas seu primeiro cleanup excedeu o prazo; esse registro também permanece no índice de segurança.

Os resultados do navegador e da restauração têm derivações públicas declaradas: o primeiro remove somente o caminho absoluto do HTML; o segundo omite nomes, IDs e estatísticas detalhadas de containers externos. Seus recibos originais permanecem localmente com hashes. Tar, cópia adulterada, caches e ferramentas auxiliares ficam fora do Git. Não há benchmark pareado de overhead, ingestão testada em collector externo ou prova de recuperação fora deste host.

[Roteiros e comandos](../../evolution.md) · [verificações completas e limites](../../verification.md) · [recursos deixados locais](resources.json).

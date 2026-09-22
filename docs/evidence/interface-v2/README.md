# Revisão da composição do relatório

O [manifesto](review-manifest.json) identifica os bytes da fonte, das entradas históricas e das capturas. O [registro do navegador](visual-review.json) informa casos, ambiente e limites. A rodada testa apresentação; não cria uma nova prova de runtime.

Testes do gerador: **38 aprovados**. [Resultado](reporting-tests.xml). As imagens desta rodada estão em `docs/images/interface-v2`; as capturas anteriores continuam preservadas.

Os hashes originais identificam os bytes locais usados na revisão. O campo `text_sha256_lf` também registra fontes, entradas e registros textuais normalizados apenas de CRLF para LF, permitindo comparar um clone sem confundir conversão de fim de linha com mudança de conteúdo. Os PNGs usam seus bytes exatos.

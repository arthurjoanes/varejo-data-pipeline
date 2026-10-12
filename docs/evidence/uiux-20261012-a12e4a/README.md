# Revisão da interface em 12/10/2026

Esta revisão cobre o HTML de conferência do Varejo Data Pipeline. O snapshot permite consulta, navegação e cópia de IDs; não executa Spark nem publica entregas. A marca usa azul petróleo, com estados semânticos conservados. [Jornadas e direção](../../frontend-quality.md#revisão-de-uiux-em-12102026).

O antes usa `64a9cf7769c9ea5225189d6dab0d9ca94548b63c`. A fonte final estava não commitada durante os gates: [94 hashes e objetos Git](source-candidate-v5.json), [diff](candidate-v5.diff) e [conferência após os gates](source-candidate-v5-after.json). HEAD sozinho não identifica o candidato. Nenhuma fonte mudou durante a execução. O índice inclui os bytes públicos; originais privados permanecem em `artifacts/uiux-20261012-a12e4a`.

## Dados e imagens

Os [22 inputs](inputs/) são três ReportPayloads relidos de publicações sintéticas existentes, cinco payloads históricos e 14 fixtures de apresentação. A captura real usou versões Delta fixadas numa sessão Spark, sem processar novos lotes. Os [174 arquivos duráveis](domain-capture-before.json) permaneceram [iguais](domain-capture-after.json). Os três HTMLs anteriores [coincidem byte a byte](before-capture-byte-equality.json) com a captura.

O replay posterior foi offline. [Manifesto anterior](corpus-before.json) e [final](corpus-after.json) conservam os mesmos hashes dos inputs. R$ 64,00, R$ 104,00 e R$ 64,00 pertencem às publicações identificadas; datas de setembro não foram renovadas. Fixtures de apresentação são rotuladas no HTML e não provam uma execução de domínio.

Os [18 pares](image-pairs.json) têm os mesmos estados e viewports de 320, 390, 768, 1024 e 1440 CSS px. Foram abertos em tamanho legível, sem edição de pixels. [Antes do perfil](../../images/uiux-20261012-a12e4a/before/comparable-profile-top-390.png) · [Depois](../../images/uiux-20261012-a12e4a/after/comparable-profile-top-390.png). Os HTMLs reais também ficam em [before](before/) e [after](after/).

## Gates e limites

| Gate final | Resultado | Recibo |
| --- | --- | --- |
| Linux | 374 unitários, incluindo 91 do renderer; Ruff, formato64, mypy20 | [Resumo](quality-final.public.json), [JUnit](quality-v5-unit.xml) |
| Pacote | Wheel com 34 arquivos iguais à fonte; import/render isolado | [Verificação](quality-v5-wheel-backend/wheel-check.json) |
| Edge155 | 22 casos, 3.560 checks, 18 capturas, zero falhas | [Relatório](qa-final-edge-v5/uiux-review.json) |
| Firefox155 | Comparação, matriz e dinheiro extenso; 479 checks, zero falhas | [Relatório](qa-final-firefox-v5/uiux-review.json) |
| Axe4.13 | Zero violações nas regras selecionadas; 80/11 resultados inconclusivos | [Revisão e seletores](manual-review-v5.json) |
| Foco e seleção | Banda12 alvos mínimo12,866:1; paleta6 tons mínimo3,904:1 para o anel mais visível | [Banda](focus-state-v5.json), [fixture separada](focus-palette-v5/probe.json) |

Os navegadores conferiram teclado, foco, âncoras/histórico, detalhes, cópia/fallback, tabelas exatas, reflow, conteúdo longo, movimento reduzido, espaçamento de texto e leitura sem JavaScript. Não houve requisição remota, falha de rede ou erro de página. Alvos medidos usam retângulo de 24 × 24 CSS px ou exceção documentada de texto/espaçamento; não constituem ensaio físico de toque.

Os `incomplete` de contraste em SVG, fundos e regiões de rolagem/sticky permanecem inconclusivos. Amostras textuais calculadas tiveram mínimo5,000:1. Zoom nativo, leitor de tela e forced-colors são **NV**. Não houve estudo com usuários, medida de produtividade, benchmark novo ou ensaio integral de PDF. Estas provas não certificam conformidade WCAG completa.

Os candidatos anteriores e falhas permanecem em `iterations-v1` a `iterations-v4`. [Correções do oracle](iterations-v1/oracle-corrections-v2.json) explicam os três falsos negativos de placeholders sem publicação e os textos de período; os problemas reais de layout não foram removidos do gate.

## Reprodução offline

Com Python do setup do projeto, usando uma pasta de saída nova:

```powershell
$env:PYTHONPATH = 'src'
python scripts/render_uiux_corpus.py docs/evidence/uiux-20261012-a12e4a/inputs artifacts/uiux-replay-new/after --phase after
$env:UIUX_INPUTS = 'docs/evidence/uiux-20261012-a12e4a/inputs'
$env:UIUX_BEFORE_MANIFEST = 'docs/evidence/uiux-20261012-a12e4a/corpus-before.json'
$env:PLAYWRIGHT_CHANNEL = 'msedge'
node scripts/uiux-report-review.cjs after artifacts/uiux-replay-new/after artifacts/uiux-replay-new/review-edge
```

Playwright1.63 e axe4.13 são ferramentas de desenvolvimento, fora das dependências do produto. `PLAYWRIGHT_MODULE` e `AXE_MODULE` podem apontar para módulos isolados; [package/lock](tools/) e [manifesto](tooling-manifest.public.json) identificam os utilizados. Para Firefox, use `REVIEW_BROWSER=firefox`, seu runtime Playwright e `PLAYWRIGHT_BROWSERS_PATH`. Instalação pode exigir rede; leitura dos HTMLs é offline.

Para renderizar o antes, selecione `PYTHONPATH=docs/evidence/uiux-20261012-a12e4a/renderer-before`, uma saída nova e `--phase before`. No navegador, indique `UIUX_RENDERER_DIR` para a subpasta `renderer-before/retail_pipeline`, `UIUX_INPUTS` para os mesmos JSONs e a fase `before`. Esse pacote congelado inclui módulos, CSS, JavaScript, fonte e licenças. Não use `--capture` nem processe novas entregas para reproduzir a apresentação.

[Pesquisa primária](research.json), [duas composições](design-plan.md) e recipes originais estão preservadas. [Proveniência inicial](provenance-public.json) e [derivações posteriores](provenance-final.json) registram hashes originais/públicos e substituições de caminhos privados. Arquivos públicos não publicam credenciais ou prefixos privados do host.

O [scan do histórico](security-final-summary.json) terminou com zero achados, mantendo regras padrão e exceções por valor e caminho exatos. [Controles negativos](security-control-summary.json) e [checksums verificados](public-checksum-verification.json) explicam o escopo.

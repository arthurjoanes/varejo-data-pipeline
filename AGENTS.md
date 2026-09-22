# Orientações para mudanças na interface

Leia [docs/frontend-quality.md](docs/frontend-quality.md) antes de alterar o relatório. O documento registra público, três jornadas, matriz de qualidade, fontes visuais e limites das provas.

- Preserve o contrato de snapshot: tentativa, publicação e última falha têm identidades próprias. Ausência não significa zero; duração não confirma sucesso; o relatório não executa operações.
- Mantenha valores e regras de domínio. Compare antes/depois com o mesmo payload e viewport, incluindo bloqueio, falha, auditoria incompleta e leitura sem JavaScript.
- Use HTML/CSS/JS locais e sem dependências de runtime adicionais. Preserve detalhes nativos, links profundos, foco, impressão e conteúdo completo dos identificadores.
- Para mudanças visuais, atualize capturas e evidências em pasta própria. Não sobrescreva provas históricas nem trate fixtures de apresentação como novas execuções.
- Execute os gates pertinentes descritos no documento. Uma mudança de renderer não exige reexecutar Spark se dados, leitura e regras permanecerem intactos; registre esse limite.

// Navegação de um snapshot local. Sem consultas de rede ou atualização automática.
// O HTML completo e os detalhes nativos continuam legíveis sem JavaScript.
const views = [...document.querySelectorAll('[data-report-view]')];
const navigation = [...document.querySelectorAll('[data-view-link]')];

function showLocation(focus = false) {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { id = ''; }
  const target = document.getElementById(id);
  const view = target?.closest('[data-report-view]')
    || (target && views.find(panel => !panel.hidden))
    || views[0];
  if (!view) return;
  for (const panel of views) panel.hidden = panel !== view;
  for (const link of navigation) {
    if (link.dataset.viewLink === view.id) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  // Âncoras de IDs revelam também o detalhe nativo que contém o campo.
  if (target) {
    let disclosure = target.closest('details');
    while (disclosure) {
      disclosure.open = true;
      disclosure = disclosure.parentElement?.closest('details');
    }
  }
  if (focus && target) {
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: 'start', behavior: 'instant' });
  }
}
showLocation();
window.addEventListener('hashchange', () => showLocation(true));
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', () => {
    if (link.hash === location.hash) showLocation(true);
  });
});

document.querySelectorAll('[data-copy-target]').forEach(button => {
  button.hidden = false;
  button.addEventListener('click', async () => {
    const input = document.getElementById(button.dataset.copyTarget);
    const status = document.getElementById('copy-status');
    try {
      if (!navigator.clipboard) throw new Error('Clipboard indisponível');
      await navigator.clipboard.writeText(input.value);
      status.textContent = 'ID copiado.';
    } catch {
      input.focus();
      input.select();
      let copied = false;
      try { copied = document.execCommand('copy'); } catch { /* Seleção permite cópia manual. */ }
      status.textContent = copied ? 'ID copiado.' : 'Falha ao copiar. ID selecionado; use Ctrl+C.';
    }
  });
});

// Matriz compacta: uma célula no percurso Tab; o valor exato permanece visível.
const matrixCells = [...document.querySelectorAll('[data-heat-cell]')];
const matrixOutput = document.getElementById('matrix-value');
const matrixRecord = document.getElementById('matrix-record');
function selectMatrixCell(cell, focus = false) {
  for (const candidate of matrixCells) {
    candidate.tabIndex = candidate === cell ? 0 : -1;
    if (candidate === cell) candidate.setAttribute('aria-current', 'true');
    else candidate.removeAttribute('aria-current');
  }
  matrixOutput.textContent = cell.dataset.value;
  matrixRecord.href = cell.getAttribute('href');
  matrixRecord.textContent = 'Consultar linha na tabela';
  if (focus) cell.focus();
}
if (matrixCells.length) {
  document.querySelector('.matrix-help').hidden = false;
  selectMatrixCell(matrixCells[0]);
  matrixCells.forEach(cell => {
    cell.addEventListener('click', event => { event.preventDefault(); selectMatrixCell(cell); });
    cell.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const row = Number(cell.dataset.row), column = Number(cell.dataset.column);
      const horizontal = ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key);
      let candidates = matrixCells.filter(candidate => horizontal ? Number(candidate.dataset.row) === row : Number(candidate.dataset.column) === column);
      const index = candidates.indexOf(cell);
      const offset = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
      const next = event.key === 'Home' ? candidates[0] : event.key === 'End' ? candidates.at(-1) : candidates[index + offset];
      if (next) selectMatrixCell(next, true);
    });
  });
}

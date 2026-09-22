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

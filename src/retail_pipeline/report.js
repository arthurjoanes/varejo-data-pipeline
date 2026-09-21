// Leitura e navegação funcionam sem este script.

// Marca na navegação a seção visível no momento.
const navLinks = new Map();
document.querySelectorAll('.report-nav a[href^="#"]').forEach(link => {
  navLinks.set(link.getAttribute('href').slice(1), link);
});
if (navLinks.size && 'IntersectionObserver' in window) {
  const order = [...navLinks.keys()];
  const visible = new Set();
  const setCurrent = current => {
    navLinks.forEach((link, id) => {
      if (id === current) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  };
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) visible.add(entry.target.id);
      else visible.delete(entry.target.id);
    }
    const current = order.find(id => visible.has(id));
    if (current) setCurrent(current);
  }, { rootMargin: '-12% 0px -70% 0px', threshold: 0 });
  order.forEach(id => {
    const section = document.getElementById(id);
    if (section) observer.observe(section);
  });
}

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
      try { copied = document.execCommand('copy'); } catch { /* Mantém o ID selecionado para cópia manual. */ }
      status.textContent = copied
        ? 'ID copiado.'
        : 'Falha ao copiar. ID selecionado; use Ctrl+C.';
    }
  });
});

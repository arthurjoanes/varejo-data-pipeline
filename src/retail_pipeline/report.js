// Navegação de um snapshot local. Sem consultas de rede ou atualização automática.
// O HTML completo e os detalhes nativos continuam legíveis sem JavaScript.
const views = [...document.querySelectorAll('[data-report-view]')];
const navigation = [...document.querySelectorAll('[data-view-link]')];
let currentView = null;

function showLocation(focus = false) {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { id = ''; }
  const target = document.getElementById(id);
  const view = target?.closest('[data-report-view]')
    || (target && currentView)
    || document.getElementById(document.getElementById('content').dataset.defaultView)
    || views[0];
  if (!view) return;
  currentView = view;
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
    const status = document.getElementById(button.dataset.copyStatus || 'copy-status');
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

// This explorer has its own scope; publication, quality and product totals stay unchanged.
const salesData = document.getElementById('sales-slice-data');
if (salesData) {
  const rows = JSON.parse(salesData.textContent);
  const from = document.getElementById('sales-from');
  const to = document.getElementById('sales-to');
  const store = document.getElementById('sales-store');
  const output = document.getElementById('sales-slice-result');
  const reference = recentSalesPeriod(rows, 1).to;
  document.getElementById('sales-slice-controls').hidden = false;
  document.getElementById('sales-slice-reference').textContent = reference
    ? `Atalhos terminam em ${reference.split('-').reverse().join('/')}, último dia comercial deste snapshot. Não há atualização automática.`
    : 'Este snapshot não contém linhas de loja e dia para recortar.';
  [...new Set(rows.map(row => row.store_id))].sort().forEach(id => store.add(new Option(id, id)));
  const params = new URLSearchParams(location.search);
  const calendarDay = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0,10) === value;
  from.value = calendarDay(params.get('salesFrom')) ? params.get('salesFrom') : '';
  to.value = calendarDay(params.get('salesTo')) ? params.get('salesTo') : '';
  if ([...store.options].some(option => option.value === params.get('salesStore'))) store.value = params.get('salesStore');
  function renderSalesSlice() {
    output.replaceChildren();
    const note = document.createElement('p');
    note.className = 'meta';
    let slice;
    try { slice = sliceSales(rows, from.value, to.value, store.value); }
    catch (error) { note.textContent = error.message; output.append(note); to.setAttribute('aria-invalid','true'); return; }
    to.removeAttribute('aria-invalid');
    const url = new URL(location.href);
    for (const [key, value] of [['salesFrom',from.value],['salesTo',to.value],['salesStore',store.value]]) {
      if (value) url.searchParams.set(key,value); else url.searchParams.delete(key);
    }
    history.replaceState(null,'',url);
    note.textContent = slice.rows.length ? `${slice.rows.length} linhas de loja e dia no recorte. Valores ausentes ficam indisponíveis.` : 'Nenhuma observação nesse período e loja. Ausência de linha não é venda zero.';
    output.append(note);
    if (!slice.rows.length) return;
    const cards = document.createElement('div'); cards.className = 'metrics';
    for (const [label,value,metric] of [['Receita no recorte',salesMoney(slice.revenue),'slice-revenue'],['Vendas',slice.sales?.toLocaleString('pt-BR') ?? '—','slice-sales'],['Unidades',slice.units?.toLocaleString('pt-BR') ?? '—','slice-units']]) {
      const card = document.createElement('article'); card.className = 'metric';
      const caption = document.createElement('p'); caption.textContent = label;
      const number = document.createElement('strong'); number.dataset.metric = metric; number.textContent = value;
      card.append(caption,number); cards.append(card);
    }
    output.append(cards);
    const heading = document.createElement('h3'); heading.textContent = 'Receita diária no recorte'; output.append(heading);
    const known = slice.daily.filter(day => day.revenue !== null);
    if (known.length) {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox','0 0 640 180'); svg.classList.add('sales-slice-chart'); svg.setAttribute('role','img'); svg.setAttribute('aria-label','Receita líquida diária. Valores exatos na tabela seguinte.');
      const minimum = known.reduce((value,day)=>day.revenue < value ? day.revenue : value,0n);
      const maximum = known.reduce((value,day)=>day.revenue > value ? day.revenue : value,0n);
      const range = maximum-minimum || 1n;
      const y = value => 145-Number((value-minimum)*13000n/range)/100;
      const first = Date.parse(`${slice.daily[0].day}T00:00:00Z`);
      const span = Math.max(1,(Date.parse(`${slice.daily.at(-1).day}T00:00:00Z`)-first)/86400000+1);
      const baseline = document.createElementNS(ns,'line'); baseline.setAttribute('x1','10'); baseline.setAttribute('x2','630'); baseline.setAttribute('y1',y(0n)); baseline.setAttribute('y2',y(0n)); baseline.classList.add('slice-baseline'); svg.append(baseline);
      for (const day of known) {
        const rect = document.createElementNS(ns,'rect'); const width = Math.min(48,590/span);
        rect.setAttribute('x',20+(Date.parse(`${day.day}T00:00:00Z`)-first)/86400000*600/span+(600/span-width)/2);
        rect.setAttribute('y',Math.min(y(day.revenue),y(0n))); rect.setAttribute('width',width); rect.setAttribute('height',Math.abs(y(day.revenue)-y(0n)));
        rect.classList.add('sales-trend-bar'); rect.dataset.chartDate = day.day; rect.dataset.valueRaw = String(day.revenue);
        if (day.revenue < 0n) rect.dataset.sign = 'negative';
        const title = document.createElementNS(ns,'title'); title.textContent = `${day.day}: ${salesMoney(day.revenue)}`; rect.append(title); svg.append(rect);
      }
      for (const [day,x,anchor] of [[slice.daily[0].day,20,'start'],[slice.daily.at(-1).day,620,'end']]) {
        const label = document.createElementNS(ns,'text'); label.setAttribute('x',x); label.setAttribute('y','174'); label.setAttribute('text-anchor',anchor); label.textContent=day.split('-').reverse().join('/'); svg.append(label);
      }
      output.append(svg);
    }
    const disclosure = document.createElement('details'); disclosure.className = 'data-detail';
    const summary = document.createElement('summary'); summary.textContent = 'Valores exatos por dia';
    const table = document.createElement('table');
    const caption = document.createElement('caption'); caption.textContent = 'Receita líquida no período e nas lojas selecionadas'; table.append(caption);
    const head = table.createTHead().insertRow();
    for (const text of ['Dia comercial','Receita líquida']) { const th = document.createElement('th'); th.scope = 'col'; th.textContent = text; head.append(th); }
    const body = table.createTBody();
    for (const day of slice.daily) { const row = body.insertRow(); row.insertCell().textContent = day.day; row.insertCell().textContent = salesMoney(day.revenue); }
    disclosure.append(summary,table); output.append(disclosure);
  }
  [from,to,store].forEach(control => control.addEventListener('change',renderSalesSlice));
  document.querySelectorAll('[data-sales-days]').forEach(button=>button.addEventListener('click',()=>{
    const days = Number(button.dataset.salesDays);
    const period = days ? recentSalesPeriod(rows,days) : {from:'',to:''};
    from.value=period.from; to.value=period.to; renderSalesSlice();
  }));
  renderSalesSlice();
}

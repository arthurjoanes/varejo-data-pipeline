/* Development-only offline UI review. Does not execute the pipeline or change inputs.
 * Usage: node uiux-review.proposed.cjs before|after HTML_DIRECTORY NEW_OUTPUT_DIRECTORY
 * PLAYWRIGHT_MODULE / AXE_MODULE select isolated developer tools.
 * REVIEW_BROWSER=chromium|firefox; PLAYWRIGHT_CHANNEL=msedge is optional for Chromium.
 * BEFORE records presentation findings; AFTER gates them. Data/journey failures gate both.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');
const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const playwright = require(playwrightModule);
const AxeBuilder = require(process.env.AXE_MODULE || '@axe-core/playwright').default;
const phase = process.argv[2];
assert.ok(['before', 'after'].includes(phase), 'Phase must be before or after');
function repository() {
  for (const candidate of [process.cwd(), path.resolve(__dirname, '..'), path.resolve(__dirname, '..', '..')]) {
    if (fs.existsSync(path.join(candidate, 'pyproject.toml')) && fs.existsSync(path.join(candidate, 'src'))) return candidate;
  }
  throw new Error('Run from the Varejo Data Pipeline repository');
}
const root = repository();
const work = path.join(root, 'artifacts', 'uiux-20261012-a12e4a');
const htmlDirectory = path.resolve(process.argv[3] || path.join(work, phase));
const inputDirectory = path.resolve(process.env.UIUX_INPUTS || path.join(path.dirname(htmlDirectory), 'inputs'));
const browserName = process.env.REVIEW_BROWSER || 'chromium';
assert.ok(['chromium', 'firefox'].includes(browserName), 'Supported browser: chromium or firefox');
const output = path.resolve(process.argv[4] || path.join(work, 'qa-' + phase + '-' + browserName));
assert.ok(fs.existsSync(htmlDirectory), 'Captured corpus directory must exist');
assert.ok(!fs.existsSync(output), 'Use a new output directory; previous evidence is preserved');
assert.ok(output.startsWith(root + path.sep), 'Output must stay inside this project');
fs.mkdirSync(path.join(output, 'images'), { recursive: true });
const widths = [320, 390, 768, 1024, 1440];
const views = ['qualidade', 'indicadores', 'proveniencia'];
const selected = process.env.UIUX_CASES ? new Set(process.env.UIUX_CASES.split(',').filter(Boolean)) : null;
const files = fs.readdirSync(htmlDirectory).filter(file => file.endsWith('.html')).sort()
  .filter(file => !selected || selected.has(path.basename(file, '.html')));
assert.ok(files.length, 'At least one HTML report is required');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const relative = file => path.relative(root, file).replaceAll('\\', '/');
const json = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim();
const attr = value => String(value).replaceAll('\\', '\\\\').replaceAll('"', '\\"').replace(/\r?\n/g, '\\a ');
// Preserve JSON numeric token spelling for Decimal(str(float)) quantile probabilities.
// This is an oracle read only; the real captured payload remains byte-identical.
function lexicalJSON(text) {
  return JSON.parse(text.replace(/("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (token, quoted, number) => quoted || JSON.stringify(number)));
}
const result = {
  phase, browser: browserName, captured_at: new Date().toISOString(), viewports: widths,
  harness_sha256: sha(fs.readFileSync(__filename)),
  inputs: [], checks: [], layouts: [], accessibility: [], contrast: [], targets: [], fonts: [],
  journeys: [], data: [], screenshots: [], requests: { remote: [], failed: [], errors: [], consoleErrors: [] },
  limitations: [
    'Automated and sampled checks complement manual keyboard/assistive-technology review; no complete WCAG conformance claim.',
    '320 CSS px layout and CSS text-spacing overrides are not native browser zoom. Native browser zoom and screen-reader assessment remain manual.',
    'Pointer target checks use layout rectangles/spacing, not pixel-perfect shape hit-testing. Incomplete axe results require review.',
    'Screenshots capture bounded viewports, not full-page pagination or every disclosure at once.',
    'Presentation fixtures are explicitly distinguished from immutable pipeline evidence.'
  ]
};
function check(name, ok, detail = {}, gate = 'always') {
  result.checks.push({ name, ok: Boolean(ok), gate, detail });
  return Boolean(ok);
}
function equal(name, actual, expected, gate = 'always') {
  let ok = true;
  try { assert.deepEqual(actual, expected); } catch { ok = false; }
  return check(name, ok, { expected, actual }, gate);
}
function scope(name, item, extra = '') { return item.name + ':' + name + (extra ? ':' + extra : ''); }
function decimalParts(value) {
  if (value == null) return null;
  let text = String(value);
  const match = text.match(/^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);
  assert.ok(match, 'Expected a finite persisted decimal: ' + text);
  const negative = match[1] === '-';
  let fraction = match[3] || '';
  let integer = match[2];
  const exponent = Number(match[4] || 0);
  if (exponent > 0) {
    integer += fraction.slice(0, exponent).padEnd(exponent, '0');
    fraction = fraction.slice(exponent);
  } else if (exponent < 0) {
    const digits = integer + fraction;
    const position = integer.length + exponent;
    integer = position > 0 ? digits.slice(0, position) : '0';
    fraction = position > 0 ? digits.slice(position) : '0'.repeat(-position) + digits;
  }
  integer = integer.replace(/^0+(?=\d)/, '');
  return { negative, integer, fraction };
}
function grouped(integer) { return integer.replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
function exact(value) {
  const parts = decimalParts(value);
  return parts ? (parts.negative ? '-' : '') + grouped(parts.integer) + (parts.fraction ? ',' + parts.fraction : '') : '—';
}
function integer(value) {
  const parts = decimalParts(value);
  return parts ? (parts.negative ? '-' : '') + grouped(parts.integer) : '—';
}
function money(value) {
  const parts = decimalParts(value);
  if (!parts) return '—';
  let cents = BigInt(parts.integer) * 100n + BigInt(parts.fraction.slice(0, 2).padEnd(2, '0'));
  if (Number(parts.fraction[2] || 0) >= 5) cents++;
  const digits = cents.toString().padStart(3, '0');
  return 'R$ ' + (parts.negative ? '-' : '') + grouped(digits.slice(0, -2)) + ',' + digits.slice(-2);
}
function percentage(value) {
  const parts = decimalParts(value);
  if (!parts) return '—';
  const scale = parts.fraction.length;
  const coefficient = BigInt(parts.integer + parts.fraction) * 100n;
  const digits = coefficient.toString().padStart(scale + 1, '0');
  const decimal = (parts.negative ? '-' : '') + (scale ? digits.slice(0, -scale) + '.' + digits.slice(-scale) : digits);
  return exact(decimal) + '%';
}
function date(value) {
  if (value == null) return '—';
  const text = String(value).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text.slice(8) + '/' + text.slice(5, 7) + '/' + text.slice(0, 4) : String(value);
}
function dateRange(value) {
  if (!value || (value.start == null && value.date_count !== 0)) return 'Período não informado';
  if (value.start == null) return 'Sem datas de movimento';
  return date(value.start) + ' a ' + date(value.end) + ' · ' + integer(value.date_count) + ' dias registrados';
}
function chips(values, limit) {
  const items = Array.isArray(values) ? values : [];
  return items.length ? items.slice(0, limit).map(String).concat(items.length > limit ? ['+' + (items.length - limit)] : []) : ['Nenhuma'];
}
// Read renderer labels and bounds instead of silently fixing an old presentation contract.
const renderer = phase === 'before' ? path.join(path.dirname(htmlDirectory), 'renderer-before', 'retail_pipeline') : path.join(root, 'src', 'retail_pipeline');
const viewSource = fs.readFileSync(path.join(renderer, 'report_view.py'), 'utf8');
const modelSource = fs.readFileSync(path.join(renderer, 'report_model.py'), 'utf8');
function sourceDictionary(name) {
  const block = viewSource.match(new RegExp('^' + name + ' = \\{([\\s\\S]*?)^\\}', 'm'));
  assert.ok(block, 'Renderer mapping missing: ' + name);
  return Object.fromEntries([...block[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(match => [match[1], match[2]]));
}
function sourceLimit(name) {
  const match = modelSource.match(new RegExp('^' + name + ' = (\\d+)', 'm'));
  assert.ok(match, 'Renderer bound missing: ' + name);
  return Number(match[1]);
}
const constants = {
  profileStates: sourceDictionary('PROFILE_STATES'), comparisonStates: sourceDictionary('COMPARISON_STATES'),
  rules: sourceDictionary('PROFILE_RULES'), ruleStates: sourceDictionary('PROFILE_RULE_STATES'),
  distributions: sourceDictionary('PROFILE_DISTRIBUTIONS'),
  totals: [...viewSource.match(/^PROFILE_TOTALS = \(([\s\S]*?)^\)/m)[1].matchAll(/\("([^"]+)", "([^"]+)", "([^"]+)"\)/g)].map(match => match.slice(1)),
  groupLimit: sourceLimit('PROFILE_GROUP_LIMIT'), quantileLimit: sourceLimit('PROFILE_QUANTILE_LIMIT')
};
result.renderer = { directory: relative(renderer), view_sha256: sha(Buffer.from(viewSource)), model_sha256: sha(Buffer.from(modelSource)), constants };
const manifestPath = path.join(path.dirname(htmlDirectory), 'corpus-' + phase + '.json');
const manifest = fs.existsSync(manifestPath) ? json(manifestPath) : null;
const beforeManifestPath = path.join(path.dirname(htmlDirectory), 'corpus-before.json');
const beforeManifest = fs.existsSync(beforeManifestPath) ? json(beforeManifestPath) : null;
function profileStatus(payload) {
  let state = payload.profile_result?.status || (payload.snapshot?.profile ? 'MISSING' : 'LEGACY');
  const profile = payload.profile_result?.profile || {};
  if (!payload.snapshot) state = 'NO_PUBLICATION';
  else if (state === 'AVAILABLE' && (profile.publication_id !== payload.snapshot.publication_id || (payload.snapshot.run_id != null && profile.run_id !== payload.snapshot.run_id))) state = 'INVALID';
  return state;
}
function safeError(error) {
  return String(error?.message || error).replaceAll(root, '<project>').replaceAll(root.replaceAll('\\', '/'), '<project>');
}
function observe(context, name, mode) {
  context.on('page', page => {
    page.on('pageerror', error => result.requests.errors.push({ name, mode, message: safeError(error) }));
    page.on('console', message => {
      if (message.type() === 'error') result.requests.consoleErrors.push({ name, mode, message: safeError(message.text()) });
    });
  });
  context.on('request', request => {
    if (/^https?:/i.test(request.url())) result.requests.remote.push({ name, mode, url: request.url() });
  });
  context.on('requestfailed', request => {
    const url = request.url();
    result.requests.failed.push({ name, mode, url: url.startsWith('file:') ? path.basename(new URL(url).pathname) : url, error: request.failure()?.errorText });
  });
}
async function loaded(page, item, hash = '') {
  // A hash-only goto reuses disclosure state and injected test CSS. Start a fresh document.
  await page.goto('about:blank');
  await page.goto(item.url + hash, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
}
async function view(page, id) {
  const link = page.locator('[data-view-link="' + id + '"]');
  await link.focus();
  await page.keyboard.press('Enter');
  await page.locator('[data-view-link="' + id + '"][aria-current="page"]').waitFor({ state: 'visible' });
  await page.locator('#' + id).waitFor({ state: 'visible' });
}
async function openDetails(page, selector) {
  const summaries = page.locator(selector + ' details > summary');
  for (let index = 0; index < await summaries.count(); index++) {
    const summary = summaries.nth(index);
    if (await summary.isVisible() && !await summary.evaluate(element => element.parentElement.open)) {
      await summary.focus();
      await page.keyboard.press('Enter');
    }
  }
}
async function tables(page, selector = '#perfil') {
  return page.locator(selector + ' table').evaluateAll(elements => elements.map(table => ({
    name: table.caption?.textContent.trim() || table.getAttribute('aria-label') || table.closest('[role="region"]')?.getAttribute('aria-label') || '',
    headers: [...(table.tHead?.rows[0]?.cells || [])].map(cell => cell.textContent.replace(/\s+/g, ' ').trim()),
    rows: [...table.tBodies].flatMap(body => [...body.rows].map(row => [...row.cells].map(cell => cell.textContent.replace(/\s+/g, ' ').trim())))
  })));
}
async function dataChecks(page, item) {
  const payload = item.payload;
  await loaded(page, item, '#perfil');
  await openDetails(page, '#perfil');
  const observedTables = await tables(page);
  item.tables = observedTables;
  result.data.push({ name: item.name, profile_tables: observedTables });
  const semantics = await page.locator('#perfil table').evaluateAll(elements => elements.map(table => ({
    name: table.caption?.textContent.trim() || '',
    column_scopes: [...(table.tHead?.rows[0]?.cells || [])].map(cell => cell.getAttribute('scope')),
    row_headers: [...table.tBodies].flatMap(body => [...body.rows].map(row => ({ tag: row.cells[0]?.tagName, scope: row.cells[0]?.getAttribute('scope') })))
  })));
  check(scope('profile_table_semantics', item), semantics.every(table => table.name && table.column_scopes.every(value => value === 'col') && table.row_headers.every(value => value.tag === 'TH' && value.scope === 'row')), { semantics }, 'after');
  for (const selector of ['#lojas', '#receita', '#produtos']) await openDetails(page, selector);
  const indicatorTables = await tables(page, '#indicadores');
  for (const [label, expected] of [
    ['Receita, unidades, vendas e ticket por loja e dia comercial', (payload.stores || []).map(row => [date(row.business_date), String(row.store_id ?? '—'), money(row.net_revenue_brl), integer(row.units), integer(row.sales_count), money(row.average_ticket_brl)])],
    ['Valores equivalentes ao gráfico de receita diária', (payload.daily || []).map(row => [date(row.business_date), money(row.net_revenue_brl)])],
    ['Produtos mais vendidos, unidades e receita líquida', (payload.products || []).map(row => [String(row.product_id ?? '—'), integer(row.units), money(row.net_revenue_brl)])]
  ]) {
    const observed = indicatorTables.find(table => table.name === label);
    equal(scope('exact_indicator_table', item, label), observed?.rows || [], expected);
  }
  const compareTable = (label, expected) => {
    const matches = observedTables.filter(table => table.name === label);
    check(scope('table_present', item, label), matches.length >= 1, { label, count: matches.length });
    if (matches.length) equal(scope('table_data', item, label), matches[0].rows, expected);
  };
  const observedMetrics = await page.locator('.metric strong[data-metric]').evaluateAll(elements => Object.fromEntries(elements.map(element => [element.dataset.metric, element.textContent.trim()])));
  equal(scope('summary_metrics', item), observedMetrics, payload.snapshot ? {
    net_revenue: money(payload.summary?.net_revenue_brl), units: integer(payload.summary?.units),
    sales_count: integer(payload.summary?.sales_count), average_ticket_brl: money(payload.summary?.average_ticket_brl)
  } : {});
  for (const [id, expected] of [['publication-id', payload.snapshot?.publication_id], ['attempt-batch-id', payload.latest_attempt?.batch_id], ['profile-baseline-id', payload.profile_result?.profile?.comparison?.baseline_publication_id]]) {
    const input = page.locator('#' + id);
    if (expected != null && await input.count()) equal(scope('identity', item, id), await input.inputValue(), String(expected));
  }
  const state = profileStatus(payload);
  if (state !== 'AVAILABLE') {
    equal(scope('profile_unavailable_state', item), normalize(await page.locator('#perfil .profile-state').textContent()), (constants.profileStates[state] || state) + '.');
    equal(scope('profile_unavailable_no_fabricated_tables', item), observedTables.length, 0);
    return;
  }
  const profile = payload.profile_result.profile;
  const lexicalProfile = item.lexicalPayload.profile_result?.profile || profile;
  const active = profile.active_state || {};
  const comparison = profile.comparison || {};
  const versionTables = observedTables.filter(table => table.name === 'Versões Delta fixadas no perfil');
  for (const [name, references] of [['active', profile.delta_versions], ['baseline', comparison.baseline_delta_versions]]) {
    if (references && Object.keys(references).length) {
      const expected = Object.entries(references).slice(0, 10).map(([key, reference]) => [key, integer(reference?.version), String(reference?.path ?? '—')]);
      check(scope('fixed_delta_versions', item, name), versionTables.some(table => JSON.stringify(table.rows) === JSON.stringify(expected)), { expected, observed: versionTables.map(table => table.rows) });
    }
  }
  const totalRows = totals => constants.totals.map(([key, label, kind]) => [label, (kind === 'money' ? money : integer)(totals?.[key])]);
  compareTable('Totais exatos do perfil ativo publicado', totalRows(active.totals));
  compareTable('Mínimos, máximos e médias das linhas ativas', Object.entries(constants.distributions).map(([key, label]) => {
    const values = active.distributions?.[key] || {};
    return [label, exact(values.min), exact(values.max), exact(values.mean)];
  }));
  const quantiles = Object.entries(constants.distributions).flatMap(([key, label]) => (lexicalProfile.active_state?.distributions?.[key]?.quantiles || []).slice(0, constants.quantileLimit).map(value => [label, exact(value.probability), exact(value.value)]));
  if (quantiles.length) compareTable('Quantis aproximados persistidos no perfil', quantiles);
  for (const [key, id, label] of [['stores', 'store_id', 'loja'], ['products', 'product_id', 'produto']]) {
    const values = (active.groups?.[key]?.values || []).slice(0, constants.groupLimit);
    if (values.length) compareTable('Contribuição publicada por ' + label + '; grupos limitados', values.map(value => [
      String(value[id] ?? '—'), integer(value.active_lines), integer(value.sales), integer(value.units), money(value.net_revenue_brl)
    ]));
  }
  if (profile.state_changes && Object.keys(profile.state_changes).length) compareTable('Alterações definidas pelo perfil', [
    ['new_keys', 'Itens novos'], ['revised_keys', 'Itens revisados'], ['cancelled_keys', 'Itens cancelados'],
    ['reactivated_keys', 'Itens reativados'], ['effective_changes', 'Alterações efetivas']
  ].map(([key, label]) => [label, integer(profile.state_changes[key])]));
  if (profile.batch && Object.keys(profile.batch).length) compareTable('Contagens do lote recebido; separadas do estado ativo', [
    [profile.batch.stats, 'received', 'Registros recebidos'], [profile.batch.stats, 'valid', 'Registros válidos'],
    [profile.batch.stats, 'rejected', 'Registros rejeitados'], [profile.batch.received_operations, 'valid_cancel_events', 'Eventos CANCEL válidos recebidos'],
    [profile.batch.received_operations, 'valid_revision_gt1_events', 'Eventos válidos com revisão maior que 1']
  ].map(([source, key, label]) => [label, integer(source?.[key])]));
  for (const [key, label] of [['original_totals', 'Totais originais das publicações anterior e atual'], ['equivalent_totals', 'Totais equivalentes nas versões Delta das duas publicações']]) {
    if (comparison[key] && Object.keys(comparison[key]).length) compareTable(label, constants.totals.map(([field, name, kind]) => {
      const format = kind === 'money' ? money : integer;
      return [name, format(comparison[key].previous?.[field]), format(comparison[key].current?.[field])];
    }));
  }
  const rules = (comparison.rules || []).slice(0, constants.quantileLimit);
  const ruleRows = rules.map(rule => [
    constants.rules[rule.metric] || String(rule.metric),
    rule.severity === 'WARNING' ? 'Aviso (WARNING)' : constants.ruleStates[rule.status] || String(rule.status),
    ...['previous', 'current', 'difference', 'relative_change', 'threshold'].map(key => exact(rule[key])), String(rule.reason ?? '—')
  ]);
  if (rules.length) {
    compareTable('Valores e motivos das regras no recorte equivalente', ruleRows);
    const observed = observedTables.find(table => table.name === 'Valores e motivos das regras no recorte equivalente');
    equal(scope('rule_table_eight_columns', item), observed?.headers.length, 8);
    if (phase === 'after') {
      if (typeof comparison.warnings === 'number' && Number.isInteger(comparison.warnings) && comparison.warnings >= 0) {
        equal(scope('warning_count', item), await page.locator('[data-profile-warning-count]').getAttribute('data-profile-warning-count'), String(comparison.warnings));
      }
      for (const rule of rules) {
        const card = page.locator('[data-profile-rule][data-profile-metric="' + attr(rule.metric) + '"]');
        equal(scope('card_count', item, rule.metric), await card.count(), 1);
        if (!await card.count()) continue;
        for (const field of ['previous', 'current', 'difference', 'relative_change', 'threshold']) {
          const value = card.locator('[data-profile-value="' + field + '"]');
          equal(scope('card_raw_decimal', item, rule.metric + '/' + field), await value.getAttribute('data-value-raw'), rule[field] == null ? null : String(rule[field]));
          equal(scope('card_display_decimal', item, rule.metric + '/' + field), normalize(await value.textContent()), ['relative_change', 'threshold'].includes(field) ? percentage(rule[field]) : exact(rule[field]));
        }
        equal(scope('card_reason', item, rule.metric), normalize(await card.locator('.profile-rule-reason').textContent()), normalize(rule.reason));
      }
      const ordered = await page.locator('[data-profile-rule]').first().getAttribute('data-profile-metric');
      const warning = rules.find(rule => rule.severity === 'WARNING');
      if (warning) equal(scope('warning_first', item), ordered, warning.metric);
    } else check(scope('cards_after_only', item), true, { status: 'Not implemented in BEFORE; existing eight-column data verified.' }, 'observe');
  }
  if (comparison.baseline_publication_id != null) {
    const context = comparison.context || {};
    const facts = await page.locator('#profile-comparison > .profile-context > div').evaluateAll(elements => Object.fromEntries(elements.map(element => [element.querySelector('dt')?.textContent.trim(), element.querySelector('dd')?.textContent.trim()])));
    equal(scope('previous_period', item), normalize(facts['Período anterior']), dateRange(context.previous_date_range));
    equal(scope('current_period', item), normalize(facts['Período atual']), dateRange(context.current_date_range));
    for (const [label, values] of [['Lojas acrescentadas', context.stores_added], ['Lojas removidas', context.stores_removed]]) {
      const text = normalize(facts[label]);
      check(scope('store_context', item, label), chips(values, constants.groupLimit).every(value => text.includes(value)), { expected: chips(values, constants.groupLimit), actual: text });
    }
  }
  if (comparison.scope && Object.keys(comparison.scope).length) {
    const scopeText = normalize(await page.locator('#profile-comparison .profile-scope').textContent());
    check(scope('comparison_scope', item), scopeText.includes(dateRange(comparison.scope.dates)) && chips(comparison.scope.stores, constants.groupLimit).every(value => scopeText.includes(value)), { expected_period: dateRange(comparison.scope.dates), expected_stores: chips(comparison.scope.stores, constants.groupLimit), actual: scopeText });
  }
  // Explicit immutable demonstration anchors, independent of the renderer labels.
  if (item.name === 'actual-comparable') {
    equal(scope('accepted_revenue_anchor', item), profile.active_state.totals.net_revenue_brl, '104.00');
    equal(scope('baseline_revenue_anchor', item), comparison.equivalent_totals.previous.net_revenue_brl, '64.00');
    const price = rules.find(rule => rule.metric === 'unit_price_mean_brl');
    equal(scope('price_anchors', item), [price?.previous, price?.current, price?.difference], ['9.642857', '15.357143', '5.714286']);
  }
  item.expected_profile = { status: state, comparison_status: comparison.status, rules: rules.length, groups: active.groups, exact_table_rows: observedTables.reduce((sum, table) => sum + table.rows.length, 0) };
}

async function focusCheck(page, locator, item, label) {
  if (!await locator.count() || !await locator.isVisible()) return;
  await locator.focus();
  const evidence = await locator.evaluate(element => {
    const style = getComputedStyle(element), box = element.getBoundingClientRect();
    const left = Math.max(0, box.left), right = Math.min(innerWidth, box.right);
    const top = Math.max(0, box.top), bottom = Math.min(innerHeight, box.bottom);
    const points = [[(left + right) / 2, (top + bottom) / 2], [left + 1, top + 1], [right - 1, bottom - 1]];
    const exposed = right > left && bottom > top && points.some(([x, y]) => {
      const hit = document.elementFromPoint(x, y); return hit && (element === hit || element.contains(hit));
    });
    return { focused: document.activeElement === element, exposed, outline: style.outlineStyle,
      outline_width: style.outlineWidth, outline_color: style.outlineColor, shadow: style.boxShadow,
      rect: { left: box.left, top: box.top, width: box.width, height: box.height } };
  });
  check(scope('focus_visible', item, label), evidence.focused && (parseFloat(evidence.outline_width) > 0 && evidence.outline !== 'none' || evidence.shadow !== 'none'), evidence, 'after');
  check(scope('focus_not_entirely_obscured', item, label), evidence.exposed, evidence, 'after');
}
async function keyboardJourney(page, item) {
  await loaded(page, item, '#qualidade');
  await view(page, 'indicadores');
  equal(scope('keyboard_panel_focus', item), await page.evaluate(() => document.activeElement.id), 'indicadores');
  await view(page, 'proveniencia');
  await page.goBack();
  await page.locator('[data-view-link="indicadores"][aria-current]').waitFor({ state: 'visible' });
  equal(scope('history_back', item), await page.locator('[data-report-view]:visible').getAttribute('id'), 'indicadores');
  await page.goForward();
  await page.locator('[data-view-link="proveniencia"][aria-current]').waitFor({ state: 'visible' });
  equal(scope('history_forward', item), await page.locator('[data-report-view]:visible').getAttribute('id'), 'proveniencia');
  for (const id of ['indicadores', 'proveniencia']) {
    await view(page, id);
    await page.locator('.skip-link').focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'content');
    equal(scope('skip_keeps_view', item, id), await page.locator('[data-report-view]:visible').getAttribute('id'), id);
    equal(scope('skip_hash', item, id), new URL(page.url()).hash, '#content');
    await page.goBack();
    await page.locator('[data-view-link="' + id + '"][aria-current]').waitFor({ state: 'visible' });
    equal(scope('skip_back', item, id), new URL(page.url()).hash, '#' + id);
  }
  await loaded(page, item, '#perfil');
  check(scope('profile_deep_link', item), await page.locator('#perfil').isVisible(), {});
  await page.locator('a[href="#perfil"]').first().focus(); await page.keyboard.press('Enter');
  equal(scope('profile_anchor_focus', item), await page.evaluate(() => document.activeElement.id), 'perfil');
  await openDetails(page, '#perfil');
  const details = page.locator('#perfil details').first();
  if (await details.count()) {
    const summary = details.locator(':scope > summary');
    const previous = await details.evaluate(element => element.open);
    await summary.focus(); await page.keyboard.press('Enter');
    equal(scope('native_disclosure_keyboard', item), await details.evaluate(element => element.open), !previous);
    await summary.focus(); await page.keyboard.press('Enter');
  }
  const targetIds = await page.locator('[data-copy-target]').evaluateAll(elements => elements.map(element => element.dataset.copyTarget));
  for (const id of targetIds) {
    await loaded(page, item, '#' + encodeURIComponent(id));
    const field = page.locator('[id="' + attr(id) + '"]');
    const button = page.locator('[data-copy-target="' + attr(id) + '"]');
    if (!await field.count()) { check(scope('copy_target_exists', item, id), false); continue; }
    const expected = await field.inputValue();
    await page.evaluate(() => {
      window.__reviewCopied = null;
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async text => { window.__reviewCopied = text; } } });
    });
    await button.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(text => window.__reviewCopied === text, expected);
    equal(scope('copy_intercepted_exact', item, id), await page.evaluate(() => window.__reviewCopied), expected);
    await page.evaluate(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
      document.execCommand = () => false;
    });
    await button.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(target => document.activeElement.id === target, id);
    equal(scope('copy_fallback_full_selection', item, id), await field.evaluate(element => element.selectionEnd - element.selectionStart), expected.length);
    const status = await button.getAttribute('data-copy-status') || 'copy-status';
    check(scope('copy_fallback_instruction', item, id), (await page.locator('[id="' + attr(status) + '"]').textContent()).includes('Ctrl+C'), { status });
  }
  await loaded(page, item, '#indicadores');
  const cells = page.locator('[data-heat-cell]');
  if (await cells.count()) {
    equal(scope('matrix_single_tabstop', item), await page.locator('[data-heat-cell][tabindex="0"]').count(), 1);
    const first = cells.first(); await first.focus();
    const firstColumn = Number(await first.getAttribute('data-column'));
    if (await page.locator('[data-heat-cell][data-row="0"][data-column="' + (firstColumn + 1) + '"]').count()) {
      await page.keyboard.press('ArrowRight');
      equal(scope('matrix_arrow', item), await page.locator('[data-heat-cell][aria-current]').getAttribute('data-column'), String(firstColumn + 1));
    }
    await page.keyboard.press('End');
    const active = page.locator('[data-heat-cell][aria-current]');
    equal(scope('matrix_exact_output', item), await page.locator('#matrix-value').textContent(), await active.getAttribute('data-value'));
    const target = await active.getAttribute('href');
    await page.locator('#matrix-record').focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(id => document.activeElement.id === id, target.slice(1));
    check(scope('matrix_exact_table_destination', item), await page.locator('#store-values').evaluate(element => element.open), { target });
  }
  // Exercise the native Tab order rather than only programmatic focus.
  await loaded(page, item, '#qualidade');
  const stops = [];
  await page.locator('[data-view-link="qualidade"]').focus();
  for (let index = 0; index < 12; index++) {
    await page.keyboard.press('Tab');
    stops.push(await page.evaluate(() => ({ tag: document.activeElement.tagName, id: document.activeElement.id, hidden: !!document.activeElement.closest('[hidden]') })));
  }
  await page.keyboard.press('Shift+Tab');
  check(scope('tab_order_never_hidden', item), stops.every(stop => !stop.hidden), { stops });
  result.journeys.push({ name: item.name, history: true, native_disclosures: true, intercepted_copy_and_manual_fallback: targetIds.length, matrix_cells: await cells.count(), tab_stops: stops.length });
}
async function layout(page, item, width, id, state = 'default') {
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  const record = { name: item.name, width, view: id, state, ...dimensions };
  if (id === 'indicadores') record.rule_table_layout = await page.locator('#profile-comparison .table-scroll').evaluateAll(elements => elements.filter(element => element.getAttribute('aria-label') === 'Valores e motivos das regras no recorte equivalente').map(element => ({
    region_width: element.clientWidth, table_width: element.querySelector('table').getBoundingClientRect().width, scroll_width: element.scrollWidth,
    appendix: !!element.closest('.profile-rules-table'), header_labels: [...element.querySelectorAll('thead th')].map(header => header.textContent.trim())
  })));
  result.layouts.push(record);
  check(scope('page_overflow', item, width + '/' + id + '/' + state), dimensions.document <= dimensions.viewport + 1, record, 'after');
  if (id === 'indicadores' && phase === 'after' && (item.payload.profile_result?.profile?.comparison?.rules || []).length && profileStatus(item.payload) === 'AVAILABLE') {
    const evidence = await page.locator('[data-profile-rule]').evaluateAll(cards => cards.map(card => {
      const box = card.getBoundingClientRect();
      const values = [...card.querySelectorAll('[data-profile-value],.profile-rule-reason')].map(element => {
        const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
        return { name: element.dataset.profileValue || 'reason', text: element.textContent.trim(),
          left: rect.left, right: rect.right, width: rect.width, scroll_width: element.scrollWidth,
          client_width: element.clientWidth, visible: !!element.getClientRects().length && style.visibility !== 'hidden',
          clipped: element.scrollWidth > element.clientWidth + 1 && ['hidden', 'clip'].includes(style.overflowX) };
      });
      return { metric: card.dataset.profileMetric, left: box.left, right: box.right, values };
    }));
    check(scope('main_rule_values_mobile', item, width), evidence.length > 0 && evidence.every(card => card.left >= -1 && card.right <= width + 1 && card.values.length === 6 && card.values.every(value => value.visible && value.left >= -1 && value.right <= width + 1 && !value.clipped && value.scroll_width <= value.client_width + 1)), { evidence }, 'after');
    const order = await page.evaluate(() => {
      const list = document.querySelector('.profile-rule-list');
      return ['.profile-context', '.profile-scope'].map(selector => {
        const element = document.querySelector('#profile-comparison > ' + selector);
        return { selector, exists: !!element, precedes: !element || !!(element.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING) };
      });
    });
    check(scope('profile_context_before_rules', item, width), order.every(part => part.precedes), { order }, 'after');
    const callout = page.locator('[data-profile-warning-count]');
    if (await callout.count()) {
      const announcements = await callout.evaluate(element => ({ role: element.getAttribute('role'), live: element.getAttribute('aria-live') }));
      check(scope('historical_warning_not_live', item, width), announcements.role !== 'alert' && !announcements.live, announcements, 'after');
    }
  }
}
async function targetChecks(page, item, width, id) {
  const targets = await page.locator('a[href]:visible,button:visible,summary:visible').evaluateAll(elements => {
    const records = elements.map(element => {
      const box = element.getBoundingClientRect(), style = getComputedStyle(element);
      return { label: element.getAttribute('aria-label') || element.textContent.trim().slice(0, 110), tag: element.tagName,
        left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height,
        inline_exception: style.display === 'inline' && !element.closest('nav,.decision-actions,.matrix-reading'), skip: element.classList.contains('skip-link') };
    }).filter(record => record.width > 0 && record.height > 0 && !record.skip);
    return records.map((record, index) => {
      if (record.width >= 24 && record.height >= 24) return { ...record, outcome: 'rectangle_minimum' };
      if (record.inline_exception) return { ...record, outcome: 'inline_exception' };
      const cx = (record.left + record.right) / 2, cy = (record.top + record.bottom) / 2;
      const clashes = records.flatMap((other, otherIndex) => {
        if (otherIndex === index) return [];
        const dx = Math.max(other.left - cx, 0, cx - other.right), dy = Math.max(other.top - cy, 0, cy - other.bottom);
        const rectangleClash = dx * dx + dy * dy < 144;
        const undersized = other.width < 24 || other.height < 24;
        const ocx = (other.left + other.right) / 2, ocy = (other.top + other.bottom) / 2;
        const circleClash = undersized && (ocx - cx) ** 2 + (ocy - cy) ** 2 < 576;
        return rectangleClash || circleClash ? [other.label] : [];
      });
      return { ...record, outcome: clashes.length ? 'requires_fix_or_verified_exception' : 'spacing_exception', clashes };
    });
  });
  result.targets.push({ name: item.name, width, view: id, targets });
  check(scope('target_layout_24', item, width + '/' + id), targets.every(target => target.outcome !== 'requires_fix_or_verified_exception'), { failing: targets.filter(target => target.outcome === 'requires_fix_or_verified_exception') }, 'after');
}
async function colorAndFontSamples(page, item, width, id) {
  const samples = await page.evaluate(() => {
    const selectors = ['.report-nav a[aria-current]', '.page-heading h1', '.publication-bridge', '.publication-heading h2', '.metric strong',
      '.meta', '.profile-decision h4', '.profile-rule h5', '.profile-rule-reason', '[data-profile-value]', '.issue > summary'];
    const rgba = value => {
      const values = value.match(/[\d.]+/g)?.map(Number);
      return values && values.length >= 3 ? [values[0], values[1], values[2], values[3] ?? 1] : null;
    };
    const compose = (front, back) => [...front.slice(0, 3).map((value, index) => value * front[3] + back[index] * (1 - front[3])), 1];
    return selectors.flatMap(selector => [...document.querySelectorAll(selector)].filter(element => element.getClientRects().length && element.closest('[hidden]') == null).slice(0, 5).map(element => {
      const style = getComputedStyle(element);
      const backgrounds = []; let ancestor = element, uncertain = false;
      while (ancestor) {
        const current = getComputedStyle(ancestor); backgrounds.push(rgba(current.backgroundColor));
        uncertain ||= current.backgroundImage !== 'none' || Number(current.opacity) !== 1;
        ancestor = ancestor.parentElement;
      }
      const background = backgrounds.reverse().filter(Boolean).reduce((back, front) => compose(front, back), [255, 255, 255, 1]);
      const foreground = rgba(style.color);
      return { selector, text: element.textContent.trim().slice(0, 120), foreground: foreground && compose(foreground, background), background,
        font_size: parseFloat(style.fontSize), font_weight: Number(style.fontWeight), font_family: style.fontFamily,
        font_variant_numeric: style.fontVariantNumeric, uncertain };
    }));
  });
  const luminance = color => color.slice(0, 3).map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
    .reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  for (const sample of samples) {
    if (sample.foreground) {
      const a = luminance(sample.foreground), b = luminance(sample.background);
      sample.ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
      sample.required = sample.font_size >= 24 || sample.font_size >= 18.6666667 && sample.font_weight >= 700 ? 3 : 4.5;
    }
  }
  result.contrast.push({ name: item.name, width, view: id, samples });
  check(scope('computed_text_contrast', item, width + '/' + id), samples.every(sample => sample.uncertain || sample.ratio == null || sample.ratio >= sample.required), { failing: samples.filter(sample => !sample.uncertain && sample.ratio < sample.required), manual: samples.filter(sample => sample.uncertain).length }, 'after');
  const numerals = await page.locator('.numeric:visible,.metric strong:visible,[data-profile-value]:visible').evaluateAll(elements => elements.slice(0, 30).map(element => ({
    text: element.textContent.trim(), font_family: getComputedStyle(element).fontFamily, font_variant_numeric: getComputedStyle(element).fontVariantNumeric
  })));
  result.fonts.push({ name: item.name, width, view: id, document_fonts_loaded: await page.evaluate(() => document.fonts.status), numerals });
  check(scope('numeric_tabular_font', item, width + '/' + id), numerals.every(sample => sample.font_variant_numeric.includes('tabular-nums')), { failing: numerals.filter(sample => !sample.font_variant_numeric.includes('tabular-nums')) }, 'after');
}
function compactAxe(rule) {
  return { id: rule.id, impact: rule.impact, description: rule.description, help: rule.help, helpUrl: rule.helpUrl,
    nodes: rule.nodes.map(node => ({ target: node.target, failureSummary: node.failureSummary })) };
}
async function axe(page, item, width, id, expanded) {
  const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  const record = { name: item.name, width, view: id, expanded_profile: expanded, engine: scan.testEngine,
    violations: scan.violations.map(compactAxe), incomplete: scan.incomplete.map(compactAxe), passed_rule_count: scan.passes.length };
  result.accessibility.push(record);
  check(scope('axe_wcag22aa', item, width + '/' + id + '/' + expanded), record.violations.length === 0,
    { violations: record.violations.length, incomplete_manual_review: record.incomplete.length }, 'after');
}
async function textSpacing(page, item) {
  await page.setViewportSize({ width: 320, height: 900 });
  await loaded(page, item);
  await page.addStyleTag({ content: '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-block-end:2em!important}' });
  for (const id of views) {
    await view(page, id);
    if (id === 'indicadores') await openDetails(page, '#perfil');
    await layout(page, item, 320, id, 'text_spacing_override');
    const clipping = await page.locator('button:visible,summary:visible,.profile-rule-reason:visible,[data-profile-value]:visible,.profile-state:visible').evaluateAll(elements => elements.map(element => {
      const style = getComputedStyle(element);
      return { label: element.textContent.trim().slice(0, 100), scroll_width: element.scrollWidth, client_width: element.clientWidth,
        scroll_height: element.scrollHeight, client_height: element.clientHeight, overflow_x: style.overflowX, overflow_y: style.overflowY };
    }).filter(element => element.scroll_width > element.client_width + 1 && ['hidden', 'clip'].includes(element.overflow_x) || element.scroll_height > element.client_height + 1 && ['hidden', 'clip'].includes(element.overflow_y)));
    check(scope('text_spacing_no_clipping', item, id), clipping.length === 0, { clipping }, 'after');
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const motion = await page.locator('.report-nav a').first().evaluate(element => ({
    reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    duration: getComputedStyle(element, '::after').transitionDuration, animation: getComputedStyle(element, '::after').animationDuration
  }));
  check(scope('reduced_motion', item), motion.reduced && motion.duration.split(',').every(value => parseFloat(value) === 0) && motion.animation.split(',').every(value => parseFloat(value) === 0), motion, 'after');
}
async function noJavaScript(browser, item) {
  const context = await browser.newContext({ javaScriptEnabled: false, offline: true, reducedMotion: 'reduce', viewport: { width: 320, height: 900 } });
  observe(context, item.name, 'no_javascript');
  try {
    const page = await context.newPage(); await loaded(page, item, '#perfil');
    equal(scope('nojs_all_native_views', item), await page.locator('[data-report-view]:visible').count(), 3);
    equal(scope('nojs_no_script_copy_buttons', item), await page.locator('[data-copy-target]:visible').count(), 0);
    await page.locator('a[href="#perfil"]').first().focus(); await page.keyboard.press('Enter');
    await openDetails(page, '#perfil');
    const nativeTables = await tables(page);
    equal(scope('nojs_same_exact_profile_tables', item), nativeTables, item.tables);
    const baseline = page.locator('#profile-baseline-id');
    if (await baseline.count()) {
      await baseline.focus(); await page.keyboard.press('Control+A');
      equal(scope('nojs_native_id_selection', item), await baseline.evaluate(element => element.selectionEnd - element.selectionStart), (await baseline.inputValue()).length);
    }
    check(scope('nojs_global_overflow', item), await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), {}, 'after');
  } finally { await context.close(); }
}
async function screenshot(page, item, width, hash, name, expand = false) {
  await page.setViewportSize({ width, height: 900 }); await loaded(page, item, hash);
  if (expand) await openDetails(page, '#proveniencia');
  await page.mouse.move(0, 0);
  await page.evaluate(() => {
    document.activeElement?.blur();
    const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (target) target.scrollIntoView({ block: 'start', behavior: 'instant' }); else window.scrollTo(0, 0);
  });
  const filename = name + '-' + width + '.png';
  await page.screenshot({ path: path.join(output, 'images', filename), fullPage: false, animations: 'disabled' });
  result.screenshots.push({ name: item.name, phase, width, height: 900, hash, expanded: expand, file: 'images/' + filename, input_sha256: item.input_sha256 });
}
async function main() {
  const browser = await playwright[browserName].launch(browserName === 'chromium' ? { channel: process.env.PLAYWRIGHT_CHANNEL || undefined } : {});
  result.browser_version = browser.version();
  result.playwright_version = require(path.join(playwrightModule, 'package.json')).version;
  try {
    for (const filename of files) {
      const name = path.basename(filename, '.html'), htmlFile = path.join(htmlDirectory, filename), inputFile = path.join(inputDirectory, name + '.json');
      assert.ok(fs.existsSync(inputFile), 'Missing captured payload: ' + name);
      const bytes = fs.readFileSync(inputFile), envelope = JSON.parse(bytes.toString('utf8')), lexicalEnvelope = lexicalJSON(bytes.toString('utf8'));
      const item = { name, payload: envelope.payload || envelope, lexicalPayload: lexicalEnvelope.payload || lexicalEnvelope,
        url: pathToFileURL(htmlFile).href, input_sha256: sha(bytes), html_sha256: sha(fs.readFileSync(htmlFile)), presentation_only: envelope.presentation_only === true };
      result.inputs.push({ name, input: relative(inputFile), html: relative(htmlFile), input_sha256: item.input_sha256, html_sha256: item.html_sha256, presentation_only: item.presentation_only });
      const receipt = manifest?.inputs?.find(value => value.name === name);
      if (receipt) {
        equal(scope('manifest_input_hash', item), item.input_sha256, receipt.input_sha256);
        equal(scope('manifest_html_hash', item), item.html_sha256, receipt.html_sha256);
      } else check(scope('corpus_manifest_receipt', item), false, { manifest: relative(manifestPath) });
      if (phase === 'after') {
        const before = beforeManifest?.inputs?.find(value => value.name === name);
        equal(scope('same_before_payload_bytes', item), item.input_sha256, before?.input_sha256);
      }
      const context = await browser.newContext({ offline: true, reducedMotion: 'reduce', viewport: { width: 1440, height: 900 } });
      context.setDefaultTimeout(10000); observe(context, name, 'javascript');
      try {
        const page = await context.newPage();
        await dataChecks(page, item);
        for (const width of widths) {
          await page.setViewportSize({ width, height: 900 }); await loaded(page, item);
          for (const id of views) {
            await view(page, id);
            equal(scope('one_js_panel', item, width + '/' + id), await page.locator('[data-report-view]:visible').count(), 1);
            equal(scope('native_links_not_aria_tabs', item, width + '/' + id), await page.locator('[role="tab"],[role="tablist"]').count(), 0);
            await layout(page, item, width, id);
            await targetChecks(page, item, width, id);
            if (width === 390 || width === 1440) {
              await colorAndFontSamples(page, item, width, id);
              await axe(page, item, width, id, false);
              if (id === 'indicadores' && profileStatus(item.payload) === 'AVAILABLE') {
                await openDetails(page, '#perfil');
                await axe(page, item, width, id, true);
              }
            }
          }
        }
        await page.setViewportSize({ width: 390, height: 900 });
        await keyboardJourney(page, item);
        await loaded(page, item, '#perfil'); await openDetails(page, '#perfil');
        await focusCheck(page, page.locator('[data-view-link="indicadores"]'), item, 'navigation');
        await focusCheck(page, page.locator('#perfil .table-scroll').first(), item, 'profile_table_scroll');
        await focusCheck(page, page.locator('#perfil summary').first(), item, 'profile_disclosure');
        await textSpacing(page, item);
        await noJavaScript(browser, item);
        if (name === 'actual-comparable') {
          for (const width of widths) {
            await screenshot(page, item, width, '#indicadores', 'comparable-indicadores');
            await screenshot(page, item, width, '#perfil', 'comparable-profile-top');
          }
        }
        if (name === 'historical-blocked-report') for (const width of widths) await screenshot(page, item, width, '#qualidade', 'blocked-qualidade');
        if (name === 'fixture-long') {
          await screenshot(page, item, 320, '#qualidade', 'long-qualidade');
          await screenshot(page, item, 320, '#proveniencia', 'long-arquivos', true);
        }
        if (name === 'fixture-matrix') await screenshot(page, item, 390, '#lojas', 'matrix-indicadores');
        process.stdout.write(JSON.stringify({ phase, browser: browserName, case: name, checks: result.checks.length, completed: true }) + '\n');
      } catch (error) {
        check(scope('harness_completed_case', item), false, { error: safeError(error) });
        process.stderr.write(name + ': ' + safeError(error) + '\n');
      } finally { await context.close(); }
    }
    equal('remote_requests_zero', result.requests.remote, []);
    equal('failed_requests_zero', result.requests.failed, []);
    equal('page_errors_zero', result.requests.errors, []);
    equal('console_errors_zero', result.requests.consoleErrors, []);
    result.finished_at = new Date().toISOString();
    result.summary = {
      cases: result.inputs.length, checks: result.checks.length, screenshots: result.screenshots.length,
      gating_failures: result.checks.filter(item => !item.ok && (item.gate === 'always' || item.gate === 'after' && phase === 'after')).length,
      presentation_findings: result.checks.filter(item => !item.ok && item.gate === 'after').length,
      axe_violations: result.accessibility.reduce((sum, scan) => sum + scan.violations.length, 0),
      axe_incomplete_manual_review: result.accessibility.reduce((sum, scan) => sum + scan.incomplete.length, 0),
      remote_requests: result.requests.remote.length, failed_requests: result.requests.failed.length, page_errors: result.requests.errors.length
    };
    result.completed = result.checks.filter(item => item.name.includes('harness_completed_case') && !item.ok).length === 0;
    fs.writeFileSync(path.join(output, 'uiux-review.json'), JSON.stringify(result, null, 2) + '\n');
    fs.writeFileSync(path.join(output, 'summary.json'), JSON.stringify({ phase, browser: result.browser_version, ...result.summary, limitations: result.limitations }, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ output: relative(output), phase, browser: result.browser_version, ...result.summary }) + '\n');
    if (result.summary.gating_failures) process.exitCode = 1;
  } finally { await browser.close(); }
}
main().catch(error => {
  result.fatal = safeError(error); result.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(output, 'uiux-review.json'), JSON.stringify(result, null, 2) + '\n');
  process.stderr.write(safeError(error) + '\n'); process.exitCode = 1;
});

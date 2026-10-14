/* Development QA for captured dashboards. Never starts Spark or executes batches.
 * Usage: node scripts/dashboard-review.cjs before|after HTML_DIR NEW_OUTPUT_DIR
 * PLAYWRIGHT_MODULE, AXE_MODULE, PLAYWRIGHT_CHANNEL and REVIEW_BROWSER select tools.
 * DASHBOARD_INPUTS and DASHBOARD_CASES optionally select immutable inputs/cases.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {pathToFileURL} = require('node:url');
const browserRequire = require('node:module').createRequire(path.join(__dirname, '../tools/browser/package.json'));
const pw = require(process.env.PLAYWRIGHT_MODULE || browserRequire.resolve('playwright'));
const AxeBuilder = require(process.env.AXE_MODULE || browserRequire.resolve('@axe-core/playwright')).default;
const phase = process.argv[2];
assert.ok(['before', 'after'].includes(phase), 'Expected before or after');
const root = process.cwd();
assert.ok(fs.existsSync(path.join(root, 'pyproject.toml')), 'Run in this repository');
const htmlDirectory = path.resolve(process.argv[3]);
const output = path.resolve(process.argv[4]);
assert.ok(output.startsWith(root + path.sep) && !fs.existsSync(output), 'Use a new output directory in this project');
const inputDirectory = path.resolve(process.env.DASHBOARD_INPUTS || path.join(path.dirname(htmlDirectory), 'inputs'));
const widths = [320, 390, 768, 1024, 1440];
const destinations = ['indicadores', 'lojas', 'perfil', 'qualidade', 'proveniencia'];
const selected = process.env.DASHBOARD_CASES ? new Set(process.env.DASHBOARD_CASES.split(',')) : null;
const files = fs.readdirSync(htmlDirectory).filter(name => name.endsWith('.html') && (!selected || selected.has(name.slice(0, -5)))).sort();
assert.ok(files.length, 'No captured HTML selected');
const browserName = process.env.REVIEW_BROWSER || 'chromium';
assert.ok(['chromium', 'firefox'].includes(browserName));
fs.mkdirSync(path.join(output, 'images'), {recursive: true});
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const relative = file => path.relative(root, file).replaceAll('\\', '/');
const result = {phase, browser: browserName, started_at: new Date().toISOString(), widths,
  script_sha256: sha(fs.readFileSync(__filename)), inputs: [], checks: [], charts: [], axe: [], screenshots: [],
  requests: [], errors: [], limitations: ['Static captured reports only; no new domain execution.',
    'Axe is sampled and incomplete results require manual review.', 'Reflow/text-spacing are not native zoom; screen-reader use is not tested.',
    'Products in this fixture corpus are already aggregated and ordered; generic aggregation is covered by helper unit tests.',
    'Source/input hashes are recorded; external corpus validation establishes their provenance.']};
function check(name, ok, details = {}) {result.checks.push({name, ok: Boolean(ok), details});}
function equal(name, actual, expected) {check(name, JSON.stringify(actual) === JSON.stringify(expected), {actual, expected});}
function numeric(value) {
  const match = String(value).match(/^([+-]?)(\d+)(?:\.(\d+))?$/);
  assert.ok(match, 'Expected an exact decimal string: ' + value);
  return {amount: BigInt(match[2] + (match[3] || '')) * (match[1] === '-' ? -1n : 1n), scale: (match[3] || '').length};
}
function decimalEqual(first, second) {
  const a = numeric(first), b = numeric(second), scale = Math.max(a.scale, b.scale);
  return a.amount * 10n ** BigInt(scale - a.scale) === b.amount * 10n ** BigInt(scale - b.scale);
}
function contrast(a, b) {
  const luminance = color => {
    const channels = color.match(/[\d.]+/g)?.slice(0, 3).map(Number);
    if (!channels || channels.length !== 3) return null;
    return channels.map(value => {const x = value / 255; return x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4;})
      .reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
  };
  const x = luminance(a), y = luminance(b);
  return x == null || y == null ? null : (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}
async function visualSamples(page, name) {
  for (const element of (await page.locator('h2:visible,.metric strong:visible,.chart-caption:visible,.app-bar a:visible').all()).slice(0, 14)) {
    const sample = await element.evaluate(element => {
      const style = getComputedStyle(element);
      let parent = element, background = 'rgb(255, 255, 255)';
      while (parent) {const candidate = getComputedStyle(parent).backgroundColor; if (candidate !== 'rgba(0, 0, 0, 0)' && candidate !== 'transparent') {background = candidate; break;} parent = parent.parentElement;}
      return {text: element.textContent.trim().slice(0, 80), color: style.color, background, size: Number.parseFloat(style.fontSize), weight: Number.parseInt(style.fontWeight, 10)};
    });
    const ratio = contrast(sample.color, sample.background), minimum = sample.size >= 24 || sample.size >= 18.66 && sample.weight >= 700 ? 3 : 4.5;
    check(`${name}:text-contrast`, ratio != null && ratio >= minimum, {...sample, ratio, minimum});
  }
  const link = page.locator('a[href="#perfil"]').first();
  await page.keyboard.press('Tab'); await link.focus();
  const ring = await link.evaluate(element => {
    const style = getComputedStyle(element);
    let parent = element, background = 'rgb(255, 255, 255)';
    while (parent) {const candidate = getComputedStyle(parent).backgroundColor; if (candidate !== 'rgba(0, 0, 0, 0)' && candidate !== 'transparent') {background = candidate; break;} parent = parent.parentElement;}
    return {style: style.outlineStyle, width: Number.parseFloat(style.outlineWidth), color: style.outlineColor, background, visible: element.matches(':focus-visible')};
  });
  check(`${name}:link-focus-visible`, ring.visible && ring.style !== 'none' && ring.width >= 2, ring);
  check(`${name}:link-focus-contrast`, contrast(ring.color, ring.background) >= 3, ring);
}
function sum(values) {
  const parsed = values.map(numeric), scale = Math.max(2, ...parsed.map(value => value.scale));
  const total = parsed.reduce((acc, value) => acc + value.amount * 10n ** BigInt(scale - value.scale), 0n);
  const digits = (total < 0 ? -total : total).toString().padStart(scale + 1, '0');
  return (total < 0 ? '-' : '') + digits.slice(0, -scale) + '.' + digits.slice(-scale);
}
function percent(value, total) {
  const a = numeric(value), b = numeric(total), scale = Math.max(a.scale, b.scale);
  const numerator = a.amount * 10n ** BigInt(scale - a.scale), denominator = b.amount * 10n ** BigInt(scale - b.scale);
  assert.ok(numerator >= 0 && denominator > 0);
  const hundredths = (numerator * 10000n + denominator / 2n) / denominator;
  const digits = hundredths.toString().padStart(3, '0');
  return digits.slice(0, -2) + '.' + digits.slice(-2);
}
function money(value) {
  if (value == null) return '—';
  const parsed = numeric(value), denominator = 10n ** BigInt(parsed.scale);
  const negative = parsed.amount < 0, absolute = negative ? -parsed.amount : parsed.amount;
  const cents = (absolute * 100n + denominator / 2n) / denominator;
  const digits = cents.toString().padStart(3, '0');
  return 'R$ ' + (negative ? '-' : '') + digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ',' + digits.slice(-2);
}
function integer(value) {return value == null ? '—' : String(value).replace(/\B(?=(\d{3})+(?!\d))/g, '.');}
async function deadline(promise, label, milliseconds = 15000) {
  let timer;
  try {return await Promise.race([promise, new Promise((_, reject) => {timer = setTimeout(() => reject(new Error(label + ' timeout')), milliseconds);})]);}
  finally {clearTimeout(timer);}
}
async function loaded(page, url, anchor = '') {
  await page.goto(url + (anchor ? '#' + anchor : ''), {waitUntil: 'load'});
  await page.bringToFront();
  // Wait for the browser's font/layout promise, including contexts without app JS.
  await deadline(page.evaluate(async () => { await document.fonts.ready; }), `fonts ready: ${url}#${anchor}`, 20000);
}
async function visit(page, id) {
  const link = page.locator(`a[href="#${id}"]`).first();
  if (await link.count()) {
    await link.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(id => location.hash === '#' + id && document.getElementById(id) && !document.getElementById(id).closest('[data-report-view]')?.hidden, id, {timeout: 5000});
    await page.locator('#' + id).waitFor({state: 'visible'});
  }
  else if (phase === 'after') throw new Error('Destination missing: ' + id);
}
async function layout(page, name, width, id, spacing = false) {
  const size = await page.evaluate(() => ({viewport: innerWidth, document: document.documentElement.scrollWidth}));
  check(`${name}:layout:${width}:${id}:${spacing}`, size.document <= size.viewport, size);
}
async function moneyLines(page, name, width, spacing = false) {
  for (const metric of ['net_revenue', 'average_ticket_brl']) {
    const element = page.locator(`[data-metric="${metric}"]`);
    const measurement = await element.evaluate(element => {
      const nodes = [], walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let node, content = '';
      while ((node = walker.nextNode())) {nodes.push({node, start: content.length}); content += node.textContent;}
      const first = content.search(/\d/), last = content.search(/\d(?=\D*$)/);
      if (first < 0 || last < 0) return {lines: 0, text: content};
      const begin = nodes.find((item, i) => item.start <= first && (!nodes[i + 1] || nodes[i + 1].start > first));
      const end = nodes.find((item, i) => item.start <= last && (!nodes[i + 1] || nodes[i + 1].start > last));
      const range = document.createRange(); range.setStart(begin.node, first - begin.start); range.setEnd(end.node, last - end.start + 1);
      const rectangles = [...range.getClientRects()].filter(rect => rect.width > .1);
      return {lines: new Set(rectangles.map(rect => Math.round(rect.top))).size, text: content,
        white_space: getComputedStyle(element).whiteSpace, focusable: element.tabIndex >= 0,
        local_scroll: element.scrollWidth > element.clientWidth};
    });
    check(`${name}:money-one-line:${metric}:${width}:${spacing}`, measurement.lines <= 1 && (!measurement.local_scroll || measurement.focusable), measurement);
  }
}
async function openNativeDetails(page) {
  for (const detail of await page.locator('#perfil details').elementHandles()) {
    if (await detail.isVisible() && await detail.getAttribute('open') === null) {
      const summary = await detail.$(':scope > summary');
      if (summary) await summary.click();
    }
  }
}
async function chartChecks(page, name, payload) {
  const charts = page.locator('figure[data-chart]');
  const names = await charts.evaluateAll(elements => elements.map(element => element.dataset.chart));
  const hasData = payload.snapshot && (payload.daily?.length || payload.stores?.length || payload.products?.length);
  for (const [expected, rows] of [['sales-trend', payload.daily], ['store-ranking', payload.stores], ['product-mix', payload.products]]) {
    if (payload.snapshot && rows?.length) check(`${name}:chart:${expected}`, names.includes(expected));
  }
  if (!names.length) {result.charts.push({name, types: [], no_chart_data: !hasData}); return;}
  for (const svg of await charts.locator('svg').all()) {
    check(`${name}:svg-semantics`, await svg.getAttribute('role') === 'img' && await svg.locator('title').count() > 0 && await svg.locator('desc').count() > 0);
  }
  const daily = new Map();
  for (const row of payload.daily || []) {
    const key = row.business_date;
    daily.set(key, daily.has(key) ? null : row.net_revenue_brl);
  }
  const trend = page.locator('figure[data-chart="sales-trend"]');
  const observedDates = new Map();
  for (const element of await trend.locator('[data-chart-date][data-value-raw]').all()) {
    const date = await element.getAttribute('data-chart-date'), value = await element.getAttribute('data-value-raw');
    observedDates.set(date, value);
    check(`${name}:daily:${date}`, daily.get(date) != null && decimalEqual(value, daily.get(date)), {value, expected: daily.get(date)});
  }
  for (const [date, value] of daily) if (value != null) check(`${name}:daily-preserved:${date}`, observedDates.has(date));
  const storeGroups = new Map();
  for (const row of payload.stores || []) {
    const group = storeGroups.get(row.store_id) || {values: [], complete: true};
    if (row.net_revenue_brl == null) group.complete = false;
    else group.values.push(String(row.net_revenue_brl));
    storeGroups.set(row.store_id, group);
  }
  const completeStores = [...storeGroups].filter(([, group]) => group.complete).map(([id, group]) => [id, sum(group.values)]);
  const stores = [...completeStores].sort((a, b) => {
    const delta = numeric(b[1]).amount - numeric(a[1]).amount;
    return delta > 0 ? 1 : delta < 0 ? -1 : a[0].localeCompare(b[0]);
  }).slice(0, 6);
  const storeChart = page.locator('figure[data-chart="store-ranking"]');
  const storeRows = await storeChart.locator('li[data-chart-store][data-value-raw]').evaluateAll(elements => elements.map(element => [element.dataset.chartStore, element.dataset.valueRaw]));
  check(`${name}:store-values`, storeRows.length === stores.length && storeRows.every(([id, value], i) => id === stores[i][0] && decimalEqual(value, stores[i][1])), {actual: storeRows, expected: stores});
  const storeDenominator = await storeChart.count() ? await storeChart.getAttribute('data-share-denominator-raw') : null;
  const storeTotal = sum(completeStores.map(([, value]) => value));
  const storeShares = completeStores.length > 0 && completeStores.every(([, value]) => numeric(value).amount >= 0) && numeric(storeTotal).amount > 0;
  equal(`${name}:store-denominator-presence`, storeDenominator != null, storeShares);
  if (storeDenominator != null) check(`${name}:store-denominator`, decimalEqual(storeDenominator, sum(completeStores.map(([, value]) => value))), {expected: sum(completeStores.map(([, value]) => value)), actual: storeDenominator});
  const storeElements = await storeChart.locator('li[data-chart-store]').all();
  for (let i = 0; i < storeElements.length; i++) {
    const percentage = storeElements[i].locator('[data-share-percent-raw]');
    equal(`${name}:store-percent-presence:${i}`, await percentage.count(), storeShares ? 1 : 0);
    if (storeShares && await percentage.count() === 1) check(`${name}:store-percent:${i}`, decimalEqual(await percentage.getAttribute('data-share-percent-raw'), percent(stores[i][1], storeTotal)));
  }
  const productChart = page.locator('figure[data-chart="product-mix"]');
  const products = new Map();
  for (const element of await productChart.locator('[data-chart-product][data-units-raw]').all()) products.set(await element.getAttribute('data-chart-product'), await element.getAttribute('data-units-raw'));
  const knownProducts = (payload.products || []).filter(row => row.units != null);
  const expectedProducts = knownProducts.slice(0, 5);
  check(`${name}:product-values`, products.size === expectedProducts.length && expectedProducts.every(row => products.has(row.product_id) && decimalEqual(products.get(row.product_id), row.units)), {actual: [...products], expected: expectedProducts.map(row => [row.product_id, row.units])});
  const remainder = productChart.locator('[data-chart-product-group="remaining"][data-units-raw]').first();
  if (knownProducts.length > 5) check(`${name}:remaining-products`, await remainder.count() === 1 && decimalEqual(await remainder.getAttribute('data-units-raw'), sum(knownProducts.slice(5).map(row => row.units))));
  const denominator = await productChart.count() ? await productChart.getAttribute('data-share-denominator-raw') : null;
  const productTotal = sum(knownProducts.map(row => row.units));
  const productShares = knownProducts.length > 0 && knownProducts.every(row => numeric(row.units).amount >= 0) && numeric(productTotal).amount > 0;
  equal(`${name}:product-denominator-presence`, denominator != null, productShares);
  if (denominator != null) check(`${name}:product-denominator`, decimalEqual(denominator, sum(knownProducts.map(row => row.units))), {expected: sum(knownProducts.map(row => row.units)), actual: denominator});
  for (const row of await productChart.locator('li[data-units-raw]').all()) {
    const percentage = row.locator('[data-share-percent-raw]');
    equal(`${name}:product-percent-presence`, await percentage.count(), productShares ? 1 : 0);
    if (productShares && await percentage.count() === 1) check(`${name}:product-percent`, decimalEqual(await percentage.getAttribute('data-share-percent-raw'), percent(await row.getAttribute('data-units-raw'), productTotal)));
  }
  result.charts.push({name, types: names, daily_points: observedDates.size, store_groups: storeRows.length, product_groups: products.size});
}
async function dataChecks(page, name, payload) {
  await visit(page, 'indicadores');
  const body = (await page.locator('body').innerText()).replaceAll('\u00a0', ' ');
  if (payload.snapshot && payload.summary?.net_revenue_brl != null) check(`${name}:published-revenue`, body.includes(money(payload.summary.net_revenue_brl)), {expected: money(payload.summary.net_revenue_brl)});
  if (!payload.snapshot) check(`${name}:no-fabricated-money`, !await page.locator('#indicadores').innerText().then(text => /R\$\s*0,00/.test(text)));
  if (phase === 'after') {
    for (const [metric, expected] of [
      ['net_revenue', payload.snapshot ? money(payload.summary?.net_revenue_brl) : '—'],
      ['units', payload.snapshot ? integer(payload.summary?.units) : '—'],
      ['sales_count', payload.snapshot ? integer(payload.summary?.sales_count) : '—'],
      ['average_ticket_brl', payload.snapshot ? money(payload.summary?.average_ticket_brl) : '—'],
    ]) equal(`${name}:kpi:${metric}`, await page.locator(`[data-metric="${metric}"]`).innerText(), expected);
    await chartChecks(page, name, payload);
  }
  await visit(page, 'perfil');
  await openNativeDetails(page);
  const profile = payload.profile_result?.profile;
  for (const rule of profile?.comparison?.rules || []) {
    const matching = page.locator('[data-profile-metric]').filter({has: page.locator('[data-profile-value]')});
    const cards = [];
    for (const element of await matching.all()) if (await element.getAttribute('data-profile-metric') === rule.metric) cards.push(element);
    equal(`${name}:profile-rule-cardinality:${rule.metric}`, cards.length, 1);
    for (const element of cards) {
      for (const field of ['previous', 'current', 'difference', 'relative_change', 'threshold']) {
        const fields = element.locator(`[data-profile-value="${field}"]`);
        const values = element.locator(`[data-profile-value="${field}"][data-value-raw]`);
        equal(`${name}:profile-field-cardinality:${rule.metric}:${field}`, await fields.count(), 1);
        equal(`${name}:profile-raw-cardinality:${rule.metric}:${field}`, await values.count(), rule[field] == null ? 0 : 1);
        if (rule[field] == null && await fields.count() === 1) equal(`${name}:profile-unavailable:${rule.metric}:${field}`, await fields.innerText(), '—');
        for (const value of await values.all()) check(`${name}:profile:${rule.metric}:${field}`, rule[field] != null && decimalEqual(await value.getAttribute('data-value-raw'), rule[field]));
      }
    }
  }
  for (const table of await page.locator('table:visible').all()) check(`${name}:table-caption`, await table.locator('caption').count() === 1 && await table.locator('th').count() > 0);
}
async function capture(browser, item, width, id, label) {
  const context = await browser.newContext({offline: true, reducedMotion: 'reduce', viewport: {width, height: 900}});
  try {
    const page = await context.newPage();
    await loaded(page, pathToFileURL(path.join(root, item.html)).href, id);
    const file = `${item.name}-${label}-${width}.png`;
    await page.screenshot({path: path.join(output, 'images', file), fullPage: false, animations: 'disabled'});
    result.screenshots.push({name: item.name, width, id, normal_text_spacing: true, fresh_context: true, file: 'images/' + file, sha256: sha(fs.readFileSync(path.join(output, 'images', file)))});
  } finally {await context.close();}
}
async function main() {
  const browser = await pw[browserName].launch(browserName === 'chromium' ? {channel: process.env.PLAYWRIGHT_CHANNEL || undefined} : {});
  result.browser_version = browser.version();
  try {
    for (const file of files) {
      const name = file.slice(0, -5), html = path.join(htmlDirectory, file), input = path.join(inputDirectory, name + '.json');
      const raw = fs.readFileSync(input), envelope = JSON.parse(raw), payload = envelope.payload || envelope;
      const item = {name, html: relative(html), input: relative(input), input_sha256: sha(raw), html_sha256: sha(fs.readFileSync(html)), presentation_only: envelope.presentation_only === true};
      result.inputs.push(item);
      const context = await browser.newContext({offline: true, reducedMotion: 'reduce', viewport: {width: 1440, height: 900}});
      await context.addInitScript(() => Object.defineProperty(navigator, 'clipboard', {value: undefined}));
      context.setDefaultTimeout(5000);
      const page = await context.newPage();
      page.on('request', request => {if (/^https?:/.test(request.url())) result.requests.push(request.url());});
      page.on('pageerror', error => result.errors.push(String(error)));
      try {
        await loaded(page, pathToFileURL(html).href);
        if (phase === 'after') {
          const expectedDefault = ['BLOCKED', 'TECHNICAL_FAILURE', 'RUNNING'].includes(payload.latest_attempt?.state) || payload.latest_attempt?.audit_incomplete ? 'qualidade' : 'indicadores';
          equal(`${name}:default-view`, await page.locator('[data-view-link][aria-current="page"]').getAttribute('data-view-link'), expectedDefault);
        }
        await dataChecks(page, name, payload);
        if (phase === 'after') equal(`${name}:profile-heading`, await page.locator('#profile-title').evaluate(element => element.tagName), 'H2');
        for (const width of widths) {
          await page.setViewportSize({width, height: 900});
          for (const id of destinations) {
            await visit(page, id);
            await layout(page, name, width, id);
            if (phase === 'after' && id === 'indicadores') await moneyLines(page, name, width);
            if (phase === 'after') {
              const active = await page.evaluate(() => document.activeElement?.id);
              check(`${name}:destination:${width}:${id}`, await page.locator('#' + id).isVisible(), {focused_id: active});
            }
          }
        }
        if (phase === 'after') {
          await loaded(page, pathToFileURL(html).href, 'lojas');
          check(`${name}:direct-link`, await page.locator('#lojas').isVisible());
          await visit(page, 'perfil'); await page.goBack();
          await page.locator('#lojas').waitFor({state: 'visible'});
          check(`${name}:history`, await page.locator('#lojas').isVisible());
          await page.setViewportSize({width: 320, height: 900});
          const override = await page.addStyleTag({content: '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}'});
          for (const id of destinations) {
            await visit(page, id); await layout(page, name, 320, id, true);
            if (id === 'indicadores') await moneyLines(page, name, 320, true);
          }
          await override.evaluate(element => element.remove());
          await loaded(page, pathToFileURL(html).href, 'indicadores');
          await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab');
          if (['actual-comparable', 'historical-demo30k-report'].includes(name)) {
            await page.setViewportSize({width: 1440, height: 900}); await visit(page, 'indicadores');
            await visualSamples(page, name);
            const primary = await page.locator('figure[data-chart="sales-trend"]').boundingBox();
            check(`${name}:analysis-first-viewport`, primary && primary.y < 900 && primary.y + primary.height > 0, primary || {});
            for (const id of ['indicadores', 'perfil']) {
              await page.setViewportSize({width: 390, height: 900}); await visit(page, id);
              const scan = await deadline(new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze(), 'axe scan', 20000);
              result.axe.push({name, id, violations: scan.violations, incomplete: scan.incomplete});
              check(`${name}:axe:${id}`, scan.violations.length === 0);
            }
          }
        }
        if (name === 'actual-comparable') {
          for (const width of [1440, 390, 320]) await capture(browser, item, width, 'indicadores', 'overview');
          for (const width of [1440, 390]) await capture(browser, item, width, 'perfil', 'comparison');
          await capture(browser, item, 320, 'proveniencia', 'files');
        }
        if (name === 'historical-demo30k-report') {
          for (const width of [1440, 390]) await capture(browser, item, width, 'indicadores', 'overview');
          await capture(browser, item, 1440, 'perfil', 'comparison');
        }
        if (name === 'historical-blocked-report') await capture(browser, item, 390, 'qualidade', 'blocked');
        if (phase === 'after') {
          await loaded(page, pathToFileURL(html).href, 'content'); await page.reload({waitUntil: 'domcontentloaded'});
          const expectedDefault = ['BLOCKED', 'TECHNICAL_FAILURE', 'RUNNING'].includes(payload.latest_attempt?.state) || payload.latest_attempt?.audit_incomplete ? 'qualidade' : 'indicadores';
          equal(`${name}:refresh-content-default`, await page.locator('[data-view-link][aria-current="page"]').getAttribute('data-view-link'), expectedDefault);
        }
        const native = await browser.newContext({offline: true, javaScriptEnabled: false, viewport: {width: 320, height: 900}});
        try {
          const nativePage = await native.newPage(); await loaded(nativePage, pathToFileURL(html).href);
          for (const id of destinations) check(`${name}:no-js:${id}`, await nativePage.locator('#' + id).isVisible());
          await layout(nativePage, name, 320, 'native');
        } finally {await native.close();}
      } catch (error) {check(`${name}:completed`, false, {error: String(error)});}
      finally {await context.close();}
      console.log(JSON.stringify({case: name, completed: true, checks: result.checks.length}));
    }
  } finally {await browser.close();}
  equal('no-remote-requests', result.requests, []); equal('no-js-errors', result.errors, []);
  result.finished_at = new Date().toISOString();
  result.summary = {cases: result.inputs.length, checks: result.checks.length, failures: result.checks.filter(check => !check.ok).length, screenshots: result.screenshots.length, axe_scans: result.axe.length};
  fs.writeFileSync(path.join(output, 'dashboard-review.json'), JSON.stringify(result, null, 2) + '\n');
  fs.writeFileSync(path.join(output, 'summary.json'), JSON.stringify(result.summary, null, 2) + '\n');
  console.log(JSON.stringify(result.summary));
  if (result.summary.failures) process.exitCode = 1;
}
main().catch(error => {console.error(error); process.exitCode = 1;});

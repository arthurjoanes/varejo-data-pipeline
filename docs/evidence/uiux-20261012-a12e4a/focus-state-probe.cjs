'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = process.cwd(), work = path.join(root, 'artifacts', 'uiux-20261012-a12e4a');
const phase = process.argv[2] || 'v3', outputName = process.argv[3] || 'focus-state-v3';
const output = path.join(work, outputName + '.json');
if (fs.existsSync(output)) throw new Error('Preserve previous probe evidence');
const rgb = value => (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
const luminance = color => color.map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
  .reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
const contrast = (first, second) => { const a = luminance(rgb(first)), b = luminance(rgb(second)); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); };
(async () => {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  const record = { phase, checked_at: new Date().toISOString(), browser: browser.version(), inputs: [], band_focus: [], matrix_states: [], requests: { remote: [], failed: [], errors: [] },
    limits: ['Computed CSS/background measurements in normal color mode; no forced-colors, native zoom or screen-reader conformance claim.','Inset ring ratios are measured against cell backgrounds; focus outline outside the grid also borders the white cell gap.'] };
  try {
    const context = await browser.newContext({ offline: true, reducedMotion: 'reduce' });
    const page = await context.newPage();
    page.on('request', request => { if (/^https?:/i.test(request.url())) record.requests.remote.push(request.url()); });
    page.on('requestfailed', request => record.requests.failed.push(request.failure()?.errorText));
    page.on('pageerror', error => record.requests.errors.push(error.message));
    for (const name of ['actual-comparable', 'fixture-large-money']) for (const width of [320, 390, 1440]) {
      const html = path.join(work, phase, 'after', name + '.html');
      if (!record.inputs.some(input => input.name === name)) record.inputs.push({ name, sha256: crypto.createHash('sha256').update(fs.readFileSync(html)).digest('hex') });
      await page.setViewportSize({ width, height: 900 }); await page.goto('about:blank'); await page.goto(pathToFileURL(html).href + '#indicadores');
      await page.evaluate(async () => { await document.fonts.ready; return document.fonts.status; });
      await page.keyboard.press('Tab');
      const targets = page.locator('.publication-band a[href],.publication-band strong[tabindex="0"]');
      for (let index = 0; index < await targets.count(); index++) {
        const target = targets.nth(index); await target.focus();
        const measured = await target.evaluate(element => {
          const style = getComputedStyle(element), box = element.getBoundingClientRect(), band = element.closest('.publication-band'), bandBox = band.getBoundingClientRect();
          const extra = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
          return { tag: element.tagName, label: element.textContent.trim(), focus_visible: element.matches(':focus-visible'),
            outline_color: style.outlineColor, outline_width: style.outlineWidth, outline_style: style.outlineStyle,
            band_background: getComputedStyle(band).backgroundColor, outline_within_band: box.left - extra >= bandBox.left && box.right + extra <= bandBox.right && box.top - extra >= bandBox.top && box.bottom + extra <= bandBox.bottom };
        });
        record.band_focus.push({ name, width, ...measured, contrast_with_band: contrast(measured.outline_color, measured.band_background) });
      }
    }
    const matrixHtml = path.join(work, phase, 'after', 'historical-demo30k-report.html');
    await page.setViewportSize({ width: 1440, height: 900 }); await page.goto('about:blank'); await page.goto(pathToFileURL(matrixHtml).href + '#lojas');
    await page.evaluate(async () => { await document.fonts.ready; return document.fonts.status; });
    const representative = await page.locator('[data-heat-cell]').evaluateAll(elements => {
      const groups = new Map();
      elements.forEach((element, index) => { const color = getComputedStyle(element).backgroundColor; if (!groups.has(color)) groups.set(color, index); });
      return [...groups].map(([color, index]) => ({ color, index }));
    });
    for (const { color, index } of representative) {
      const cell = page.locator('[data-heat-cell]').nth(index); await cell.click(); await page.mouse.move(0, 0);
      const selected = await cell.evaluate(element => ({ background: getComputedStyle(element).backgroundColor, box_shadow: getComputedStyle(element).boxShadow,
        aria_current: element.getAttribute('aria-current'), value: element.dataset.value, focus_visible: element.matches(':focus-visible') }));
      const colors = selected.box_shadow.match(/rgba?\([^)]+\)/g) || [];
      record.matrix_states.push({ ...selected, ring_contrasts_with_cell: colors.map(ring => ({ color: ring, contrast: contrast(ring, color) })), strongest_ring_contrast: Math.max(0, ...colors.map(ring => contrast(ring, color))) });
    }
    record.summary = { band_targets: record.band_focus.length, band_min_contrast: Math.min(...record.band_focus.map(item => item.contrast_with_band)),
      band_below_3: record.band_focus.filter(item => item.focus_visible && item.outline_within_band && item.contrast_with_band < 3).length,
      cell_colors: record.matrix_states.length, selection_min_best_ring_contrast: Math.min(...record.matrix_states.map(item => item.strongest_ring_contrast)),
      selection_colors_below_3: record.matrix_states.filter(item => item.strongest_ring_contrast < 3).length };
    fs.writeFileSync(output, JSON.stringify(record, null, 2) + '\n'); console.log(JSON.stringify(record.summary));
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

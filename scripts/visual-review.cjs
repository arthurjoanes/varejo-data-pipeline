/* Optional developer check. Playwright is not a runtime dependency of the report. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(playwrightModule);

const root = path.resolve(__dirname, '..');
const images = path.join(root, 'docs', 'images', 'interface');
const evidence = path.join(root, 'docs', 'evidence', 'interface');
const reportURL = name => pathToFileURL(path.join(root, 'artifacts', 'interface', `${name}.html`)).href;

async function main() {
  fs.mkdirSync(evidence, { recursive: true });
  fs.mkdirSync(images, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  const results = [];
  const errors = [];
  let screenshots = 0;
  const capture = async (page, name) => {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(images, name), fullPage: true });
    screenshots++;
  };
  try {
    const page = await browser.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const width of [1440, 1366, 768, 390, 320]) {
      await page.setViewportSize({ width, height: width < 800 ? 844 : 900 });
      await page.goto(reportURL('demo30k-report'));
      for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
        await page.locator(`[data-view-link="${view}"]`).click();
        assert.equal(await page.locator('[data-report-view]:visible').count(), 1);
        assert.equal(await page.locator(`[data-view-link="${view}"]`).getAttribute('aria-current'), 'page');
        const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
        assert.ok(dimensions.document <= dimensions.viewport, `${view} overflow at ${width}px`);
        results.push({ width, view, ...dimensions });
        if (width === 1440) await capture(page, { qualidade: 'report.png', indicadores: 'indicators.png', proveniencia: 'files.png' }[view]);
      }
      assert.equal(await page.locator('#lojas tbody tr').count(), 360);
      assert.equal(await page.locator('#receita details tbody tr').count(), 30);
      assert.equal(await page.locator('.coverage-total').textContent(), '12 de 12 lojas com entrega confirmada');
      assert.equal(await page.locator('[role="tab"], [role="tablist"]').count(), 0);
      await page.locator('[data-view-link="qualidade"]').click();
      if (width !== 1440) await capture(page, `report-${width}.png`);
    }
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.getByRole('link', { name: 'Indicadores', exact: true }).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#indicadores').evaluate(el => document.activeElement === el), true);
    await page.locator('#receita summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#receita details').getAttribute('open'), '');
    await page.getByRole('link', { name: 'Arquivos', exact: true }).click();
    assert.equal(await page.locator('#proveniencia').evaluate(el => document.activeElement === el), true);
    const publicationId = await page.locator('#publication-id').inputValue();
    assert.ok(publicationId.length > 16);
    await page.evaluate(() => {
      window.copiedForTest = null;
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
        writeText: async text => { window.copiedForTest = text; }
      }});
    });
    await page.getByRole('button', { name: 'Copiar ID da publicação', exact: true }).click();
    assert.equal(await page.evaluate(() => window.copiedForTest), publicationId);
    assert.equal(await page.locator('#copy-status').innerText(), 'ID copiado.');
    await page.evaluate(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
      document.execCommand = () => false;
    });
    await page.getByRole('button', { name: 'Copiar ID da publicação', exact: true }).click();
    assert.ok((await page.locator('#copy-status').innerText()).includes('use Ctrl+C'));
    assert.equal(await page.locator('#publication-id').evaluate(el => el.selectionEnd - el.selectionStart), publicationId.length);
    assert.equal(await page.locator('.source-record').count(), 1);
    await page.locator('.source-record summary').click();
    assert.ok((await page.locator('.source-record').innerText()).includes('SHA-256'));
    await page.goBack();
    assert.equal(await page.locator('#indicadores').isVisible(), true);
    await page.goto(`${reportURL('demo30k-report')}#lojas`);
    assert.equal(await page.locator('#indicadores').isVisible(), true);
    await page.locator('#lojas summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#lojas details').getAttribute('open'), '');
    await page.getByRole('link', { name: 'Execução', exact: true }).click();
    const stage = page.locator('.stage').first();
    const openBefore = await stage.getAttribute('open');
    await stage.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.notEqual(await stage.getAttribute('open'), openBefore);
    await page.getByRole('link', { name: 'Ver registro da tentativa ↗', exact: true }).click();
    assert.equal(await page.locator('#attempt-identity').getAttribute('open'), '');
    assert.equal(await page.locator('#attempt-identity').evaluate(el => document.activeElement === el), true);
    await page.goto(`${reportURL('demo30k-report')}#attempt-batch-id`);
    assert.equal(await page.locator('#attempt-batch-id').isVisible(), true);

    // Saltar ao conteúdo preserva a vista selecionada e o foco chega ao main.
    for (const view of ['indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      await page.locator('.skip-link').focus();
      await page.keyboard.press('Enter');
      assert.equal(new URL(page.url()).hash, '#content');
      assert.equal(await page.locator(`#${view}`).isVisible(), true);
      assert.equal(await page.locator('[data-report-view]:visible').count(), 1);
      assert.equal(await page.locator('#content').evaluate(el => document.activeElement === el), true);
      await page.goBack();
      assert.equal(new URL(page.url()).hash, `#${view}`);
      assert.equal(await page.locator(`#${view}`).isVisible(), true);
      await page.goForward();
      assert.equal(new URL(page.url()).hash, '#content');
      assert.equal(await page.locator(`#${view}`).isVisible(), true);
      assert.equal(await page.locator('#content').evaluate(el => document.activeElement === el), true);
    }

    // CSS magnification and an equivalent layout viewport; neither is native browser zoom.
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto(reportURL('demo30k-report'));
    await page.evaluate(() => { document.body.style.zoom = '2'; });
    for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `CSS zoom: ${view}`);
    }
    const reflow = await browser.newContext({ viewport: { width: 683, height: 450 }, deviceScaleFactor: 2 });
    const reflowPage = await reflow.newPage();
    await reflowPage.goto(reportURL('demo30k-report'));
    for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
      await reflowPage.locator(`[data-view-link="${view}"]`).click();
      assert.equal(await reflowPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Reflow: ${view}`);
    }
    await reflow.close();

    const noScript = await browser.newContext({ javaScriptEnabled: false });
    const plainPage = await noScript.newPage();
    await plainPage.goto(reportURL('demo30k-report'));
    assert.equal(await plainPage.locator('[data-report-view]:visible').count(), 3);
    assert.equal(await plainPage.locator('#publication-id').inputValue(), publicationId);
    assert.equal(await plainPage.getByRole('button', { name: 'Copiar ID da publicação', exact: true }).count(), 0);
    await plainPage.getByRole('link', { name: 'Indicadores', exact: true }).click();
    await plainPage.locator('#receita summary').click();
    assert.equal(await plainPage.locator('#receita details').getAttribute('open'), '');
    await noScript.close();

    for (const [file, name, expected, context] of [
      ['report', 'recovered.png', 'R$ 77,00', 'fechamento publicado'],
      ['blocked-report', 'blocked.png', 'R$ 64,00', 'publicação anterior'],
      ['failure-report', 'failure.png', 'R$ 57,00', 'falhou antes de publicar'],
      ['quality-review', 'quality-mobile.png', 'Sem publicação disponível', 'Ainda não há indicadores publicados'],
      ['empty-fixture', 'empty.png', 'Sem publicação disponível', 'Nenhum fechamento publicado'],
      ['running-fixture', 'running.png', 'Sem publicação disponível', 'não acompanha a execução em tempo real'],
      ['audit-fixture', 'audit.png', 'R$ 77,00', 'registro final da tentativa incompleto'],
    ]) {
      await page.setViewportSize({ width: name.includes('mobile') ? 390 : 1366, height: 900 });
      await page.goto(reportURL(file));
      assert.ok((await page.locator('body').textContent()).includes(expected), `${file}: expected ${expected}`);
      assert.ok((await page.locator('.publication-context').innerText()).includes(context), file);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, file);
      await capture(page, name);
    }
    assert.ok((await page.locator('.audit-note').innerText()).includes('Métricas ausentes'));
    assert.ok((await page.locator('.quality-outcome').innerText()).includes('— rejeitados'));
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto(reportURL('long-fixture'));
    for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Long content: ${view}`);
    }
    await page.locator('#attempt-identity summary').click();
    assert.equal((await page.locator('#attempt-batch-id').inputValue()).length, 251);
    await page.emulateMedia({ media: 'print' });
    assert.equal(await page.locator('[data-report-view]:visible').count(), 3);
    assert.deepEqual(errors, []);

    const luminance = hex => {
      const rgb = hex.match(/[a-f0-9]{2}/gi).map(v => parseInt(v, 16) / 255)
        .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    };
    const contrast = [['primary', '1c303b', 'ffffff'], ['muted', '52636e', 'f4f7f8'],
      ['link', '17634f', 'ffffff'], ['success', '205b44', 'dcece3'], ['failure', '8d3b23', 'fbe7db'],
      ['sidebar', 'c7d5da', '142830']]
      .map(([name, fg, bg]) => ({ name, ratio: Number(((Math.max(luminance(bg), luminance(fg)) + 0.05) / (Math.min(luminance(bg), luminance(fg)) + 0.05)).toFixed(3)) }));
    assert.ok(contrast.every(pair => pair.ratio >= 4.5));
    fs.writeFileSync(path.join(evidence, 'visual-review.json'), JSON.stringify({
      captured_at: new Date().toISOString(), browser: await browser.version(),
      playwright: require(`${playwrightModule}/package.json`).version, results, contrast, screenshots,
      data: 'Historical demo and benchmark snapshots replayed from docs/evidence/interface/payloads; no new pipeline run. Empty/running/audit are presentation fixtures.',
      keyboard: 'Panel navigation and focus, browser history, deep link, daily/store tables and stage expansion passed. Skip link preserves Indicators/Files, focuses main, and survives back/forward.',
      clipboard: 'Exact ID delivered to intercepted Clipboard API; unavailable fallback selects full ID. System clipboard not used.',
      no_script: 'All three panels visible; equivalent daily table and full publication ID available; native disclosure works.',
      states: 'Published, blocked with previous publication, failed before publication, invalid first delivery, empty, running snapshot and incomplete audit.',
      magnification: 'All three views at CSS zoom 200% in 1366px; equivalent 683 CSS px layout viewport with DPR2 also checked. Neither is native browser zoom.',
      long_content: '320px: long batch/run identifiers, issue code and unbroken diagnostic text; no page overflow and full ID retained.',
      limits: 'Contrast samples, not a full accessibility audit. No screen-reader audit or native browser-zoom check. Print reveals panels; closed disclosures still require expansion.',
    }, null, 2) + '\n');
    console.log(JSON.stringify({ screenshots, viewChecks: results.length, contrast }));
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

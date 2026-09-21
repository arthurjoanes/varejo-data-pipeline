/* Optional developer check: Playwright is not a runtime dependency of the report. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const images = path.join(root, 'docs', 'images', 'round-2');
const evidence = path.join(root, 'docs', 'evidence', 'round-2');

async function main() {
  fs.mkdirSync(evidence, { recursive: true });
  fs.mkdirSync(images, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  const results = [];
  try {
    const page = await browser.newPage();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const width of [1440, 1366, 768, 390, 320]) {
      await page.setViewportSize({ width, height: width < 800 ? 844 : 900 });
      await page.goto(pathToFileURL(path.join(root, 'artifacts', 'demo30k-report.html')).href);
      const dimensions = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        background: getComputedStyle(document.body).backgroundColor,
        mainWidth: document.querySelector('main').getBoundingClientRect().width,
        bodyFont: getComputedStyle(document.body).fontSize,
        navigationFont: getComputedStyle(document.querySelector('.report-nav a')).fontSize,
        dataFont: getComputedStyle(document.querySelector('.numeric')).fontSize,
        coverage: document.querySelector('.coverage-total').textContent,
        hasFalseTabs: Boolean(document.querySelector('[role="tab"], [role="tablist"]')),
        detailRows: document.querySelectorAll('#lojas tbody tr').length,
        dailyRows: document.querySelectorAll('#indicadores details tbody tr').length,
      }));
      assert.ok(dimensions.document <= dimensions.viewport, `Page overflow at ${width}px`);
      assert.equal(dimensions.detailRows, 360);
      assert.equal(dimensions.dailyRows, 30);
      assert.equal(dimensions.bodyFont, '16px');
      assert.equal(dimensions.navigationFont, '15px');
      assert.equal(dimensions.dataFont, '14px');
      assert.equal(dimensions.hasFalseTabs, false);
      assert.equal(dimensions.coverage, '12 de 12 lojas com entrega confirmada');
      await page.screenshot({ path: path.join(images, width === 1440 ? 'report.png' : `report-${width}.png`), fullPage: width !== 1440 });
      results.push({ width, ...dimensions });
    }
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.getByRole('link', { name: 'Indicadores', exact: true }).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#indicadores').evaluate(el => document.activeElement === el), true);
    const dailySummary = page.locator('#indicadores summary');
    await dailySummary.focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#indicadores details').getAttribute('open'), '');
    await page.locator('#indicadores').screenshot({ path: path.join(images, 'indicators.png') });
    await page.getByRole('link', { name: 'Arquivos e versões', exact: true }).click();
    assert.equal(await page.locator('#proveniencia').evaluate(el => document.activeElement === el), true);
    const publicationId = await page.locator('#publication-id').inputValue();
    await page.evaluate(() => {
      window.copiedForTest = null;
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
        writeText: async text => { window.copiedForTest = text; }
      }});
    });
    await page.getByRole('button', { name: 'Copiar ID da publicação', exact: true }).click();
    assert.equal(await page.evaluate(() => window.copiedForTest), publicationId);
    assert.equal(await page.locator('#copy-status').innerText(), 'ID copiado.');
    assert.equal(await page.locator('#copy-status').evaluate(el => getComputedStyle(el).position), 'static');
    assert.equal(await page.locator('#proveniencia #copy-status').count(), 1);
    await page.evaluate(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
      document.execCommand = () => false;
    });
    await page.getByRole('button', { name: 'Copiar ID da publicação', exact: true }).click();
    assert.ok((await page.locator('#copy-status').innerText()).includes('use Ctrl+C'));
    assert.equal(await page.locator('#publication-id').evaluate(el => el.selectionEnd - el.selectionStart), publicationId.length);
    const noScript = await browser.newContext({ javaScriptEnabled: false });
    const plainPage = await noScript.newPage();
    await plainPage.emulateMedia({ reducedMotion: 'reduce' });
    await plainPage.goto(pathToFileURL(path.join(root, 'artifacts', 'demo30k-report.html')).href);
    assert.equal(await plainPage.locator('#publication-id').inputValue(), publicationId);
    assert.equal(await plainPage.getByRole('button', { name: 'Copiar ID da publicação', exact: true }).count(), 0);
    await plainPage.getByRole('link', { name: 'Indicadores', exact: true }).click();
    await plainPage.locator('#indicadores summary').click();
    assert.equal(await plainPage.locator('#indicadores details').getAttribute('open'), '');
    await noScript.close();
    for (const [file, name, expected] of [
      ['report.html', 'review-recovered.png', 'R$ 77,00'],
      ['blocked-report.html', 'blocked.png', 'R$ 64,00'],
      ['failure-report.html', 'failure.png', 'R$ 57,00'],
      ['quality-review.html', 'empty-mobile.png', 'Sem publicação disponível'],
    ]) {
      await page.setViewportSize({ width: name.includes('mobile') ? 390 : 1366, height: 900 });
      await page.goto(pathToFileURL(path.join(root, 'artifacts', file)).href);
      assert.ok((await page.locator('body').innerText()).includes(expected));
      await page.screenshot({ path: path.join(images, name), fullPage: true });
    }
    const luminance = hex => {
      const rgb = hex.match(/[a-f0-9]{2}/gi).map(v => parseInt(v, 16) / 255)
        .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    };
    const contrast = [['primary', '182c45', 'ffffff'], ['muted', '526278', 'edf1f6'],
      ['blue', '185c91', 'e4eef8'], ['success', '236044', 'e7f1e9'], ['failure', '8b3b21', 'fae7dc']]
      .map(([name, fg, bg]) => ({ name, ratio: Number(((luminance(bg) + 0.05) / (luminance(fg) + 0.05)).toFixed(3)) }));
    assert.ok(contrast.every(pair => pair.ratio >= 4.5));
    fs.writeFileSync(path.join(evidence, 'visual-review.json'), JSON.stringify({
      captured_at: new Date().toISOString(), browser: await browser.version(),
      playwright: require('playwright/package.json').version, results, contrast,
      keyboard: 'Anchor focus, daily table expansion and provenance navigation passed, including with JavaScript disabled.',
      clipboard: 'Exact ID delivered to intercepted Clipboard API; unavailable fallback selects full ID. System clipboard not used.',
      limits: 'Not a screen-reader audit or a native browser-zoom check.',
    }, null, 2) + '\n');
    console.log(JSON.stringify({ screenshots: 10, viewports: results.length, contrast }));
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

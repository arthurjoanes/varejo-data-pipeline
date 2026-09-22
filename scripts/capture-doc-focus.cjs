/* Native browser crop of an existing replay; no DOM or payload replacement. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const htmlDirectory = path.resolve(root, process.env.REVIEW_HTML_DIR || 'artifacts/interface');
const output = path.resolve(root, process.env.REVIEW_IMAGES || 'artifacts/interface-review/images');
const evidence = path.resolve(root, process.env.REVIEW_EVIDENCE || 'artifacts/interface-review/evidence');
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  fs.mkdirSync(output, { recursive: true });
  fs.mkdirSync(evidence, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 1120, height: 900 }, reducedMotion: 'reduce' });
    const html = path.join(htmlDirectory, 'blocked-report.html');
    await page.goto(pathToFileURL(html).href + '#qualidade');
    await page.evaluate(() => document.fonts.ready);
    const coverage = page.locator('.coverage-summary');
    assert.ok((await coverage.innerText()).includes('2 de 3 lojas'));
    assert.ok((await coverage.innerText()).includes('S02'));
    assert.ok((await coverage.innerText()).includes('Zero movimento confirmado'));
    const bounds = await coverage.boundingBox();
    assert.ok(bounds && bounds.height <= 650 && bounds.height / bounds.width <= 1.1);
    const image = path.join(output, 'coverage-focus.png');
    await coverage.screenshot({ path: image, animations: 'disabled' });
    fs.writeFileSync(path.join(evidence, 'doc-focus.json'), JSON.stringify({
      captured_at: new Date().toISOString(), browser: await browser.version(),
      method: 'Playwright locator.screenshot of the real coverage panel; no DOM, CSS, data or image editing.',
      selector: '.coverage-summary', viewport: { width: 1120, height: 900 }, bounds,
      input: 'blocked-report.html', input_sha256: sha256(html),
      payload: 'docs/evidence/interface/payloads/blocked-report.json',
      payload_sha256: sha256(path.join(root, 'docs/evidence/interface/payloads/blocked-report.json')),
      image: 'coverage-focus.png', image_sha256: sha256(image),
      scope: 'Current renderer, historical missing-delivery snapshot. Not the separate editorial sender-calendar experiment and not a new pipeline run.',
    }, null, 2) + '\n');
    console.log(JSON.stringify({ image: 'coverage-focus.png', bounds }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

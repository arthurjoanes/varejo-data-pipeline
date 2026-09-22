// Capture the already generated operational reports; this does not run Spark.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const modulePath = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(modulePath);
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');

async function main() {
  const root = path.resolve(__dirname, '../../..');
  const output = path.join(root, 'docs/images/state-proof');
  fs.mkdirSync(output, { recursive: true });
  const proof = JSON.parse(fs.readFileSync(path.join(__dirname, 'restore.json'), 'utf8'));
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const records = [];
  const errors = [];
  const networkRequests = [];
  try {
    const page = await browser.newPage({ reducedMotion: 'reduce' });
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (/^https?:/.test(r.url())) networkRequests.push(r.url()); });
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
      for (const report of proof.reports) {
        if (width === 390 && !['blocked', 'corrected'].includes(report.state)) continue;
        const html = path.join(__dirname, report.path);
        assert.equal(sha(html), report.sha256);
        await page.goto(pathToFileURL(html).href);
        await page.getByRole('heading', { level: 1 }).waitFor();
        const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
        assert.ok(dimensions.document <= dimensions.viewport, `${report.state}: global overflow`);
        const publication = await page.locator('#publication-id').inputValue();
        assert.equal(publication, report.publication_id);
        const title = await page.locator('#execution-title').textContent();
        const file = `${report.state}-${width}.png`;
        await page.screenshot({ path: path.join(output, file), fullPage: true, animations: 'disabled' });
        records.push({ state: report.state, viewport: { width, height: width === 1440 ? 900 : 844 }, title, publication_id: publication, run_id: report.run_id, html_sha256: sha(html), screenshot: `docs/images/state-proof/${file}`, screenshot_sha256: sha(path.join(output, file)), ...dimensions });
      }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(networkRequests, []);
    fs.writeFileSync(path.join(__dirname, 'captures.json'), JSON.stringify({ status: 'passed', recorded_at: new Date().toISOString(), scope: 'Local rendering of four reports produced by the restore scenario. Not a live monitor, visual comparison study, accessibility certification, or another Spark execution.', browser: browser.version(), playwright: require(path.join(modulePath, 'package.json')).version, restore_sha256: sha(path.join(__dirname, 'restore.json')), collector_sha256: sha(__filename), errors, networkRequests, records }, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'passed', captures: records.length, errors, networkRequests }));
  } finally {
    await browser.close();
  }
}
main().catch(e => { console.error(e); process.exitCode = 1; });

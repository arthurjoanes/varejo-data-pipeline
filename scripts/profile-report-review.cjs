/* Functional check for a captured local report. Does not start Spark. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const input = path.resolve(process.argv[2] || 'artifacts/report.html');
  const output = path.resolve(process.argv[3] || 'artifacts/profile-report-review');
  assert.ok(fs.statSync(input).isFile(), 'Expected a captured HTML file');
  assert.ok(!fs.existsSync(output), 'Use a new output directory to preserve previous evidence');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  const errors = [], remoteRequests = [], checks = [];
  try {
    const context = await browser.newContext({ offline: true, reducedMotion: 'reduce' });
    // Force the supported selection/copy fallback on a local file.
    await context.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { value: undefined }));
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) remoteRequests.push(request.url()); });
    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(pathToFileURL(input).href);
      const indicators = page.locator('[data-view-link="indicadores"]');
      await indicators.focus();
      await page.keyboard.press('Enter');
      await page.locator('[data-view-link="indicadores"][aria-current="page"]').waitFor({ state: 'visible' });
      const link = page.locator('a[href="#perfil"]');
      await link.focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.activeElement?.id === 'perfil');
      const details = page.locator('#perfil details').filter({ has: page.locator('summary', { hasText: 'Perfil do estado ativo publicado' }) }).first();
      const available = await details.count() === 1;
      if (available) {
        const summary = details.locator(':scope > summary');
        await summary.focus();
        await page.keyboard.press('Enter');
        await page.waitForFunction(() => [...document.querySelectorAll('#perfil details')].some(element => element.open && element.querySelector(':scope > summary')?.textContent === 'Perfil do estado ativo publicado'));
        assert.ok(await details.locator('table').count() >= 2, 'Equivalent profile tables exist');
        const groups = details.locator('.table-scroll[aria-label*="grupos limitados"]');
        for (let index = 0; index < await groups.count(); index++) {
          assert.ok(await groups.nth(index).locator('tbody tr').count() <= 20, 'Profile group presentation is bounded');
        }
        const scroll = details.locator('.table-scroll').first();
        await scroll.focus();
        assert.equal(await scroll.evaluate(element => document.activeElement === element), true, 'Table scroll is keyboard focusable');
        const baseline = page.locator('#profile-baseline-id');
        if (await baseline.count()) {
          assert.ok((await baseline.inputValue()).length > 0, 'Baseline is identified');
          const copy = page.locator('[data-copy-target="profile-baseline-id"]');
          await copy.focus();
          await page.keyboard.press('Enter');
          await page.locator('#profile-copy-status').filter({ hasText: /ID copiado|ID selecionado/ }).waitFor({ state: 'visible' });
          assert.equal(await baseline.evaluate(element => document.activeElement === element), true, 'Copy fallback focuses the baseline');
          assert.equal(await baseline.evaluate(element => element.selectionEnd - element.selectionStart), (await baseline.inputValue()).length, 'Copy fallback selects the complete baseline');
        }
      } else {
        assert.equal(await page.locator('#perfil .profile-state').count(), 1, 'Unavailable profile has an explicit state');
      }
      const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
      assert.ok(dimensions.document <= dimensions.viewport, `Global overflow at ${width}px`);
      checks.push({ width, available, keyboard_anchor_focus: true, table_focus: available, ...dimensions });
      if (width === 1440 || width === 320) {
        await page.locator('#perfil').screenshot({ path: path.join(output, `profile-${width}.png`) });
      }
    }
    const noScript = await browser.newContext({ javaScriptEnabled: false, offline: true, reducedMotion: 'reduce', viewport: { width: 320, height: 900 } });
    const nativePage = await noScript.newPage();
    await nativePage.goto(pathToFileURL(input).href + '#perfil');
    assert.equal(await nativePage.locator('[data-report-view]:visible').count(), 3, 'Native HTML exposes all report views');
    const nativeSummary = nativePage.locator('#perfil summary').filter({ hasText: 'Perfil do estado ativo publicado' });
    if (await nativeSummary.count()) {
      await nativeSummary.focus();
      await nativePage.keyboard.press('Enter');
      assert.equal(await nativeSummary.evaluate(element => element.parentElement.open), true, 'Native disclosure works by keyboard without JS');
      assert.ok(await nativePage.locator('#perfil table:visible').count() >= 2, 'Data remains available without JS');
    }
    assert.deepEqual(errors, [], 'No JavaScript error');
    assert.deepEqual(remoteRequests, [], 'No HTTP request');
    const result = { browser: browser.version(), checked_at: new Date().toISOString(), input, checks, no_script: true, errors, remoteRequests };
    fs.writeFileSync(path.join(output, 'profile-functional.json'), JSON.stringify(result, null, 2));
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    await context.close();
    await noScript.close();
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

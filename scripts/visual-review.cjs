/* Optional developer check. Playwright is not a runtime dependency of the report. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(playwrightModule);

const root = path.resolve(__dirname, '..');
const images = path.resolve(root, process.env.REVIEW_IMAGES || 'artifacts/interface-review/images');
const evidence = path.resolve(root, process.env.REVIEW_EVIDENCE || 'artifacts/interface-review/evidence');
const htmlDirectory = path.resolve(root, process.env.REVIEW_HTML_DIR || 'artifacts/interface');
const reportURL = name => pathToFileURL(path.join(htmlDirectory, `${name}.html`)).href;

async function waitForView(page, view) {
  // A hash navigation can finish before the hashchange handler updates the DOM.
  // Keep Playwright's default timeout and require both the link and its panel.
  await page.locator(`[data-view-link="${view}"][aria-current="page"]`).waitFor({ state: 'visible' });
  await page.locator(`#${view}`).waitFor({ state: 'visible' });
}

async function main() {
  fs.mkdirSync(evidence, { recursive: true });
  fs.mkdirSync(images, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  const results = [];
  const errors = [];
  let screenshots = 0;
  const capture = async (page, name) => {
    await page.evaluate(() => document.fonts.ready);
    await page.mouse.move(0, 0);
    await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
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
        await waitForView(page, view);
        assert.equal(await page.locator('[data-report-view]:visible').count(), 1);
        assert.equal(await page.locator(`[data-view-link="${view}"]`).getAttribute('aria-current'), 'page');
        const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
        assert.ok(dimensions.document <= dimensions.viewport, `${view} overflow at ${width}px`);
        const targets = await page.locator('nav a:visible, button:visible, summary:visible').evaluateAll(es => es.map(e => ({ text: e.textContent.trim(), height: e.getBoundingClientRect().height })));
        assert.ok(targets.length >= 3, `At least the three navigation links: ${view} at ${width}px`);
        assert.ok(targets.every(target => target.height >= 24), `Control targets: ${view} at ${width}px`);
        if (view === 'indicadores') {
          const boxes = await page.locator('#receita, #produtos, #lojas').evaluateAll(es => es.map(e => { const b=e.getBoundingClientRect(); return { id:e.id, top:b.top, bottom:b.bottom, left:b.left }; }));
          const byId = Object.fromEntries(boxes.map(box => [box.id, box]));
          assert.ok(byId.lojas.top < byId.receita.top, 'Store/day matrix is the first analysis');
          if (width > 900) assert.equal(byId.receita.top, byId.produtos.top, 'Daily series and product ranking share an axis');
          else assert.ok(byId.produtos.top > byId.receita.bottom, 'Mobile preserves matrix, daily, ranking order');
        }
        results.push({ width, view, ...dimensions });
        if (width === 1440) await capture(page, { qualidade: 'report.png', indicadores: 'indicators.png', proveniencia: 'files.png' }[view]);
      }
      assert.equal(await page.locator('#lojas .data-detail tbody tr').count(), 360);
      assert.equal(await page.locator('#receita details tbody tr').count(), 30);
      assert.equal(await page.locator('.coverage-total').textContent(), '12 de 12 lojas com entrega confirmada');
      assert.equal(await page.locator('[role="tab"], [role="tablist"]').count(), 0);
      await page.locator('[data-view-link="qualidade"]').click();
      await waitForView(page, 'qualidade');
      if (width !== 1440) await capture(page, `report-${width}.png`);
    }
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.getByRole('link', { name: 'Indicadores', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement.id === 'indicadores');
    await page.locator('#receita summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#receita details').getAttribute('open'), '');
    await page.getByRole('link', { name: 'Arquivos', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'proveniencia');
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
    await waitForView(page, 'indicadores');
    assert.equal(await page.locator('#indicadores').isVisible(), true);
    await page.goto(`${reportURL('demo30k-report')}#lojas`);
    assert.equal(await page.locator('#indicadores').isVisible(), true);
    await page.locator('#lojas summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#lojas details').getAttribute('open'), '');
    await page.getByRole('link', { name: 'Execução', exact: true }).click();
    await page.locator('.timing-disclosure > summary').click();
    const stage = page.locator('.stage').first();
    const openBefore = await stage.getAttribute('open');
    await stage.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.notEqual(await stage.getAttribute('open'), openBefore);
    const qualityStage = page.locator('.stage').nth(1);
    await qualityStage.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('.stage[open]').count(), 1);
    assert.equal(await qualityStage.locator('.stage-note').isVisible(), true);
    await page.getByRole('link', { name: 'Ver registro da tentativa', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'attempt-identity');
    assert.equal(await page.locator('#attempt-identity').getAttribute('open'), '');
    await page.goto(`${reportURL('demo30k-report')}#attempt-batch-id`);
    assert.equal(await page.locator('#attempt-batch-id').isVisible(), true);

    // Saltar ao conteúdo preserva a vista selecionada e o foco chega ao main.
    for (const view of ['indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      await waitForView(page, view);
      await page.locator('.skip-link').focus();
      await page.keyboard.press('Enter');
      assert.equal(new URL(page.url()).hash, '#content');
      assert.equal(await page.locator(`#${view}`).isVisible(), true);
      assert.equal(await page.locator('[data-report-view]:visible').count(), 1);
      await page.waitForFunction(() => document.activeElement.id === 'content');
      await page.goBack();
      await waitForView(page, view);
      assert.equal(new URL(page.url()).hash, `#${view}`);
      assert.equal(await page.locator(`#${view}`).isVisible(), true);
      await page.goForward();
      await waitForView(page, view);
      assert.equal(new URL(page.url()).hash, '#content');
      assert.equal(await page.locator(`#${view}`).isVisible(), true);
      await page.waitForFunction(() => document.activeElement.id === 'content');
    }

    // CSS magnification and an equivalent layout viewport; neither is native browser zoom.
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto(reportURL('demo30k-report'));
    await page.evaluate(() => { document.body.style.zoom = '2'; });
    for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      await waitForView(page, view);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `CSS zoom: ${view}`);
    }
    const reflow = await browser.newContext({ viewport: { width: 683, height: 450 }, deviceScaleFactor: 2 });
    const reflowPage = await reflow.newPage();
    await reflowPage.goto(reportURL('demo30k-report'));
    for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
      await reflowPage.locator(`[data-view-link="${view}"]`).click();
      await waitForView(reflowPage, view);
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
    await plainPage.locator('[data-heat-cell]').first().click();
    assert.equal(await plainPage.locator('#store-values').getAttribute('open'), '');
    assert.equal(await plainPage.locator('#store-row-0').isVisible(), true);
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
      assert.ok((await page.locator('.publication-bridge').innerText()).includes(context), file);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, file);
      await capture(page, name);
    }
    assert.ok((await page.locator('.audit-note').innerText()).includes('Métricas ausentes'));
    await page.locator('.quality-measurements > summary').click();
    assert.ok((await page.locator('.quality-outcome').innerText()).includes('— rejeitados'));
    // A delivery blocker is not a count of bad sales rows. Keep its cause and destination together.
    for (const width of [1366, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(reportURL('blocked-report'));
      assert.equal(await page.locator('.page-heading .badge, .publication-overview .badge').count(), 0);
      assert.equal(await page.locator('.issues > .issue').count(), 1);
      assert.equal(await page.locator('.quality-measurements').getAttribute('open'), null);
      assert.ok((await page.locator('#execution-title').innerText()).includes('Publicação bloqueada'));
      await page.locator('.decision-action').focus(); await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.activeElement.id === 'pendencias');
      const issue = page.locator('.issues > .issue').first();
      assert.equal(await issue.evaluate(e => getComputedStyle(e).borderLeftWidth), '3px');
      await issue.locator('.issue-record > summary').click();
      assert.ok((await issue.innerText()).includes('MISSING_FILE'));
      assert.equal(await issue.evaluate(e => getComputedStyle(e).borderLeftWidth), '3px');
      await page.locator('.quality-measurements > summary').click();
      const baselines = await page.locator('.quality-outcome p').evaluateAll(es => es.map(e => e.getBoundingClientRect().top));
      if (width >= 1366) assert.equal(new Set(baselines).size, 1);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await capture(page, `blocked-expanded-${width}.png`);
    }
    for (const file of ['demo30k-report', 'quality-review']) {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(reportURL(file));
      const edges = await page.locator('.coverage-summary, .diagnostic-section, .technical-register').evaluateAll(es => es.map(e => e.getBoundingClientRect().right));
      assert.equal(edges.length, 3, `${file}: coverage, diagnostics and technical register exist`);
      assert.ok(Math.max(...edges) - Math.min(...edges) <= 1, `${file}: consistent right edge`);
      const issueSummaries = await page.locator('.issue > summary').all();
      assert.equal(issueSummaries.length, file === 'quality-review' ? 4 : 0, `${file}: expected issue disclosures`);
      for (const summary of issueSummaries) {
        assert.equal(await summary.evaluate(e => getComputedStyle(e).display), 'grid');
        assert.ok(await summary.evaluate(e => e.firstElementChild.getBoundingClientRect().right < e.getBoundingClientRect().right - 20));
      }
    }
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    assert.ok((await page.locator('.report-nav a').first().evaluate(e => getComputedStyle(e, '::after').transitionDuration)).includes('0.18s'));
    await page.emulateMedia({ reducedMotion: 'reduce' });
    assert.equal(await page.locator('.report-nav a').first().evaluate(e => getComputedStyle(e, '::after').transitionDuration), '0s');
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto(reportURL('long-fixture'));
    for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      await waitForView(page, view);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Long content: ${view}`);
    }
    await page.locator('#attempt-identity summary').click();
    assert.equal((await page.locator('#attempt-batch-id').inputValue()).length, 251);
    await capture(page, 'long-files-320.png');
    await page.goto(reportURL('blocked-report'));
    await page.emulateMedia({ media: 'print' });
    assert.equal(await page.locator('[data-report-view]:visible').count(), 3);
    assert.equal(await page.locator('.issue-record p').first().isVisible(), true);
    assert.equal(await page.locator('.quality-measurements .quality-outcome').isVisible(), true);
    await page.setViewportSize({ width: 1200, height: 900 });
    await page.screenshot({ path: path.join(images, 'print-preview.png'), fullPage: false }); screenshots++;
    await page.emulateMedia({ media: 'screen', reducedMotion: 'reduce' });
    for (const [file, expected] of [
      ['unknown-fixture', 'Resultado da tentativa não reconhecido'],
      ['validated-fixture', 'Entrega validada, sem publicação'],
      ['zero-fixture', 'Fechamento publicado'],
      ['missing-metrics-fixture', 'Fechamento publicado'],
      ['large-fixture', 'Fechamento publicado'],
      ['gaps-fixture', 'Fechamento publicado'],
    ]) {
      await page.setViewportSize({ width: 320, height: 900 });
      await page.goto(reportURL(file));
      assert.ok((await page.locator('#execution-title').innerText()).includes(expected));
      for (const view of ['qualidade', 'indicadores', 'proveniencia']) {
        await page.locator(`[data-view-link="${view}"]`).click();
        await waitForView(page, view);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${file}: ${view}`);
      }
      await page.locator('[data-view-link="indicadores"]').click();
      await waitForView(page, 'indicadores');
      if (file === 'missing-metrics-fixture') assert.deepEqual(await page.locator('.metric strong').allTextContents(), ['—', '—', '—', '—']);
      if (file === 'zero-fixture') assert.ok((await page.locator('.metrics').innerText()).includes('R$ 0,00'));
      if (file === 'large-fixture') {
        assert.equal(await page.locator('.metric-wide strong').innerText(), 'R$ 1.234.567.890.123,45');
        assert.ok(await page.locator('.metric-wide').evaluate(e => e.getBoundingClientRect().width >= 240));
      }
      if (file === 'gaps-fixture') {
        assert.equal(await page.locator('#receita circle').count(), 3);
        assert.equal(await page.locator('#receita polyline').count(), 1);
        assert.ok((await page.locator('#receita').innerText()).includes('Dias sem observação não representam receita zero'));
      }
      await capture(page, `${file}-320.png`);
    }
    await page.setViewportSize({ width: 390, height: 900 });
    await page.goto(reportURL('blocked-report'));
    assert.equal(await page.locator('.coverage-total').isVisible(), true);
    assert.equal(await page.locator('.timing-disclosure').getAttribute('open'), null);
    assert.deepEqual(await page.locator('.store-ledger .delivery-state').allTextContents(), ['Entrega confirmada', 'Pendente', 'Zero movimento confirmado']);
    await page.locator('[data-view-link="indicadores"]').click();
    await waitForView(page, 'indicadores');
    assert.equal(await page.locator('.decision-action:visible').count(), 0);
    assert.equal(await page.locator('.publication-heading').isVisible(), true);
    for (const view of ['indicadores', 'proveniencia']) {
      await page.locator(`[data-view-link="${view}"]`).click();
      await waitForView(page, view);
      await capture(page, `${view}-390.png`);
    }
    const matrixChecks = [];
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${reportURL('demo30k-report')}#indicadores`);
    assert.equal(await page.locator('[data-heat-cell]').count(), 360);
    assert.equal(await page.locator('[data-heat-cell][tabindex="0"]').count(), 1);
    const firstCell = page.locator('[data-heat-cell]').first();
    await firstCell.focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('[data-heat-cell][aria-current]').getAttribute('data-column'), '1');
    await page.keyboard.press('ArrowDown');
    assert.equal(await page.locator('[data-heat-cell][aria-current]').getAttribute('data-row'), '1');
    await page.keyboard.press('End');
    assert.equal(await page.locator('[data-heat-cell][aria-current]').getAttribute('data-column'), '29');
    const selected = await page.locator('[data-heat-cell][aria-current]').getAttribute('data-value');
    assert.equal(await page.locator('#matrix-value').innerText(), selected);
    const rowTarget = await page.locator('#matrix-record').getAttribute('href');
    await page.locator('#matrix-record').click();
    await page.waitForFunction(id => document.activeElement.id === id, rowTarget.slice(1));
    assert.equal(await page.locator('#store-values').getAttribute('open'), '');
    matrixChecks.push({ file: 'demo30k-report', cells: 360, tabStops: 1, arrows: true, selected, exactTableFocus: rowTarget });
    for (const file of ['matrix-fixture', 'extreme-dates-fixture']) {
      await page.setViewportSize({ width: 390, height: 900 });
      await page.goto(`${reportURL(file)}#indicadores`);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (file === 'matrix-fixture') {
        assert.equal(await page.locator('.heat-zero').count(), 1);
        assert.equal(await page.locator('.heat-missing').count(), 3);
        const negative = page.locator('[data-heat-cell]').filter({ hasText: 'R$ -12,34' });
        await negative.click();
        assert.ok((await page.locator('#matrix-value').innerText()).includes('R$ -12,34'));
        assert.equal(await page.locator('#receita circle').count(), 2);
        assert.equal(await page.locator('#receita polyline').count(), 0);
      } else {
        assert.equal(await page.locator('.store-matrix').count(), 0);
        assert.equal(await page.locator('#store-values tbody tr').count(), 3);
        assert.ok((await page.locator('#lojas').innerText()).includes('amplo ou disperso'));
      }
      matrixChecks.push({ file, zeroAbsentNegativeOrExtreme: true });
      await capture(page, `${file}-390.png`);
    }
    const fontChecks = [];
    const offline = await browser.newContext({ offline: true, viewport: { width: 1440, height: 900 } });
    const offlinePage = await offline.newPage();
    const externalRequests = [];
    offlinePage.on('request', request => { if (/^https?:/.test(request.url())) externalRequests.push(request.url()); });
    await offlinePage.goto(`${reportURL('demo30k-report')}#indicadores`);
    await offlinePage.evaluate(() => document.fonts.ready);
    const session = await offline.newCDPSession(offlinePage);
    await session.send('DOM.enable'); await session.send('CSS.enable');
    const documentNode = await session.send('DOM.getDocument');
    for (const selector of ['#indicators-title', '[data-metric="net_revenue"]', '.ranking-name']) {
      const node = await session.send('DOM.querySelector', { nodeId: documentNode.root.nodeId, selector });
      const fonts = (await session.send('CSS.getPlatformFontsForNode', { nodeId: node.nodeId })).fonts;
      assert.ok(fonts.some(font => font.isCustomFont && font.familyName.replaceAll(' ', '').includes('SourceSans')));
      fontChecks.push({ selector, fonts });
    }
    assert.deepEqual(externalRequests, []);
    await offline.close();
    const baselineComparisons = [];
    if (process.env.REVIEW_BASELINE_DIR) {
      const baselinePage = await browser.newPage();
      const extract = async target => target.evaluate(() => ({
        metrics: [...document.querySelectorAll('.metric strong')].map(e => e.textContent),
        rows: ['receita','produtos','lojas'].map(id => [...document.querySelectorAll(`#${id} .table-scroll tbody tr`)].map(e => e.textContent.replace(/\s+/g, ' ').trim())),
        ids: [...document.querySelectorAll('.copy-field input')].map(e => [e.id, e.value]),
        sources: [...document.querySelectorAll('.source-record')].map(e => e.textContent.replace(/\s+/g, ' ').trim()),
      }));
      for (const file of ['report', 'blocked-report', 'failure-report', 'quality-review', 'demo30k-report']) {
        await page.goto(reportURL(file));
        await baselinePage.goto(pathToFileURL(path.join(process.env.REVIEW_BASELINE_DIR, `${file}.html`)).href);
        const current = await extract(page); const before = await extract(baselinePage);
        assert.deepEqual(current, before, `Same historical data: ${file}`);
        baselineComparisons.push({ file, metrics: current.metrics, tableRows: current.rows.flat().length, identityFields: current.ids.length, equivalent: true });
      }
      const pairs = [];
      const cases = [
        ...[1440,1024,390].flatMap(width => [['blocked-report','qualidade',width],['demo30k-report','indicadores',width],['demo30k-report','proveniencia',width]]),
        ...['failure-report','quality-review','empty-fixture','running-fixture','audit-fixture'].map(file => [file,'qualidade',390]),
      ];
      fs.mkdirSync(path.join(images,'before'), { recursive: true });
      await baselinePage.emulateMedia({ reducedMotion: 'reduce' });
      for (const [file,view,width] of cases) {
        const viewport = { width, height: 900 };
        const name = `${file}-${view}-${width}.png`;
        const pair = { file, view, viewport, filters: 'none; identical historical payload or presentation fixture', before: `before/${name}`, after: name };
        for (const [target,url,out] of [[baselinePage,pathToFileURL(path.join(process.env.REVIEW_BASELINE_DIR,`${file}.html`)).href,pair.before],[page,reportURL(file),pair.after]]) {
          await target.setViewportSize(viewport); await target.goto(`${url}#${view}`);
          await target.evaluate(() => document.fonts.ready);
          await target.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0,0); });
          assert.ok(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          await target.screenshot({ path:path.join(images,out), fullPage:true });
        }
        pairs.push(pair);
      }
      fs.writeFileSync(path.join(evidence,'comparison.json'),JSON.stringify({baseline:'636e8408f1108ce387ddc291318d2d1ebe042dee',pairs,limits:'Same offline data, hash and viewport; font changes intentionally. No timing or usability improvement claimed.'},null,2)+'\n');
      await baselinePage.close();
    }
    assert.deepEqual(errors, []);

    const luminance = hex => {
      const rgb = hex.match(/[a-f0-9]{2}/gi).map(v => parseInt(v, 16) / 255)
        .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    };
    const contrast = [['primary', '263248', 'ffffff'], ['muted', '596274', 'f2f3f5'],
      ['link', '49488f', 'ffffff'], ['success', '226348', 'edf7f1'], ['failure', '923b35', 'e5e8ef'],
      ['selected navigation', '49488f', 'ffffff'], ['publication', 'ffffff', '263248'], ['publication metadata', 'dce0e9', '263248']]
      .map(([name, fg, bg]) => ({ name, ratio: Number(((Math.max(luminance(bg), luminance(fg)) + 0.05) / (Math.min(luminance(bg), luminance(fg)) + 0.05)).toFixed(3)) }));
    assert.ok(contrast.every(pair => pair.ratio >= 4.5));
    const controlContrast = ['ffffff', 'e5e8ef'].map(bg => ({ name: 'Control border', foreground: '7186a9', background: bg, ratio: Number(((luminance(bg) + 0.05) / (luminance('7186a9') + 0.05)).toFixed(3)) }));
    assert.ok(controlContrast.every(pair => pair.ratio >= 3));
    fs.writeFileSync(path.join(evidence, 'visual-review.json'), JSON.stringify({
      captured_at: new Date().toISOString(), browser: await browser.version(),
      playwright: require(`${playwrightModule}/package.json`).version, results, contrast, controlContrast, screenshots, baselineComparisons, matrixChecks, fontChecks, externalRequests,
      composition: 'Publication+metrics band, store/day matrix, then daily series and unit ranking. Matrix limited before allocating dates; exact rows retained.',
      assets: 'Source Sans 3 VF embedded as unmodified WOFF2; full OFL included. Original SVG mark/favicon/monochrome variant. No external request.',
      data: 'Historical demo and benchmark snapshots replayed from docs/evidence/interface/payloads; no new pipeline run. Empty/running/audit are presentation fixtures.',
      keyboard: 'Panel navigation and focus, browser history, deep link, daily/store tables and stage expansion passed. Matrix arrows/Home/End use one tabstop; selected value links to exact row. Skip link preserves Indicators/Files, focuses main, and survives back/forward.',
      clipboard: 'Exact ID delivered to intercepted Clipboard API; unavailable fallback selects full ID. System clipboard not used.',
      no_script: 'All three panels visible; equivalent daily table and full publication ID available; native disclosure works.',
      states: 'Published, blocked with previous publication, failed before publication, invalid first delivery, empty, running, audit incomplete, unknown state, validated, zero, absent metrics, large numbers.',
      magnification: 'All three views at CSS zoom 200% in 1366px; equivalent 683 CSS px layout viewport with DPR2 also checked. Neither is native browser zoom.',
      long_content: '320px: long batch/run identifiers, issue code and unbroken diagnostic text; no page overflow and full ID retained.',
      refinements: 'Blocker cause/CTA/focus; one primary incident, related record preserved; visible coverage/zero confirmation; measured times secondary; attempt heading scoped to Execution, published identity scoped to Indicators; full-height parent border; fixed toggle column; 180ms selection transitions disabled with reduced motion.',
      limits: 'Contrast samples, not a full accessibility audit. No screen-reader audit or native browser-zoom check. Print reveals panels and disclosure content; full PDF pagination was not audited.',
    }, null, 2) + '\n');
    console.log(JSON.stringify({ screenshots, viewChecks: results.length, contrast }));
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

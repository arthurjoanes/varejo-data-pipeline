/* Optional development audit; neither axe nor Playwright is a report dependency. */
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const AxeBuilder = require(process.env.AXE_MODULE || '@axe-core/playwright').default;
const root = path.resolve(__dirname, '..');

(async () => {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
  const results = [];
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    const cases = [1440, 390].flatMap(width => ['qualidade', 'indicadores', 'proveniencia'].map(view => ['blocked-report', view, width]));
    cases.push(['quality-review', 'qualidade', 390], ['empty-fixture', 'qualidade', 390], ['running-fixture', 'qualidade', 390], ['audit-fixture', 'qualidade', 1440]);
    cases.push(...[1440,390].flatMap(width => [['demo30k-report','indicadores',width], ['matrix-fixture','indicadores',width]]));
    for (const [file, view, width] of cases) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(pathToFileURL(path.join(root, 'artifacts/interface', `${file}.html`)).href + '#' + view);
      const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
      results.push({ file, view, width, axe: report.testEngine.version, violations: report.violations, incomplete: report.incomplete.map(rule => ({ id: rule.id, description: rule.description, nodes: rule.nodes.map(node => ({ target: node.target, summary: node.failureSummary })) })), passedRules: report.passes.length });
    }
    const output = { browser: await browser.version(), captured_at: new Date().toISOString(), results, scope: 'Automated WCAG-tagged checks on 14 offline views. Complements keyboard, responsive and contrast checks; not a complete WCAG or screen-reader audit.' };
    fs.writeFileSync(path.join(root, 'docs/evidence/interface-v4/accessibility.json'), JSON.stringify(output, null, 2) + '\n');
    const violations = results.reduce((sum, result) => sum + result.violations.length, 0);
    console.log(JSON.stringify({ views: results.length, violations }));
    if (violations) process.exitCode = 1;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

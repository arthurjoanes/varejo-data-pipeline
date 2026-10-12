const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const here = __dirname;
const pw = require(path.join(here, 'tools/node_modules/playwright'));
const { AxeBuilder } = require(path.join(here, 'tools/node_modules/@axe-core/playwright'));
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const scan = root => {
  const result = {};
  function walk(dir) {
    for (const item of fs.readdirSync(dir, {withFileTypes: true})) {
      const file = path.join(dir, item.name);
      if (item.isDirectory()) walk(file);
      else if (item.isFile()) result[path.relative(root, file).replaceAll('\\', '/')] = hash(file);
    }
  }
  walk(root);
  return result;
};

(async () => {
  const engines = [];
  for (const [name, type, options] of [['edge', pw.chromium, {channel: 'msedge'}], ['firefox', pw.firefox, {}]]) {
    const browser = await type.launch({headless: true, ...options});
    try {
      const context = await browser.newContext({offline: true});
      const page = await context.newPage();
      await page.setContent('<!doctype html><html lang="pt-BR"><head><title>Prova isolada de ferramentas</title></head><body><main><h1>Prova isolada</h1><p>Verifica o runtime; nenhum relatório ou lote é executado.</p></main></body></html>');
      const results = await new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
      engines.push({name, version: browser.version(), headless: true, offline: true,
                    axe_version: results.testEngine.version, violations: results.violations.length,
                    incomplete: results.incomplete.length});
    } finally { await browser.close(); }
  }
  const manifest = {
    method: 'Isolated browser/axe runtime smoke, not report UI evidence.',
    node_version: process.version, node_executable: process.execPath, node_sha256: hash(process.execPath),
    playwright: require(path.join(here, 'tools/node_modules/playwright/package.json')).version,
    playwright_core_used: require(path.join(here, 'tools/node_modules/playwright/node_modules/playwright-core/package.json')).version,
    axe_core: require(path.join(here, 'tools/node_modules/axe-core/package.json')).version,
    axe_playwright: require(path.join(here, 'tools/node_modules/@axe-core/playwright/package.json')).version,
    npm_registry: 'https://registry.npmjs.org/',
    package_lock_sha256: hash(path.join(here, 'tools/package-lock.json')),
    firefox_download: {url: 'https://cdn.playwright.dev/dbazure/download/playwright/builds/firefox/1543/firefox-win64.zip',
      bytes: fs.statSync(path.join(here, 'firefox-1543-win64.zip')).size,
      sha256: hash(path.join(here, 'firefox-1543-win64.zip')), method: 'Official Playwright build downloaded over HTTPS with PowerShell after Node installer timeouts.'},
    winldd_download: {url: 'https://cdn.playwright.dev/dbazure/download/playwright/builds/winldd/1007/winldd-win64.zip',
      bytes: fs.statSync(path.join(here, 'winldd-1007-win64.zip')).size,
      sha256: hash(path.join(here, 'winldd-1007-win64.zip'))},
    node_modules_hashes: scan(path.join(here, 'tools/node_modules')),
    firefox_runtime_hashes: scan(path.join(here, 'browsers/firefox-1543')),
    winldd_runtime_hashes: scan(path.join(here, 'browsers/winldd-1007')),
    setup_logs: Object.fromEntries(['tools-install.log', 'browser-install.log', 'browser-install-retry.log'].map(name => [name, hash(path.join(here, name))])),
    engines,
    probe_sha256: hash(__filename),
  };
  fs.writeFileSync(path.join(here, 'tooling-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(JSON.stringify({engines, playwright: manifest.playwright, axe: manifest.axe_core,
    firefox_archive_sha256: manifest.firefox_download.sha256}));
})().catch(error => { console.error(error); process.exitCode = 1; });

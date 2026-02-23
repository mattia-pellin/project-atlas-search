const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER LOG:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  await page.goto('http://localhost:5173/');
  await page.fill('.search-input', 'matrix');
  await page.click('.search-button');
  await page.waitForTimeout(10000);
  await browser.close();
})();

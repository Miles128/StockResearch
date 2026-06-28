const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1600 }});
  await page.goto('http://127.0.0.1:5175', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(3000);

  // Click portfolio tab
  const tabs = await page.$$('[role="tab"], nav button, .nav-tab');
  for (const tab of tabs) {
    const text = await tab.textContent();
    if (text && text.includes('持仓')) {
      await tab.click();
      break;
    }
  }
  await page.waitForTimeout(2000);

  // Get all elements with 'briefing' in class
  const result = await page.evaluate(() => {
    const els = document.querySelectorAll('[class*="briefing"]');
    return Array.from(els).map(el => ({
      tag: el.tagName,
      cls: el.className,
      kids: el.children.length,
      disp: getComputedStyle(el).display,
      dir: getComputedStyle(el).flexDirection || getComputedStyle(el).gridTemplateColumns,
    }));
  });
  console.log(JSON.stringify(result, null, 2));

  // Screenshot
  await page.screenshot({ path: '_design/live-check.png', fullPage: false });

  await browser.close();
})();

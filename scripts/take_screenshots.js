const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:3000';
const OUT_DIR = path.join(__dirname, '../screenshots');

async function login(page) {
  await page.goto(BASE_URL + '/login', { waitUntil: 'networkidle', timeout: 10000 });
  await page.fill('input[type="email"], input[autocomplete="email"]', 'admin@firewatch.kz');
  await page.fill('input[type="password"]', 'admin123');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard**', { timeout: 8000 });
  console.log('   ✓ logged in');
}

const PAGES = [
  { name: '01_dashboard',   url: '/dashboard',            waitFor: '.recharts-responsive-container, canvas, [class*="card"]' },
  { name: '02_map',         url: '/dashboard/map',        waitFor: '.leaflet-container' },
  { name: '03_inspector',   url: '/dashboard/inspector',  waitFor: 'table, [class*="table"], [class*="list"]' },
  { name: '04_forecast',    url: '/dashboard/forecast',   waitFor: '.recharts-responsive-container' },
  { name: '05_chat',        url: '/dashboard/chat',       waitFor: '[class*="chat"], input, textarea' },
  { name: '06_alerts',      url: '/dashboard/alerts',     waitFor: '[class*="alert"], button' },
];

(async () => {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  await login(page);

  for (const { name, url, waitFor } of PAGES) {
    console.log(`📸 ${name} — ${url}`);
    try {
      await page.goto(BASE_URL + url, { waitUntil: 'networkidle', timeout: 15000 });
      // wait for key element or just settle
      try {
        await page.waitForSelector(waitFor, { timeout: 5000 });
      } catch (_) {}
      await page.waitForTimeout(1500); // let charts animate
      const file = path.join(OUT_DIR, `${name}.png`);
      await page.screenshot({ path: file, fullPage: false });
      console.log(`   ✓ saved → ${file}`);
    } catch (err) {
      console.error(`   ✗ failed: ${err.message}`);
    }
  }

  await browser.close();
  console.log('\nDone. Screenshots in:', OUT_DIR);
})();

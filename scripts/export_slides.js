const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SLIDES_HTML = path.resolve(__dirname, 'slides.html');
const OUT_DIR = path.resolve(__dirname, '../slides_export');
const SLIDE_IDS = ['s1','s2','s3','s4','s5','s6','s7','s8','s9','s10'];

(async () => {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('file://' + SLIDES_HTML, { waitUntil: 'networkidle' });

  // wait for Google Fonts to load
  await page.waitForTimeout(1500);

  for (let i = 0; i < SLIDE_IDS.length; i++) {
    const id = SLIDE_IDS[i];
    const num = String(i + 1).padStart(2, '0');
    const outFile = path.join(OUT_DIR, `slide_${num}.png`);

    const el = await page.$(`#${id}`);
    if (!el) { console.error(`  ✗ #${id} not found`); continue; }

    await el.screenshot({ path: outFile });
    console.log(`✓ slide ${num} (${id}) → ${outFile}`);
  }

  await browser.close();
  console.log('\nAll slides saved to:', OUT_DIR);
})();

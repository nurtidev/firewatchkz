const { chromium } = require('playwright');
const path = require('path');

const SLIDES_HTML = path.resolve(__dirname, 'slides.html');
const OUT_PNG = path.resolve(__dirname, '../slides_export/slide_10.png');
const OUT_PDF = path.resolve(__dirname, '../slides_export/slide_10.pdf');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('file://' + SLIDES_HTML, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);

  const el = await page.$('#s10');

  // PNG
  await el.screenshot({ path: OUT_PNG });
  console.log('✓ PNG →', OUT_PNG);

  // PDF — открываем слайд отдельно в нужном размере
  const page2 = await browser.newPage();
  await page2.setViewportSize({ width: 1280, height: 720 });
  await page2.goto('file://' + SLIDES_HTML, { waitUntil: 'networkidle' });
  await page2.waitForTimeout(1200);

  // Показываем только s10, остальные скрываем
  await page2.evaluate(() => {
    document.querySelectorAll('.slide').forEach(s => s.style.display = 'none');
    document.querySelector('#s10').style.display = 'flex';
  });

  await page2.pdf({
    path: OUT_PDF,
    width: '1280px',
    height: '720px',
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });
  console.log('✓ PDF →', OUT_PDF);

  await browser.close();
})();

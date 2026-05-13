const { chromium } = require('playwright');
const path = require('path');

const SLIDES_HTML = path.resolve(__dirname, 'slides.html');
const OUT_PDF = path.resolve(__dirname, '../slides_export/firewatch_pitch.pdf');
const SLIDE_IDS = ['s1','s2','s3','s4','s5','s6','s7','s8','s9','s10'];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 720 });

  // Build HTML where each slide is a separate page (page-break-after)
  await page.goto('file://' + SLIDES_HTML, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  await page.evaluate((ids) => {
    ids.forEach((id, i) => {
      const el = document.querySelector('#' + id);
      if (!el) return;
      el.style.pageBreakAfter = 'always';
      el.style.breakAfter = 'page';
      el.style.marginBottom = '0';
    });
    // remove body background so PDF pages are clean
    document.body.style.background = '#0a0d14';
  }, SLIDE_IDS);

  await page.pdf({
    path: OUT_PDF,
    width: '1280px',
    height: '720px',
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });

  console.log('✓ PDF →', OUT_PDF);
  await browser.close();
})();

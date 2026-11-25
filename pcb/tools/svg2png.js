// Render an SVG (or a cropped region of it) to PNG with the preinstalled Chromium.
// usage: node svg2png.js in.svg out.png width [x y w h]  (crop in SVG user units, fractions 0..1)
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [inp, out, width, cx, cy, cw, ch] = process.argv.slice(2);
  let svg = fs.readFileSync(inp, 'utf8');
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: 1 });
  const W = parseInt(width);
  await p.setContent(`<html><body style="margin:0;background:#fff"><div id=c style="width:${W}px;overflow:hidden">${svg}</div></body></html>`);
  await p.evaluate(([W, cx, cy, cw, ch]) => {
    const s = document.querySelector('svg');
    const vb = s.viewBox.baseVal;
    let x = vb.x, y = vb.y, w = vb.width, h = vb.height;
    if (cx !== undefined) { x = vb.x + vb.width * cx; y = vb.y + vb.height * cy; w = vb.width * cw; h = vb.height * ch; }
    s.setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
    s.setAttribute('width', W); s.setAttribute('height', Math.round(W * h / w));
  }, [W, cx && +cx, cy && +cy, cw && +cw, ch && +ch]);
  await p.locator('svg').first().screenshot({ path: out });
  await b.close();
})();

// SVG → PNG 래스터라이저 (품질 채점용). resvg-js 사용.
// usage: node _svg_raster.js <in.svg> <out.png> <targetWidthPx>
const fs = require('fs');
const path = require('path');

let Resvg;
try {
  ({ Resvg } = require('@resvg/resvg-js'));
} catch (e) {
  process.stderr.write('resvg-js not available: ' + e.message);
  process.exit(3);
}

const [, , inSvg, outPng, wStr] = process.argv;
if (!inSvg || !outPng) { process.stderr.write('usage: node _svg_raster.js <in.svg> <out.png> [width]'); process.exit(2); }

try {
  const svg = fs.readFileSync(inSvg, 'utf8');
  const opts = { background: 'white' };
  const w = parseInt(wStr, 10);
  if (w > 0) opts.fitTo = { mode: 'width', value: w };
  const png = new Resvg(svg, opts).render().asPng();
  fs.mkdirSync(path.dirname(outPng), { recursive: true });
  fs.writeFileSync(outPng, png);
  process.stdout.write('ok');
} catch (e) {
  process.stderr.write('render failed: ' + (e && e.message ? e.message : String(e)));
  process.exit(1);
}

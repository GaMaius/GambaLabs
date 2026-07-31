// 로고 SVG → PNG 4종 생성 (브랜드/화이트 × 전체로고/아이콘)
// 사용: node assets/gen_logo.js
const fs = require("fs");
const path = require("path");
const { Resvg } = require("@resvg/resvg-js");

const SVG_PATH = path.join(__dirname, "..", "assets", "logo", "gambalabs-logo.svg");
const OUT_DIR = path.join(__dirname, "..", "assets", "logo");
const raw = fs.readFileSync(SVG_PATH, "utf8");

// 화이트 변환: 모든 fill rgb(...) 및 그라데이션 stop-color 를 흰색으로
function toWhite(svg) {
  return svg.replace(/rgb\([^)]*\)/g, "rgb(100%,100%,100%)");
}

// 아이콘만 크롭: viewBox 를 아이콘 영역(0 0 46 30)으로 축소 → 워드마크(x>=51)는 밖으로 나가 잘림
function iconOnly(svg) {
  return svg.replace(/viewBox="[^"]*"/, 'viewBox="0 0 46 30"')
            .replace(/width="[^"]*"/, 'width="46px"')
            .replace(/height="[^"]*"/, 'height="30px"');
}

function render(svg, outName, widthPx) {
  const resvg = new Resvg(svg, { fitTo: { mode: "width", value: widthPx }, background: "rgba(0,0,0,0)" });
  const png = resvg.render().asPng();
  const out = path.join(OUT_DIR, outName);
  fs.writeFileSync(out, png);
  console.log("wrote", outName, png.length, "bytes");
}

// 전체 로고: 비율 8.16:1
render(raw, "logo_color.png", 1200);
render(toWhite(raw), "logo_white.png", 1200);
// 아이콘: 비율 1.53:1
render(iconOnly(raw), "icon_color.png", 360);
render(iconOnly(toWhite(raw)), "icon_white.png", 360);
console.log("done");

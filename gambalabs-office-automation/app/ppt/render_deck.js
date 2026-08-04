// 일반화된 덱 렌더러 — 슬라이드 플랜(JSON) → .pptx
// 테마 구동: plan.theme = "gamba"(기본) | "light" | "none"
// 사용: node render_deck.js <plan.json> <assets_dir> <out.pptx>
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const [, , planPath, assetsDir, outPath] = process.argv;
const plan = JSON.parse(fs.readFileSync(planPath, "utf8"));
const A = (p) => path.join(assetsDir, p);

// ── 테마 정의 ─────────────────────────────────────
// C: 색 팔레트 / F: 폰트 / useImages: 브랜드 이미지 에셋(band.png·bg_cover.png·로고) 사용 여부
const THEMES = {
  // 감바랩스 네이비 — 브랜드 풀(이미지 배경·밴드·로고)
  gamba: {
    label: "감바랩스 네이비",
    C: { hero: "123979", brand: "0038A3", med: "1970AE", body: "ECECEC", white: "FFFFFF",
         muted: "C9D4E8", gray: "5A6472", sky: "4E86C6", teal: "2A9D99", surface2: "E7ECF3",
         cardBg: "FFFFFF", cardInk: "123979" },
    // 제목 폰트: 브랜드 HY견고딕이 이상적이나 미설치 PC가 많아 PowerPoint가 임의 대체(깨짐)
    // → 전 Windows에 기본 탑재된 '맑은 고딕'으로 폴백해 어디서나 동일하게 렌더
    F: { title: "맑은 고딕", body: "맑은 고딕" },
    useImages: true,
  },
  // 감바랩스 라이트 — 브랜드 색은 유지하되 밝은 배경(인쇄·문서용), 이미지 에셋 없이 도형만
  light: {
    C: { hero: "123979", brand: "0038A3", med: "1970AE", body: "F4F6FA", white: "FFFFFF",
         muted: "5A6472", gray: "5A6472", sky: "4E86C6", teal: "2A9D99", surface2: "E9EFF9",
         cardBg: "FFFFFF", cardInk: "123979" },
    F: { title: "맑은 고딕", body: "맑은 고딕" },
    useImages: false, bandColor: "0038A3", bandInk: "FFFFFF",
    coverBg: "FFFFFF", coverInk: "123979", coverSub: "1970AE", coverFoot: "5A6472",
    logo: "logo/logo_color.png", closingBg: "F4F6FA", accent: "0038A3",
  },
  // 테마 없음 — 브랜드 무관 플레인(흰 배경·검정/회색·파랑 포인트), 로고·밴드 이미지 전혀 없음
  none: {
    C: { hero: "222222", brand: "2456C7", med: "4A76D6", body: "FFFFFF", white: "FFFFFF",
         muted: "777777", gray: "666666", sky: "4A76D6", teal: "2A9D99", surface2: "F0F0F0",
         cardBg: "FAFAFA", cardInk: "222222" },
    F: { title: "맑은 고딕", body: "맑은 고딕" },
    useImages: false, bandColor: "FFFFFF", bandInk: "1A1A1A", bandLine: "DADADA",
    coverBg: "FFFFFF", coverInk: "1A1A1A", coverSub: "666666", coverFoot: "888888",
    logo: null, closingBg: "FFFFFF", accent: "2456C7",
  },
};
// plan.themeConfig(커스텀 업로드/제작 테마) 우선, 없으면 내장 키
const T = (plan.themeConfig && plan.themeConfig.C) ? plan.themeConfig : (THEMES[plan.theme] || THEMES.gamba);
const C = T.C;
const F = T.F;
const W = 13.333, H = 7.5;

const prs = new pptxgen();
prs.layout = "LAYOUT_WIDE";

// ── 자동 글자 크기: 박스(inch)에 텍스트가 넘치지 않는 최대 pt를 계산(한글 전각 기준) ──
function fitSize(text, wIn, hIn, base, min, ls) {
  ls = ls || 1.18;
  const len = ((text == null ? "" : String(text)).length) || 1;
  for (let p = base; p >= min; p -= 0.5) {
    const charW = (p / 72) * 0.92;                 // 한글 1글자 ≈ 1em(약간 보정)
    const cpl = Math.max(1, Math.floor(wIn / charW));
    const lineH = (p / 72) * ls;
    const maxLines = Math.max(1, Math.floor(hIn / lineH));
    if (len <= cpl * maxLines * 0.92) return p;    // 8% 여유
  }
  return min;
}
// 여러 불릿/항목: 각 항목이 최소 1줄, 길면 여러 줄로 줄바꿈된다고 보고 총 높이로 판정
function fitList(items, wIn, hIn, base, min, ls, paraGapPt) {
  ls = ls || 1.25; paraGapPt = paraGapPt || 8;
  const arr = (items || []).map((t) => (t == null ? "" : String(t)));
  for (let p = base; p >= min; p -= 0.5) {
    const charW = (p / 72) * 0.92;
    const cpl = Math.max(1, Math.floor(wIn / charW));
    const lineH = (p / 72) * ls;
    let lines = 0;
    arr.forEach((t) => { lines += Math.max(1, Math.ceil((t.length || 1) / cpl)); });
    const totalH = lines * lineH + Math.max(0, arr.length - 1) * (paraGapPt / 72);
    if (totalH <= hIn * 0.96) return p;
  }
  return min;
}

// ── 공통: 헤더 밴드 ────────────────────────────────
function bandHeader(slide, title) {
  if (T.useImages) {
    slide.background = { color: C.body };
    slide.addImage({ path: A("backgrounds/band.png"), x: 0, y: 0, w: W, h: 1.05 });
    slide.addImage({ path: A("logo/icon_white.png"), x: 0.4, y: 0.27, w: 0.72 * 1.53, h: 0.72 });
    slide.addText(title || "", { x: 1.4, y: 0, w: W - 2.8, h: 1.05, fontFace: F.title,
      fontSize: fitSize(title, W - 2.8, 0.95, 26, 15), bold: true, color: C.white,
      align: "center", valign: "middle", margin: 0 });
    return;
  }
  // 이미지 없는 테마: 도형 밴드
  slide.background = { color: C.body };
  slide.addShape(prs.ShapeType.rect, { x: 0, y: 0, w: W, h: 1.05, fill: { color: T.bandColor }, line: { type: "none" } });
  if (T.bandLine)
    slide.addShape(prs.ShapeType.line, { x: 0, y: 1.05, w: W, h: 0, line: { color: T.bandLine, width: 1 } });
  else  // 컬러 밴드엔 좌측 포인트 바
    slide.addShape(prs.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: 1.05, fill: { color: C.med }, line: { type: "none" } });
  slide.addText(title || "", { x: 0.7, y: 0, w: W - 1.4, h: 1.05, fontFace: F.title,
    fontSize: fitSize(title, W - 1.4, 0.95, 25, 15), bold: true, color: T.bandInk,
    align: "left", valign: "middle", margin: 0 });
}
function lead(slide, text) {
  if (!text) return 1.35;
  slide.addText(text, { x: 0.8, y: 1.3, w: W - 1.6, h: 0.55, fontFace: F.body,
    fontSize: fitSize(text, W - 1.6, 0.5, 15, 11), color: C.gray, valign: "top", margin: 0 });
  return 2.0;
}

// ── 표지 ──
function cover() {
  const s = prs.addSlide();
  if (T.useImages) {
    s.background = { path: A("backgrounds/bg_cover.png") };
    s.addShape(prs.ShapeType.roundRect, { x: 9.55, y: 3.05, w: 1.95, h: 5.0, rectRadius: 0.97,
      fill: { color: "EAEAEA", transparency: 88 }, line: { type: "none" } });
    s.addImage({ path: A("logo/logo_white.png"), x: 10.05, y: 0.5, w: 2.55, h: 2.55 / 8.16 });
    s.addText(plan.title || "발표자료", { x: 0.9, y: 2.15, w: 8.3, h: 2.2, fontFace: F.title, fontSize: 40,
      bold: true, color: C.white, align: "left", valign: "top", lineSpacingMultiple: 1.05, margin: 0 });
    if (plan.subtitle)
      s.addText(plan.subtitle, { x: 0.92, y: 4.5, w: 8.2, h: 0.9, fontFace: F.body, fontSize: 20, color: C.muted, margin: 0 });
    s.addText(plan.presenter || "감바랩스 주식회사 (Gamba Labs Co., Ltd.)",
      { x: 0.92, y: 6.1, w: 8.0, h: 0.5, fontFace: F.body, fontSize: 14, color: C.white, margin: 0 });
    return;
  }
  // 이미지 없는 테마: 단색 표지
  s.background = { color: T.coverBg };
  if (T.logo) s.addImage({ path: A(T.logo), x: 0.9, y: 0.75, w: 2.2, h: 2.2 / 8.16 });
  s.addShape(prs.ShapeType.rect, { x: 0.94, y: 2.55, w: 1.1, h: 0.09, fill: { color: T.accent }, line: { type: "none" } });
  s.addText(plan.title || "발표자료", { x: 0.9, y: 2.85, w: 10.5, h: 2.0, fontFace: F.title, fontSize: 40,
    bold: true, color: T.coverInk, align: "left", valign: "top", lineSpacingMultiple: 1.05, margin: 0 });
  if (plan.subtitle)
    s.addText(plan.subtitle, { x: 0.94, y: 4.9, w: 10.0, h: 0.9, fontFace: F.body, fontSize: 20, color: T.coverSub, margin: 0 });
  s.addText(plan.presenter || "감바랩스 주식회사 (Gamba Labs Co., Ltd.)",
    { x: 0.94, y: 6.5, w: 10.0, h: 0.5, fontFace: F.body, fontSize: 14, color: T.coverFoot, margin: 0 });
}

// ── 목차 ──
function toc(titles) {
  const s = prs.addSlide();
  bandHeader(s, "목차");
  const half = Math.ceil(titles.length / 2);
  titles.forEach((t, i) => {
    const col = i < half ? 0 : 1;
    const row = i < half ? i : i - half;
    s.addText([{ text: String(i + 1).padStart(2, "0") + "  ", options: { color: C.med, bold: true } },
               { text: t, options: { color: C.hero } }],
      { x: 0.9 + col * 6.1, y: 1.7 + row * 0.62, w: 5.8, h: 0.5, fontFace: F.body, fontSize: 15, margin: 0 });
  });
}

// ── 카드형 본문 ──
function cardsSlide(sl) {
  const s = prs.addSlide();
  bandHeader(s, sl.title);
  const top = lead(s, sl.lead);
  const items = (sl.items || []).slice(0, 4);
  const n = items.length || 1, gap = 0.35, left0 = 0.8, usable = W - 1.6;
  const cw = (usable - gap * (n - 1)) / n, ch = 6.9 - top;
  items.forEach((it, i) => {
    const x = left0 + i * (cw + gap);
    s.addShape(prs.ShapeType.roundRect, { x, y: top, w: cw, h: ch, rectRadius: 0.1,
      fill: { color: C.cardBg }, line: T.useImages ? { type: "none" } : { color: "E1E6EE", width: 1 },
      shadow: { type: "outer", color: "8A96A8", opacity: 0.35, blur: 8, offset: 3, angle: 90 } });
    s.addShape(prs.ShapeType.roundRect, { x: x + 0.25, y: top + 0.25, w: 0.62, h: 0.46, rectRadius: 0.06,
      fill: { color: C.brand }, line: { type: "none" } });
    s.addText(String(i + 1).padStart(2, "0"),
      { x: x + 0.25, y: top + 0.25, w: 0.62, h: 0.46, fontFace: F.title, fontSize: 13, bold: true,
        color: C.white, align: "center", valign: "middle", margin: 0 });
    s.addText(it, { x: x + 0.25, y: top + 0.95, w: cw - 0.5, h: ch - 1.2, fontFace: F.body,
      fontSize: fitSize(it, cw - 0.5, ch - 1.2, 15, 9, 1.2), color: C.cardInk,
      align: "left", valign: "top", lineSpacingMultiple: 1.15, margin: 0 });
  });
}

// ── 표형 본문 ──
function tableSlide(sl) {
  const s = prs.addSlide();
  bandHeader(s, sl.title);
  const top = lead(s, sl.lead);
  const rows = sl.rows || [];
  if (!rows.length) return;
  const cols = Math.max(...rows.map((r) => r.length));
  const tblRows = rows.map((r, ri) => r.map((cell) => ({
    text: String(cell), options: {
      fontFace: ri === 0 ? F.title : F.body, fontSize: ri === 0 ? 14 : 12.5, bold: ri === 0,
      color: ri === 0 ? C.white : C.cardInk, fill: { color: ri === 0 ? C.brand : C.cardBg },
      align: "left", valign: "middle" } })));
  s.addTable(tblRows, { x: 0.8, y: top, w: W - 1.6, colW: Array(cols).fill((W - 1.6) / cols),
    border: { type: "solid", color: "C9D2E0", pt: 0.5 }, rowH: 0.5, margin: 4 });
}

// ── 텍스트(불릿) 본문 ──
function textSlide(sl) {
  const s = prs.addSlide();
  bandHeader(s, sl.title);
  const top = lead(s, sl.lead);
  const box = { x: 0.8, y: top, w: W - 1.6, h: 6.9 - top };
  s.addShape(prs.ShapeType.roundRect, { ...box, rectRadius: 0.1, fill: { color: C.cardBg },
    line: T.useImages ? { type: "none" } : { color: "E1E6EE", width: 1 },
    shadow: { type: "outer", color: "8A96A8", opacity: 0.3, blur: 8, offset: 3, angle: 90 } });
  const bullets = (sl.bullets || []).slice(0, 8);
  const bfs = fitList(bullets, box.w - 1.1, box.h - 0.7, 15, 10, 1.25, 8);
  s.addText(bullets.map((b, i) => ({ text: b, options: { bullet: { code: "2022" }, breakLine: i < bullets.length - 1 } })),
    { x: box.x + 0.4, y: box.y + 0.35, w: box.w - 0.8, h: box.h - 0.7, fontFace: F.body, fontSize: bfs,
      color: C.cardInk, align: "left", valign: "top", paraSpaceAfter: 8, margin: 0 });
}

// ── 지표(큰 숫자 스탯 카드) ──
function metricsSlide(sl) {
  const s = prs.addSlide();
  bandHeader(s, sl.title);
  const top = lead(s, sl.lead);
  const items = (sl.metrics || []).slice(0, 4).filter((m) => m && (m.value || m.label));
  const n = items.length || 1, gap = 0.35, left0 = 0.8, usable = W - 1.6;
  const cw = (usable - gap * (n - 1)) / n, ch = 6.9 - top;
  items.forEach((m, i) => {
    const x = left0 + i * (cw + gap);
    s.addShape(prs.ShapeType.roundRect, { x, y: top, w: cw, h: ch, rectRadius: 0.1,
      fill: { color: C.cardBg }, line: T.useImages ? { type: "none" } : { color: "E1E6EE", width: 1 },
      shadow: { type: "outer", color: "8A96A8", opacity: 0.32, blur: 8, offset: 3, angle: 90 } });
    s.addShape(prs.ShapeType.rect, { x: x + 0.3, y: top + 0.35, w: 0.5, h: 0.08, fill: { color: C.brand }, line: { type: "none" } });
    s.addText(String(m.value || ""), { x: x + 0.28, y: top + 0.55, w: cw - 0.56, h: 1.1, fontFace: F.title,
      fontSize: fitSize(m.value, cw - 0.56, 1.05, 40, 18, 1.05), bold: true, color: C.hero,
      align: "left", valign: "middle", margin: 0 });
    s.addText(String(m.label || ""), { x: x + 0.3, y: top + 1.7, w: cw - 0.6, h: 0.5, fontFace: F.body,
      fontSize: fitSize(m.label, cw - 0.6, 0.5, 16, 11), bold: true, color: C.brand,
      align: "left", valign: "top", margin: 0 });
    if (m.desc)
      s.addText(String(m.desc), { x: x + 0.3, y: top + 2.25, w: cw - 0.6, h: ch - 2.5, fontFace: F.body,
        fontSize: fitSize(m.desc, cw - 0.6, ch - 2.5, 13, 9, 1.2), color: C.gray,
        align: "left", valign: "top", lineSpacingMultiple: 1.2, margin: 0 });
  });
}

// ── 도넛(가운데 라벨) ──
function doughnut(s, chart, x, y, w, h) {
  s.addChart(prs.ChartType.doughnut, [{ name: chart.name || "비율", labels: chart.cats.map(String), values: chart.vals }], {
    x, y, w, h, chartColors: [C.brand, "C3CEE0", C.med, C.sky], holeSize: 62,
    showLegend: true, legendPos: "b", legendColor: C.gray, legendFontSize: 10,
    showValue: false, showTitle: false, dataBorder: { pt: 2, color: T.useImages ? "ECECEC" : (T.coverBg || "FFFFFF") },
  });
  if (chart.center)
    s.addText(String(chart.center), { x, y: y + h / 2 - 0.75, w, h: 0.9, fontFace: F.title, fontSize: 15,
      bold: true, color: C.hero, align: "center", valign: "middle", margin: 0 });
}

// ── 비교(2열 대비, 가운데 도넛 옵션) ──
function compareColumn(s, col, accent, x, w, top, h) {
  s.addShape(prs.ShapeType.roundRect, { x, y: top, w, h, rectRadius: 0.09, fill: { color: C.cardBg },
    line: T.useImages ? { type: "none" } : { color: "E1E6EE", width: 1 },
    shadow: { type: "outer", color: "8A96A8", opacity: 0.28, blur: 7, offset: 3, angle: 90 } });
  s.addShape(prs.ShapeType.roundRect, { x, y: top, w, h: 0.62, rectRadius: 0.09, fill: { color: accent }, line: { type: "none" } });
  s.addShape(prs.ShapeType.rect, { x, y: top + 0.31, w, h: 0.31, fill: { color: accent }, line: { type: "none" } });
  s.addText(String(col.name || ""), { x: x + 0.25, y: top, w: w - 0.5, h: 0.62, fontFace: F.title,
    fontSize: fitSize(col.name, w - 0.5, 0.58, 15, 10), bold: true, color: "FFFFFF",
    align: "left", valign: "middle", margin: 0 });
  const pts = (col.points || []).slice(0, 6);
  const pfs = fitList(pts, w - 0.9, h - 1.1, 13.5, 9, 1.25, 8);
  s.addText(pts.map((p, i) => ({ text: String(p), options: { bullet: { code: "2022" }, breakLine: i < pts.length - 1 } })),
    { x: x + 0.3, y: top + 0.85, w: w - 0.6, h: h - 1.1, fontFace: F.body, fontSize: pfs, color: C.hero,
      align: "left", valign: "top", paraSpaceAfter: 8, margin: 0 });
}
function compareSlide(sl) {
  const s = prs.addSlide();
  bandHeader(s, sl.title);
  const top = lead(s, sl.lead);
  const h = 6.9 - top;
  const c = sl.chart;
  const hasDonut = c && Array.isArray(c.vals) && c.vals.length;
  const L = sl.left || {}, R = sl.right || {};
  if (hasDonut) {  // 좌 컬럼 · 가운데 도넛 · 우 컬럼
    compareColumn(s, L, C.brand, 0.8, 3.85, top, h);
    doughnut(s, c, 4.85, top + 0.1, 3.6, h - 0.2);
    compareColumn(s, R, C.gray, 8.68, 3.85, top, h);
  } else {          // 좌/우 2열
    compareColumn(s, L, C.brand, 0.8, 5.65, top, h);
    compareColumn(s, R, C.gray, 6.9, 5.65, top, h);
  }
}

// ── 디자인 보조: 콘텐츠(불릿+차트/이미지+강조) ──
function bulletsBlock(s, bullets, x, y, w, h) {
  const texts = bullets.map((b) => (typeof b === "string" ? b : b.text));
  const fs = fitList(texts, w - 0.3, h, 15, 10, 1.25, 9);
  s.addText(bullets.map((b, i) => {
    const em = typeof b === "object" && b.emphasis;
    return { text: (typeof b === "string" ? b : b.text), options: {
      bullet: { code: "2022" }, bold: !!em, color: em ? C.brand : C.hero,
      breakLine: i < bullets.length - 1 } };
  }), { x, y, w, h, fontFace: F.body, fontSize: fs, valign: "top", paraSpaceAfter: 9, margin: 0 });
}
function chartBlock(s, chart, x, y, w, h) {
  if (chart.kind === "doughnut") return doughnut(s, chart, x, y, w, h);
  // 막대 + 추세선(선형회귀) 복합차트
  if (chart.trend && chart.kind !== "pie" && chart.kind !== "line") {
    const v = chart.vals, n = v.length;
    let sx = 0, sy = 0, sxy = 0, sxx = 0;
    v.forEach((val, i) => { sx += i; sy += val; sxy += i * val; sxx += i * i; });
    const slope = (n * sxx - sx * sx) ? (n * sxy - sx * sy) / (n * sxx - sx * sx) : 0;
    const intc = (sy - slope * sx) / n;
    const trend = v.map((_, i) => Math.round((intc + slope * i) * 100) / 100);
    const labels = chart.cats.map(String);
    return s.addChart([
      { type: prs.ChartType.bar, data: [{ name: chart.name || "값", labels, values: v }],
        options: { chartColors: [C.brand] } },
      { type: prs.ChartType.line, data: [{ name: "추세", labels, values: trend }],
        options: { chartColors: [C.med], lineSize: 2, lineDataSymbol: "none" } },
    ], { x, y, w, h, showLegend: true, legendPos: "b", legendColor: C.gray, legendFontSize: 10,
         showTitle: false, catAxisLabelColor: C.gray, valAxisLabelColor: C.gray,
         valGridLine: { color: "DDE3EC", size: 0.5 }, catGridLine: { style: "none" } });
  }
  const kind = chart.kind === "pie" ? prs.ChartType.pie : chart.kind === "line" ? prs.ChartType.line : prs.ChartType.bar;
  s.addChart(kind, [{ name: chart.name || "값", labels: chart.cats.map(String), values: chart.vals }], {
    x, y, w, h, chartColors: [C.brand, C.med, C.sky, "9BB4D4", C.hero, C.teal],
    showLegend: chart.kind === "pie", legendPos: "b", legendColor: C.gray, legendFontSize: 10,
    showValue: chart.kind !== "line", dataLabelColor: chart.kind === "pie" ? C.white : C.hero, dataLabelFontSize: 10,
    showTitle: false, catAxisLabelColor: C.gray, valAxisLabelColor: C.gray,
    valGridLine: { color: "DDE3EC", size: 0.5 }, catGridLine: { style: "none" },
  });
}
function imageBlock(s, image, x, y, w, h) {
  if (image.path && image.mode === "background") {
    s.addImage({ path: image.path, x: 0, y: 1.05, w: W, h: 6.45, sizing: { type: "cover", w: W, h: 6.45 }, transparency: image.transparency || 0 });
    return;
  }
  if (image.path) { s.addImage({ path: image.path, x, y, w, h, sizing: { type: "cover", w, h } }); return; }
  // 폴백: 이미지 자리 표시(스톡 검색 미설정 시)
  s.addShape(prs.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.1, fill: { color: C.surface2 }, line: { color: C.med, width: 1, dashType: "dash" } });
  s.addText(`🖼  이미지 자리\n"${image.query || ""}"`, { x, y, w, h, fontFace: F.body, fontSize: 13, color: C.gray, align: "center", valign: "middle", margin: 0 });
}
function contentSlide(sl) {
  const s = prs.addSlide();
  bandHeader(s, sl.title);
  // 그라데이션 배경 — 슬라이드별 지시(gradientPath) 우선, 없으면 테마 폼의 전역 그라데이션(T.gradientBg)
  const gp = sl.gradientPath || T.gradientBg;
  if (gp)
    s.addImage({ path: gp, x: 0, y: 1.05, w: W, h: 6.45, sizing: { type: "cover", w: W, h: 6.45 } });
  const top = lead(s, sl.lead);
  // 유효성 가드: 데이터 없는 차트/설명 없는 이미지는 무시(렌더 크래시 방지)
  const c = sl.chart;
  const validChart = c && Array.isArray(c.cats) && c.cats.length && Array.isArray(c.vals) && c.vals.length && c.cats.length === c.vals.length;
  const img = sl.image;
  const validImg = img && (img.path || img.query);
  const bgImg = validImg && img.mode === "background" && img.path; // 배경은 실제 파일 있을 때만
  const sideImg = validImg && img.mode !== "background";
  if (bgImg) imageBlock(s, img, 0, 0, 0, 0);
  const hasSideVisual = validChart || sideImg;
  const bw = hasSideVisual ? 5.7 : (W - 1.6);
  if (sl.bullets && sl.bullets.length) bulletsBlock(s, sl.bullets, 0.8, top + 0.05, bw, 6.7 - top);
  if (validChart) chartBlock(s, c, 6.75, top, 5.75, 6.55 - top);
  else if (sideImg) imageBlock(s, img, 6.75, top, 5.75, 6.55 - top);
}

// ── 마무리 ──
function closing() {
  const s = prs.addSlide();
  if (T.useImages) {
    s.background = { color: C.body };
    s.addShape(prs.ShapeType.roundRect, { x: 9.55, y: 0, w: 3.783, h: 7.5, rectRadius: 0.5,
      fill: { color: C.hero }, line: { type: "none" } });
    s.addImage({ path: A("logo/logo_color.png"), x: 0.9, y: 0.7, w: 2.3, h: 2.3 / 8.16 });
  } else {
    s.background = { color: T.closingBg };
    if (T.logo) s.addImage({ path: A(T.logo), x: 0.9, y: 0.7, w: 2.3, h: 2.3 / 8.16 });
    s.addShape(prs.ShapeType.rect, { x: 0.94, y: 2.35, w: 1.1, h: 0.09, fill: { color: T.accent }, line: { type: "none" } });
  }
  s.addText("감사합니다.", { x: 0.9, y: 2.6, w: 8.0, h: 1.2, fontFace: F.title, fontSize: 50, bold: true, color: C.brand, margin: 0 });
  s.addText(plan.tagline || "Proprietary Technology, Ultimate Result",
    { x: 0.92, y: 3.9, w: 8.0, h: 0.6, fontFace: F.body, fontSize: 20, color: C.gray, margin: 0 });
  s.addText(plan.contact || "Contact: contact@gambalabs.ai  |  https://gambalabs.ai",
    { x: 0.92, y: 6.2, w: 8.0, h: 0.5, fontFace: F.body, fontSize: 13, color: C.hero, margin: 0 });
}

// ── 조립 ──
cover();
const slides = plan.slides || [];
if (slides.length > 2) toc(slides.map((s) => s.title || ""));
for (const sl of slides) {
  if (sl.type === "table") tableSlide(sl);
  else if (sl.type === "cards") cardsSlide(sl);
  else if (sl.type === "metrics") metricsSlide(sl);
  else if (sl.type === "compare") compareSlide(sl);
  else if (sl.type === "content") contentSlide(sl);
  else textSlide(sl);
}
closing();

prs.writeFile({ fileName: outPath }).then((f) => console.log("WROTE", f));

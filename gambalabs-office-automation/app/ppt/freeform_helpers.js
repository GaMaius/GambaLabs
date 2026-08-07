// Smart PPT Layout Helpers — Premium Design System (Claude / Gamma Level)
const W = 13.333, H = 7.5;

// 배경색이 밝은지 판정 — 표지 글자색을 뒤집을 때 쓴다.
function isLight(hex) {
  const h = String(hex || "").replace("#", "");
  if (h.length !== 6) return true;
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150;
}

function fitText(text, wIn, hIn, base = 18, min = 11, ls = 1.15) {
  const str = String(text || "").trim();
  const len = str.length || 1;
  for (let p = base; p >= min; p -= 0.5) {
    const charW = (p / 72) * 0.92;
    const cpl = Math.max(1, Math.floor(wIn / charW));
    const lineH = (p / 72) * ls;
    const maxLines = Math.max(1, Math.floor(hIn / lineH));
    if (len <= cpl * maxLines * 0.92) return p;
  }
  return min;
}

function addCover(prs, title, subtitle, presenter, themeInfo, assetsDir) {
  const slide = prs.addSlide();
  const A = (p) => path.join(assetsDir, p);
  const C = themeInfo.C || {}, F = themeInfo.F || {}, useImages = themeInfo.useImages;

  if (useImages) {
    slide.background = { path: A("backgrounds/bg_cover.png") };
    try { slide.addImage({ path: A("logo/logo_white.png"), x: 10.05, y: 0.5, w: 2.55, h: 0.31 }); } catch(e){}
    slide.addShape('roundRect', {
      x: 9.55, y: 3.05, w: 1.95, h: 5.0, rectRadius: 0.97,
      fill: { color: "EAEAEA", transparency: 88 }, line: { type: "none" }
    });
    slide.addText(title, {
      x: 0.9, y: 2.0, w: 8.5, h: 2.2, fontFace: F.title || "맑은 고딕", fontSize: fitText(title, 8.5, 2.2, 40, 24),
      bold: true, color: C.white || "FFFFFF", align: "left", valign: "top", margin: 0
    });
    if (subtitle) {
      slide.addText(subtitle, {
        x: 0.92, y: 4.35, w: 8.2, h: 0.8, fontFace: F.body || "맑은 고딕", fontSize: fitText(subtitle, 8.2, 0.8, 20, 14),
        color: C.muted || "C9D4E8", margin: 0
      });
    }
    if (presenter) {
      slide.addText(presenter, {
        x: 0.92, y: 5.8, w: 8.0, h: 1.0, fontFace: F.body || "맑은 고딕", fontSize: 14, color: C.white || "FFFFFF", margin: 0
      });
    }
  } else {
    // 이미지 에셋이 없을 때의 단색 표지.
    // 주의: C.hero는 '글자색'이다(테마 폼에서 ink가 그대로 들어온다). 이걸 배경으로 쓰면
    // 글자색을 검정으로 고른 사용자의 표지가 새까맣게 나온다. 표지 배경은 coverBg를 쓴다.
    const bg = themeInfo.coverBg || C.brand || C.hero || "123979";
    const onDark = !isLight(bg);
    const ink = themeInfo.coverInk || (onDark ? (C.white || "FFFFFF") : (C.hero || "1A1A1A"));
    const sub = themeInfo.coverSub || (onDark ? (C.muted || "C9D4E8") : (C.brand || "0038A3"));
    slide.background = { color: bg };
    // Decorative side arch accent
    slide.addShape('roundRect', {
      x: 10.2, y: 1.0, w: 2.5, h: 5.5, rectRadius: 1.2,
      fill: { color: onDark ? (C.white || "FFFFFF") : (C.brand || "0038A3"), transparency: 92 }, line: { type: "none" }
    });
    slide.addText(title, {
      x: 1.0, y: 2.0, w: 9.0, h: 2.2, fontFace: F.title || "맑은 고딕", fontSize: fitText(title, 9.0, 2.2, 42, 26),
      bold: true, color: ink, align: "left", valign: "middle", margin: 0
    });
    if (subtitle) {
      slide.addText(subtitle, {
        x: 1.05, y: 4.4, w: 8.5, h: 0.8, fontFace: F.body || "맑은 고딕", fontSize: fitText(subtitle, 8.5, 0.8, 20, 14),
        color: sub, align: "left", margin: 0
      });
    }
    if (presenter) {
      slide.addText(presenter, {
        x: 1.05, y: 5.8, w: 8.5, h: 0.8, fontFace: F.body || "맑은 고딕", fontSize: 14, color: sub, align: "left", margin: 0
      });
    }
  }
  return slide;
}

function addHeader(slide, title, themeInfo, assetsDir) {
  const A = (p) => path.join(assetsDir, p);
  const C = themeInfo.C || {}, F = themeInfo.F || {}, useImages = themeInfo.useImages;
  
  if (useImages) {
    slide.background = { color: C.body || "ECECEC" };
    slide.addImage({ path: A("backgrounds/band.png"), x: 0, y: 0, w: W, h: 1.05 });
    try { slide.addImage({ path: A("logo/icon_white.png"), x: 0.4, y: 0.27, w: 1.1, h: 0.72 }); } catch(e){}
    slide.addText(title, {
      x: 0, y: 0, w: W, h: 1.05, fontFace: F.title || "맑은 고딕", fontSize: fitText(title, 10, 1.05, 28, 18),
      bold: true, color: C.white || "FFFFFF", align: "center", valign: "middle", margin: 0
    });
  } else {
    slide.background = { color: C.body || "F4F6FA" };
    slide.addShape('rect', { x: 0, y: 0, w: W, h: 1.05, fill: { color: C.brand || "0038A3" }, line: { type: "none" } });
    slide.addText(title, {
      x: 0, y: 0, w: W, h: 1.05, fontFace: F.title || "맑은 고딕", fontSize: fitText(title, 10, 1.05, 28, 18),
      bold: true, color: C.white || "FFFFFF", align: "center", valign: "middle", margin: 0
    });
  }
}

function addStats(slide, statsList, themeInfo) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const n = statsList.length;
  if (n === 0) return;

  const cardH = 3.2;
  const topY = 2.1; // Vertically centered
  const leftX = 0.9;
  const availW = W - 1.8;
  const gapX = 0.4;
  const cardW = (availW - gapX * (n - 1)) / n;

  statsList.forEach((st, i) => {
    const x = leftX + i * (cardW + gapX);
    const y = topY;

    // Card Body
    slide.addShape('roundRect', {
      x, y, w: cardW, h: cardH, rectRadius: 0.15,
      fill: { color: C.cardBg || "FFFFFF" }, line: { type: "none" },
      shadow: { type: "outer", color: "8A96A8", opacity: 0.22, blur: 8, offset: 3, angle: 90 }
    });

    // Top Accent Color Bar
    slide.addShape('roundRect', {
      x, y, w: cardW, h: 0.12, rectRadius: 0.05,
      fill: { color: C.brand || "0038A3" }, line: { type: "none" }
    });

    // Hero Stat Number
    const numText = String(st.num || "");
    const fontSize = fitText(numText, cardW - 0.4, 1.2, 44, 28);
    slide.addText(numText, {
      x: x + 0.2, y: y + 0.5, w: cardW - 0.4, h: 1.2,
      fontFace: F.title || "맑은 고딕", fontSize, bold: true,
      color: C.hero || "123979", align: "center", valign: "middle", margin: 0
    });

    // Label / Description below
    const labelText = String(st.label || "");
    slide.addText(labelText, {
      x: x + 0.2, y: y + 1.8, w: cardW - 0.4, h: 1.1,
      fontFace: F.body || "맑은 고딕", fontSize: fitText(labelText, cardW - 0.4, 1.1, 16, 12),
      color: C.gray || "5A6472", align: "center", valign: "top",
      lineSpacingMultiple: 1.15, margin: 0
    });
  });
}

function addCards(slide, cardsList, themeInfo) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const n = cardsList.length;
  if (n === 0) return;

  // Adapt card height to avoid giant empty white space
  let rows = 1, cols = n;
  if (n === 4) { rows = 2; cols = 2; }
  else if (n >= 5) { rows = 2; cols = Math.ceil(n / 2); }

  const availW = W - 1.6;
  const leftX = 0.8;
  const gapX = 0.4;
  const gapY = 0.3;

  // Determine ideal card height based on rows
  const idealH = rows === 1 ? 4.2 : 2.4;
  const topY = 1.05 + (H - 1.05 - (idealH * rows + gapY * (rows - 1))) / 2; // Center vertically
  const cardW = (availW - gapX * (cols - 1)) / cols;

  cardsList.forEach((card, i) => {
    const r = Math.floor(i / cols);
    const c = i % cols;
    const x = leftX + c * (cardW + gapX);
    const y = topY + r * (idealH + gapY);

    slide.addShape('roundRect', {
      x, y, w: cardW, h: idealH, rectRadius: 0.12,
      fill: { color: C.cardBg || "FFFFFF" }, line: { type: "none" },
      shadow: { type: "outer", color: "8A96A8", opacity: 0.22, blur: 8, offset: 3, angle: 90 }
    });

    // Left Title Accent Bar
    slide.addShape('rect', {
      x, y: y + 0.3, w: 0.08, h: 0.5,
      fill: { color: C.brand || "0038A3" }, line: { type: "none" }
    });

    const innerMargin = 0.25;
    const contentW = cardW - innerMargin * 2 - 0.1;
    let currY = y + 0.25;

    if (card.title || card.num) {
      const t = card.title || card.num;
      const isNum = Boolean(card.num);
      const fontSize = fitText(t, contentW, 0.6, 20, 15);
      slide.addText(t, {
        x: x + innerMargin + 0.1, y: currY, w: contentW, h: 0.6,
        fontFace: F.title || "맑은 고딕", fontSize, bold: true,
        color: C.brand || "0038A3", align: "left", valign: "middle", margin: 0
      });
      currY += 0.65;
    }

    const bodyText = card.body || card.label || (Array.isArray(card.items) ? card.items.join("\n• ") : card.items) || "";
    if (bodyText) {
      const bodyH = idealH - (currY - y) - 0.2;
      let textContent = bodyText;
      if (Array.isArray(card.items)) {
        textContent = card.items.map(it => `• ${it}`).join("\n");
      }

      const fontSize = fitText(textContent, contentW, bodyH, 15, 11);

      slide.addText(textContent, {
        x: x + innerMargin, y: currY, w: contentW + 0.1, h: bodyH,
        fontFace: F.body || "맑은 고딕", fontSize, color: C.gray || "5A6472",
        align: "left", valign: "top", lineSpacingMultiple: 1.2, margin: 0
      });
    }
  });
}

function addCompare(slide, leftCol, rightCol, themeInfo) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const cardW = 5.4;
  const cardH = 4.2;
  const topY = 1.9; // Vertically centered
  const gapX = 0.53;
  const leftX = 0.9;

  const cols = [
    { data: leftCol, x: leftX, tag: "기존 방식 (As-Is)", color: C.gray || "5A6472" },
    { data: rightCol, x: leftX + cardW + gapX, tag: "개선 방식 (To-Be)", color: C.brand || "0038A3" }
  ];

  cols.forEach((colObj) => {
    const { data, x, tag, color } = colObj;
    
    // Card Container
    slide.addShape('roundRect', {
      x, y: topY, w: cardW, h: cardH, rectRadius: 0.15,
      fill: { color: C.cardBg || "FFFFFF" }, line: { type: "none" },
      shadow: { type: "outer", color: "8A96A8", opacity: 0.25, blur: 8, offset: 3, angle: 90 }
    });

    // Top Header Pill Tag
    slide.addShape('roundRect', {
      x: x + 0.3, y: topY + 0.3, w: 2.2, h: 0.4, rectRadius: 0.08,
      fill: { color }, line: { type: "none" }
    });
    slide.addText(tag, {
      x: x + 0.3, y: topY + 0.3, w: 2.2, h: 0.4,
      fontFace: F.title || "맑은 고딕", fontSize: 12, bold: true,
      color: "FFFFFF", align: "center", valign: "middle", margin: 0
    });

    // Column Title
    const titleText = data.title || "";
    slide.addText(titleText, {
      x: x + 0.3, y: topY + 0.85, w: cardW - 0.6, h: 0.6,
      fontFace: F.title || "맑은 고딕", fontSize: fitText(titleText, cardW - 0.6, 0.6, 22, 16),
      bold: true, color: C.hero || "123979", align: "left", valign: "middle", margin: 0
    });

    // Bullet Items
    const items = data.items || [];
    const textContent = Array.isArray(items) ? items.map(it => `• ${it}`).join("\n\n") : String(items);
    const bodyH = cardH - 1.6;
    slide.addText(textContent, {
      x: x + 0.3, y: topY + 1.5, w: cardW - 0.6, h: bodyH,
      fontFace: F.body || "맑은 고딕", fontSize: fitText(textContent, cardW - 0.6, bodyH, 15, 11),
      color: C.gray || "5A6472", align: "left", valign: "top",
      lineSpacingMultiple: 1.2, margin: 0
    });
  });
}

// 선형회귀 추세값
function linearTrend(values) {
  const n = values.length;
  if (!n) return [];
  let sx = 0, sy = 0, sxy = 0, sxx = 0;
  values.forEach((v, i) => { sx += i; sy += v; sxy += i * v; sxx += i * i; });
  const den = n * sxx - sx * sx;
  const slope = den ? (n * sxy - sx * sy) / den : 0;
  const intc = (sy - slope * sx) / n;
  return values.map((_, i) => Math.round((intc + slope * i) * 100) / 100);
}

/**
 * chartData = { kind: "bar|line|pie|doughnut", labels: [...],
 *               series: [{name, values}], trend: true, grid: true }
 */
function addChart(slide, title, chartData, themeInfo, prs, rect) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const r = rect || {};
  const x = r.x != null ? r.x : 1.0, y = r.y != null ? r.y : 1.6;
  const w = r.w != null ? r.w : 11.33, h = r.h != null ? r.h : 4.8;

  if (!chartData || !chartData.labels || !chartData.series || !chartData.series.length) {
    addCards(slide, [{ title: title, body: "차트 데이터 준비 중" }], themeInfo);
    return;
  }

  const kind = String(chartData.kind || "bar").toLowerCase();
  const labels = chartData.labels.map(String);
  const palette = [C.brand || "0038A3", C.med || "1970AE", C.sky || "4E86C6",
                   "9BB4D4", C.teal || "2A9D99", C.hero || "123979"];
  // 격자선은 기본 ON — 값을 읽을 수 있어야 차트 구실을 한다.
  const grid = chartData.grid === false ? { style: "none" } : { color: "DDE3EC", size: 0.5 };
  const axis = {
    showTitle: false, catAxisLabelColor: C.gray || "5A6472", valAxisLabelColor: C.gray || "5A6472",
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    valGridLine: grid, catGridLine: { style: "none" },
  };

  // 원형·도넛
  if (kind === "pie" || kind === "doughnut") {
    const s0 = chartData.series[0];
    slide.addChart(kind === "doughnut" ? prs.ChartType.doughnut : prs.ChartType.pie,
      [{ name: s0.name || "비율", labels, values: s0.values }], {
        x, y, w, h, chartColors: palette,
        showLegend: true, legendPos: "b", legendColor: C.gray || "5A6472", legendFontSize: 11,
        showValue: true, showPercent: false,
        dataLabelColor: C.white || "FFFFFF", dataLabelFontSize: 12, dataLabelFormatCode: '0"%"',
        holeSize: kind === "doughnut" ? 55 : undefined,
        showTitle: false,
      });
    return;
  }

  // 막대 + 추세선(복합 차트)
  if (chartData.trend && kind !== "line") {
    const s0 = chartData.series[0];
    const trend = linearTrend(s0.values);
    slide.addChart([
      { type: prs.ChartType.bar,
        data: [{ name: s0.name || "값", labels, values: s0.values }],
        options: { chartColors: [palette[0]] } },
      { type: prs.ChartType.line,
        data: [{ name: "추세", labels, values: trend }],
        options: { chartColors: [C.med || "1970AE"], lineSize: 2.5, lineDataSymbol: "none" } },
    ], Object.assign({
      x, y, w, h,
      showLegend: true, legendPos: "b", legendColor: C.gray || "5A6472", legendFontSize: 11,
    }, axis));
    return;
  }

  const type = kind === "line" ? prs.ChartType.line : prs.ChartType.bar;
  const data = chartData.series.map((s) => ({
    name: s.name || "지표", labels, values: s.values,
  }));
  slide.addChart(type, data, Object.assign({
    x, y, w, h, chartColors: palette,
    showLegend: data.length > 1, legendPos: "b", legendColor: C.gray || "5A6472", legendFontSize: 11,
    showValue: kind !== "line", dataLabelColor: C.hero || "123979", dataLabelFontSize: 11,
  }, axis));
}

/** 지정 영역에 그라데이션 패널(미리 렌더한 PNG)을 깐다. 카드보다 먼저 호출할 것. */
function addGradientPanel(slide, imgPath, rect) {
  if (!imgPath) return;
  const r = rect || {};
  slide.addImage({
    path: imgPath,
    x: r.x != null ? r.x : 0, y: r.y != null ? r.y : 1.05,
    w: r.w != null ? r.w : W, h: r.h != null ? r.h : (H - 1.05),
  });
}

/**
 * 슬라이드 이미지. mode="background"면 헤더 아래 전면, 아니면 지정 영역.
 * transparency(0~100)로 반투명 배경 처리.
 */
function addSlideImage(slide, imgPath, opts) {
  if (!imgPath) return;
  const o = opts || {};
  if (o.mode === "background") {
    slide.addImage({
      path: imgPath, x: 0, y: 1.05, w: W, h: H - 1.05,
      sizing: { type: "cover", w: W, h: H - 1.05 },
      transparency: o.transparency != null ? o.transparency : 70,
    });
    return;
  }
  const x = o.x != null ? o.x : 7.0, y = o.y != null ? o.y : 1.6;
  const w = o.w != null ? o.w : 5.6, h = o.h != null ? o.h : 4.8;
  slide.addImage({
    path: imgPath, x, y, w, h, sizing: { type: "contain", w, h },
    transparency: o.transparency || 0,
  });
}

module.exports = { fitText, isLight, addCover, addHeader, addCards, addStats,
                   addCompare, addChart, addGradientPanel, addSlideImage };

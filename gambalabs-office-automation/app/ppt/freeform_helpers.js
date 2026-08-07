// Smart PPT Layout Helpers — Premium Design System (Claude / Gamma Level)
// 슬라이드 크기는 헤더에서 주입한다(비율 16:9 / 4:3).
const W = (typeof SLIDE_W !== "undefined") ? SLIDE_W : 13.333;
const H = (typeof SLIDE_H !== "undefined") ? SLIDE_H : 7.5;

// ── 레이아웃 그리드(모든 헬퍼가 공유하는 단 하나의 기준) ──────────────
// 이 값을 helpers 안에서만 쓰는 게 아니라 프롬프트에도 같은 숫자로 적어 둔다.
// 예전에는 모델이 매번 다른 y를 골라 본문이 위쪽 1/3에만 몰렸다.
const HEADER_H = 1.05;   // 상단 밴드
const MARGIN = 0.8;      // 좌우 여백
const LEAD_Y = HEADER_H + 0.16;   // 한 줄 요약(리드) 위치
const LEAD_H = 0.5;
const BODY_TOP = LEAD_Y + LEAD_H + 0.22;   // = 1.93  본문 시작
const BODY_BOTTOM = H - 0.62;              // = 6.88  본문 끝(아래는 푸터)
const BODY_W = W - MARGIN * 2;
const BODY_H = BODY_BOTTOM - BODY_TOP;

// 카드 공통 스타일. 테두리는 반드시 none — 지정하지 않으면 파워포인트가
// 테마 기본 검은 윤곽선을 그린다(실제로 그렇게 나왔다).
const CARD_SHADOW = { type: "outer", color: "9AA7BC", opacity: 0.28, blur: 10, offset: 3, angle: 90 };
const NO_LINE = { type: "none" };

var _pageNo = 1;   // 표지가 1. addHeader가 부를 때마다 증가.

// 배경색이 밝은지 판정 — 표지 글자색을 뒤집을 때 쓴다.
function isLight(hex) {
  const h = String(hex || "").replace("#", "");
  if (h.length !== 6) return true;
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150;
}

// 색을 섞는다(t=0이면 a, 1이면 b). 카드 배경을 본문색보다 살짝 밝게 할 때 쓴다.
function mix(a, b, t) {
  const pa = String(a || "").replace("#", ""), pb = String(b || "").replace("#", "");
  if (pa.length !== 6 || pb.length !== 6) return pa || pb || "FFFFFF";
  let out = "";
  for (let i = 0; i < 3; i++) {
    const x = parseInt(pa.slice(i * 2, i * 2 + 2), 16), y = parseInt(pb.slice(i * 2, i * 2 + 2), 16);
    out += Math.round(x + (y - x) * t).toString(16).padStart(2, "0");
  }
  return out.toUpperCase();
}

// 한글은 라틴 문자보다 넓다. 폭 계산에 반영하지 않으면 항상 최소 크기로 떨어진다.
function _weight(str) {
  let n = 0;
  for (const ch of String(str)) n += (ch.charCodeAt(0) > 0x2000) ? 1.0 : 0.55;
  return n || 1;
}

function fitText(text, wIn, hIn, base = 18, min = 11, ls = 1.15) {
  const str = String(text || "").trim();
  const len = _weight(str);
  for (let p = base; p >= min; p -= 0.5) {
    const charW = (p / 72);
    const cpl = Math.max(1, Math.floor(wIn / charW));
    const lineH = (p / 72) * ls * 1.35;
    const maxLines = Math.max(1, Math.floor(hIn / lineH));
    if (len <= cpl * maxLines * 0.94) return p;
  }
  return min;
}

// 불릿 문단. 리터럴 '•'를 쓰면 두 번째 줄이 왼쪽 끝으로 붙어(행잉 인덴트 없음)
// 글이 깨져 보인다. pptxgenjs의 bullet:true는 marL/indent를 넣어 준다.
function bulletRuns(items, opts) {
  const arr = (Array.isArray(items) ? items : [items]).map(String).filter(Boolean);
  return arr.map((t, i) => ({
    text: t,
    options: Object.assign({ bullet: true, breakLine: i < arr.length - 1 }, opts || {}),
  }));
}

function addCover(prs, title, subtitle, presenter, themeInfo, assetsDir) {
  const slide = prs.addSlide();
  const A = (p) => path.join(assetsDir, p);
  const C = themeInfo.C || {}, F = themeInfo.F || {}, useImages = themeInfo.useImages;
  _pageNo = 1;

  if (useImages) {
    slide.background = { path: A("backgrounds/bg_cover.png") };
    try { slide.addImage({ path: A("logo/logo_white.png"), x: 10.05, y: 0.5, w: 2.55, h: 0.31 }); } catch (e) {}
    // 장식 아치. y+h가 7.5을 넘으면 슬라이드 밖으로 나간다(예전 값 y3.05+h5.0=8.05).
    slide.addShape('roundRect', {
      x: 9.55, y: 1.5, w: 1.95, h: 4.6, rectRadius: 0.97,
      fill: { color: "EAEAEA", transparency: 88 }, line: NO_LINE
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
    const accent = C.brand || "0038A3";
    slide.background = { color: bg };
    // 우측 장식 패널 — 화면 끝까지 붙여야 '잘린 알약'처럼 보이지 않는다.
    slide.addShape('rect', {
      x: W - 3.6, y: 0, w: 3.6, h: H,
      fill: { color: onDark ? (C.white || "FFFFFF") : accent, transparency: onDark ? 92 : 94 }, line: NO_LINE
    });
    slide.addShape('rect', {
      x: W - 0.34, y: 0, w: 0.34, h: H, fill: { color: accent }, line: NO_LINE
    });
    // 제목 위 짧은 강조 룰
    slide.addShape('rect', { x: 1.0, y: 2.35, w: 1.0, h: 0.09, fill: { color: accent }, line: NO_LINE });
    slide.addText(title, {
      x: 1.0, y: 2.7, w: 8.4, h: 2.0, fontFace: F.title || "맑은 고딕", fontSize: fitText(title, 8.4, 2.0, 42, 26),
      bold: true, color: ink, align: "left", valign: "top", margin: 0, lineSpacingMultiple: 1.12
    });
    if (subtitle) {
      slide.addText(subtitle, {
        x: 1.02, y: 4.75, w: 8.2, h: 0.7, fontFace: F.body || "맑은 고딕", fontSize: fitText(subtitle, 8.2, 0.7, 20, 14),
        color: sub, align: "left", valign: "top", margin: 0
      });
    }
    if (presenter) {
      slide.addText(presenter, {
        x: 1.02, y: 5.95, w: 8.2, h: 0.5, fontFace: F.body || "맑은 고딕", fontSize: 13,
        color: themeInfo.coverFoot || sub, align: "left", valign: "top", margin: 0
      });
    }
  }
  return slide;
}

/**
 * 본문 슬라이드의 상단 밴드 + 제목 + 리드 + 푸터. 배경 장식(decorPath)까지 여기서
 * 함께 깐다 — 밖에서 따로 부르면 순서를 틀려 리드·푸터가 장식에 덮인다(실제로 그랬다).
 */
function addHeader(slide, title, themeInfo, assetsDir, lead, decorPath) {
  const A = (p) => path.join(assetsDir, p);
  const C = themeInfo.C || {}, F = themeInfo.F || {}, useImages = themeInfo.useImages;
  const bandInk = themeInfo.bandInk || C.white || "FFFFFF";
  _pageNo += 1;

  if (decorPath) addDecor(slide, decorPath);   // 항상 맨 먼저

  if (useImages) {
    slide.background = { color: C.body || "ECECEC" };
    slide.addImage({ path: A("backgrounds/band.png"), x: 0, y: 0, w: W, h: HEADER_H });
    try { slide.addImage({ path: A("logo/icon_white.png"), x: 0.4, y: 0.27, w: 1.1, h: 0.72 }); } catch (e) {}
    slide.addText(title, {
      x: 1.7, y: 0, w: W - 2.5, h: HEADER_H, fontFace: F.title || "맑은 고딕",
      fontSize: fitText(title, W - 2.5, 0.75, 27, 18),
      bold: true, color: bandInk, align: "left", valign: "middle", margin: 0
    });
  } else {
    slide.background = { color: C.body || "F4F6FA" };
    slide.addShape('rect', {
      x: 0, y: 0, w: W, h: HEADER_H,
      fill: { color: themeInfo.bandColor || C.brand || "0038A3" }, line: NO_LINE
    });
    slide.addText(title, {
      x: MARGIN, y: 0, w: W - MARGIN * 2, h: HEADER_H, fontFace: F.title || "맑은 고딕",
      fontSize: fitText(title, W - MARGIN * 2, 0.75, 27, 18),
      bold: true, color: bandInk, align: "left", valign: "middle", margin: 0
    });
  }
  if (lead) addLead(slide, lead, themeInfo);
  addFooter(slide, themeInfo);
}

/** 헤더 바로 아래 한 줄 요약. 제목만 덩그러니 있는 슬라이드를 막아 준다. */
function addLead(slide, text, themeInfo) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  if (!text) return;
  slide.addText(String(text), {
    x: MARGIN, y: LEAD_Y, w: BODY_W, h: LEAD_H,
    fontFace: F.body || "맑은 고딕", fontSize: fitText(text, BODY_W, LEAD_H, 16, 12),
    color: C.gray || "5A6472", align: "left", valign: "middle", margin: 0
  });
}

/** 하단 페이지 번호 + 얇은 구분선. 자동으로 붙는다(모델이 신경 쓸 필요 없음). */
function addFooter(slide, themeInfo, label) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  slide.addShape('rect', {
    x: MARGIN, y: H - 0.52, w: BODY_W, h: 0.012,
    fill: { color: mix(C.body || "F4F6FA", C.gray || "5A6472", 0.28) }, line: NO_LINE
  });
  if (label) {
    slide.addText(String(label), {
      x: MARGIN, y: H - 0.48, w: BODY_W - 1.0, h: 0.34,
      fontFace: F.body || "맑은 고딕", fontSize: 10, color: C.gray || "5A6472",
      align: "left", valign: "middle", margin: 0
    });
  }
  slide.addText(String(_pageNo), {
    x: W - MARGIN - 1.0, y: H - 0.48, w: 1.0, h: 0.34,
    fontFace: F.body || "맑은 고딕", fontSize: 10, color: C.gray || "5A6472",
    align: "right", valign: "middle", margin: 0
  });
}

// 콘텐츠가 놓일 영역. rect가 있으면 그 안에만 그린다(옆에 사진이 있을 때 자리를 비켜주기 위함).
function contentArea(rect) {
  const r = rect || {};
  return {
    x: r.x != null ? r.x : MARGIN,
    y: r.y != null ? r.y : BODY_TOP,
    w: r.w != null ? r.w : BODY_W,
    h: r.h != null ? r.h : BODY_H,
  };
}

/**
 * 카드 하나. 테두리 없음 + 그림자 + 좌측 액센트 + 행잉 인덴트 불릿.
 * o = {x,y,w,h, title, body, items, tone:"light|solid|ghost", accent}
 * 내용이 짧으면 카드 안에서 세로 가운데로 모아 준다(위에만 붙고 아래가 텅 비는 것 방지).
 */
function addCard(slide, o, themeInfo) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const tone = o.tone || "light";
  const accent = o.accent || C.brand || "0038A3";
  const bg = tone === "solid" ? accent
    : tone === "ghost" ? mix(C.body || "F4F6FA", C.white || "FFFFFF", 0.55)
    : (C.cardBg || "FFFFFF");
  const onDark = tone === "solid";
  const titleColor = onDark ? (C.white || "FFFFFF") : accent;
  const bodyColor = onDark ? mix(accent, "FFFFFF", 0.78) : (C.gray || "5A6472");

  const padX = 0.32, padY = 0.3;
  const cw = o.w - padX * 2;
  const items = Array.isArray(o.items) ? o.items.map(String).filter(Boolean) : null;
  const body = o.body != null ? String(o.body) : (o.label != null ? String(o.label) : "");

  // 카드가 크면 글자도 같이 커져야 한다. 큰 카드에 11pt 본문이면 더 휑해 보인다.
  const scale = Math.max(0, Math.min(1, (o.h - 2.2) / 2.4));
  const titleText = o.title || o.num || "";
  const titleH = titleText ? Math.min(0.85, Math.max(0.42, o.h * 0.17)) : 0;
  const titleSize = titleText ? fitText(titleText, cw, titleH, o.num ? 34 : (20 + 7 * scale), 14) : 0;

  // 큰 카드의 윗머리를 채우는 인덱스 숫자(01, 02 …). 흔한 프리미엄 덱 관용구다.
  const idx = (o.index && o.h >= 2.9) ? String(o.index) : "";
  const idxH = idx ? 0.72 : 0;

  const availH = o.h - padY * 2 - (titleText ? titleH + 0.16 : 0) - idxH;
  // 본문 글자 크기는 '카드가 크니까 무조건 15pt'가 아니라 실제 분량으로 정한다.
  const raw = items && items.length ? items.join(" ") + "  ".repeat(items.length * 3) : body;
  const size = raw ? fitText(raw, cw - (items ? 0.3 : 0), Math.min(availH, 2.6),
                             15 + 4 * scale, 10.5) : 0;

  // 내용이 카드보다 훨씬 짧으면 위에만 붙지 않게 덩어리째 세로 가운데로 모은다.
  // (카드를 본문 영역에 꽉 채우니 짧은 글이 위에 붙으면 카드 안이 텅 비어 보인다)
  let lines = 0;
  if (raw) {
    const cpl = Math.max(1, Math.floor((cw - (items ? 0.35 : 0)) / (size / 72)));
    if (items && items.length) {
      items.forEach((t) => { lines += Math.max(1, Math.ceil(_weight(t) / cpl)); });
      lines += (items.length - 1) * 0.55;                       // 항목 사이 여백
    } else {
      lines = Math.max(1, Math.ceil(_weight(body) / cpl));
    }
  }
  const bodyNeed = lines * (size / 72) * 1.32;
  const blockH = idxH + (titleText ? titleH + 0.16 : 0) + bodyNeed;
  if (o.measure) return blockH;      // addCards가 한 줄의 카드 높이를 맞추려고 먼저 잰다

  // 같은 줄의 카드들이 서로 다른 높이에서 시작하면 들쭉날쭉해 보인다 →
  // addCards가 넘겨준 공통 블록 높이로 시작점을 맞춘다.
  const useH = Math.max(blockH, o.blockH || 0);
  let top = o.y + padY;
  if (useH < o.h - padY * 2 - 0.35) top = o.y + (o.h - useH) / 2;

  slide.addShape('roundRect', {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.1,
    fill: { color: bg }, line: NO_LINE,
    shadow: tone === "ghost" ? undefined : CARD_SHADOW,
  });

  if (idx) {
    slide.addText(idx, {
      x: o.x + padX, y: top, w: cw, h: idxH,
      fontFace: F.title || "맑은 고딕", fontSize: 40, bold: true,
      color: onDark ? mix(accent, "FFFFFF", 0.45) : mix(bg, accent, 0.22),
      align: "left", valign: "middle", margin: 0
    });
    top += idxH;
  }
  if (titleText) {
    if (!onDark) {   // 제목 옆 액센트 바 — 제목 높이에 맞춰 같이 움직인다
      slide.addShape('rect', {
        x: o.x, y: top + titleH * 0.12, w: 0.075, h: titleH * 0.76,
        fill: { color: accent }, line: NO_LINE
      });
    }
    slide.addText(titleText, {
      x: o.x + padX, y: top, w: cw, h: titleH,
      fontFace: F.title || "맑은 고딕", fontSize: titleSize, bold: true,
      color: titleColor, align: "left", valign: "middle", margin: 0
    });
    top += titleH + 0.16;
  }
  const bodyH = Math.max(0.3, Math.min(o.y + o.h - padY - top, Math.max(bodyNeed, 0.3) + 0.25));
  if (items && items.length) {
    slide.addText(bulletRuns(items, { paraSpaceAfter: Math.max(4, size * 0.5) }), {
      x: o.x + padX, y: top, w: cw, h: bodyH,
      fontFace: F.body || "맑은 고딕", fontSize: size, color: bodyColor,
      align: "left", valign: "top", lineSpacingMultiple: 1.22, margin: 0
    });
  } else if (body) {
    slide.addText(body, {
      x: o.x + padX, y: top, w: cw, h: bodyH,
      fontFace: F.body || "맑은 고딕", fontSize: size,
      color: bodyColor, align: "left", valign: "top", lineSpacingMultiple: 1.25, margin: 0
    });
  }
}

/**
 * 카드 그리드. **본문 영역을 세로로 꽉 채운다.**
 * 예전에는 내용 분량으로 카드 높이를 정해서, 짧은 카드 2장이면 슬라이드 아래 절반이
 * 통째로 비었다(사용자가 지적한 바로 그 문제). 이제 카드가 영역을 채우고,
 * 짧은 내용은 카드 안에서 배치로 해결한다.
 */
function addCards(slide, cardsList, themeInfo, rect) {
  const n = (cardsList || []).length;
  if (!n) return;
  const A = contentArea(rect);

  let rows = 1, cols = n;
  if (n === 4) { rows = 2; cols = 2; }
  else if (n >= 5) { rows = 2; cols = Math.ceil(n / 2); }
  if (A.w < 6.2 && n > 1) { cols = 1; rows = n; }     // 좁은 영역이면 세로로 쌓는다

  const gapX = 0.36, gapY = 0.3;
  const cardW = (A.w - gapX * (cols - 1)) / cols;
  const cardH = (A.h - gapY * (rows - 1)) / rows;

  const opts = cardsList.map((card, i) => {
    const r = Math.floor(i / cols), c = i % cols;
    // 마지막 줄이 덜 찼으면 가운데로 모은다(왼쪽만 붙어 오른쪽이 비는 것 방지)
    const inRow = Math.min(cols, n - r * cols);
    const rowW = inRow * cardW + (inRow - 1) * gapX;
    const x0 = A.x + (A.w - rowW) / 2;
    return {
      x: x0 + c * (cardW + gapX), y: A.y + r * (cardH + gapY),
      w: cardW, h: cardH, row: r,
      title: card.title, num: card.num, body: card.body, items: card.items, label: card.label,
      tone: card.tone,
      index: card.num ? "" : String(i + 1).padStart(2, "0"),
    };
  });
  // 한 줄 안에서 제목·본문 시작선을 맞춘다(카드마다 따로 가운데 정렬하면 들쭉날쭉하다)
  const rowBlock = {};
  opts.forEach((o) => {
    const bh = addCard(slide, Object.assign({}, o, { measure: true }), themeInfo);
    rowBlock[o.row] = Math.max(rowBlock[o.row] || 0, bh);
  });
  opts.forEach((o) => addCard(slide, Object.assign({}, o, { blockH: rowBlock[o.row] }), themeInfo));
}

/** 큰 수치 카드. 카드가 본문 영역을 채우고 숫자·라벨은 가운데로 모은다. */
function addStats(slide, statsList, themeInfo, rect) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const n = (statsList || []).length;
  if (!n) return;

  const A = contentArea(rect);
  const gapX = 0.36;
  // 카드 하나가 본문 폭을 통째로 먹으면 흰 벌판에 숫자 하나가 떠 있는 꼴이 된다.
  // 개수가 적으면 폭을 제한하고 가운데로 모은다.
  const maxW = n === 1 ? Math.min(A.w, 6.2) : n === 2 ? Math.min((A.w - gapX) / 2, 5.4) : A.w / n;
  const cardW = Math.min((A.w - gapX * (n - 1)) / n, maxW);
  const rowW = cardW * n + gapX * (n - 1);
  const x0 = A.x + (A.w - rowW) / 2;
  const cardH = A.h;

  statsList.forEach((st, i) => {
    const x = x0 + i * (cardW + gapX);
    const y = A.y;
    const accent = C.brand || "0038A3";

    slide.addShape('roundRect', {
      x, y, w: cardW, h: cardH, rectRadius: 0.1,
      fill: { color: C.cardBg || "FFFFFF" }, line: NO_LINE, shadow: CARD_SHADOW
    });
    slide.addShape('rect', { x, y, w: cardW, h: 0.11, fill: { color: accent }, line: NO_LINE });

    const numText = String(st.num || st.value || "");
    const labelText = String(st.label || "");
    const descText = String(st.desc || "");
    // 숫자 + 라벨(+설명) 덩어리를 카드 세로 가운데에 놓는다.
    const numH = Math.min(1.5, cardH * 0.34);
    const labelH = labelText ? Math.min(0.66, cardH * 0.16) : 0;
    const descH = descText ? Math.min(1.1, cardH * 0.24) : 0;
    const blockH = numH + labelH + descH + (labelH ? 0.1 : 0) + (descH ? 0.12 : 0);
    let cy = y + Math.max(0.35, (cardH - blockH) / 2);

    slide.addText(numText, {
      x: x + 0.25, y: cy, w: cardW - 0.5, h: numH,
      fontFace: F.title || "맑은 고딕", fontSize: fitText(numText, cardW - 0.5, numH, 54, 26),
      bold: true, color: accent, align: "center", valign: "middle", margin: 0
    });
    cy += numH + (labelH ? 0.1 : 0);
    if (labelText) {
      slide.addText(labelText, {
        x: x + 0.25, y: cy, w: cardW - 0.5, h: labelH,
        fontFace: F.title || "맑은 고딕", fontSize: fitText(labelText, cardW - 0.5, labelH, 17, 12),
        bold: true, color: C.hero || "1A1A1A", align: "center", valign: "middle", margin: 0
      });
      cy += labelH + (descH ? 0.12 : 0);
    }
    if (descText) {
      slide.addText(descText, {
        x: x + 0.35, y: cy, w: cardW - 0.7, h: descH,
        fontFace: F.body || "맑은 고딕", fontSize: fitText(descText, cardW - 0.7, descH, 14, 10.5),
        color: C.gray || "5A6472", align: "center", valign: "top",
        lineSpacingMultiple: 1.2, margin: 0
      });
    }
  });
}

function addCompare(slide, leftCol, rightCol, themeInfo, rect) {
  const C = themeInfo.C || {}, F = themeInfo.F || {};
  const A = contentArea(rect);
  const gapX = 0.4;
  const cardW = (A.w - gapX) / 2;
  const cardH = A.h;

  const cols = [
    { data: leftCol || {}, x: A.x, tag: (leftCol && leftCol.tag) || "기존 방식 (As-Is)", color: C.gray || "5A6472", tone: "ghost" },
    { data: rightCol || {}, x: A.x + cardW + gapX, tag: (rightCol && rightCol.tag) || "개선 방식 (To-Be)", color: C.brand || "0038A3", tone: "light" }
  ];

  cols.forEach((colObj) => {
    const { data, x, tag, color, tone } = colObj;
    const bg = tone === "ghost" ? mix(C.body || "F4F6FA", C.white || "FFFFFF", 0.5) : (C.cardBg || "FFFFFF");

    slide.addShape('roundRect', {
      x, y: A.y, w: cardW, h: cardH, rectRadius: 0.12,
      fill: { color: bg }, line: NO_LINE, shadow: CARD_SHADOW
    });

    slide.addShape('roundRect', {
      x: x + 0.34, y: A.y + 0.34, w: 2.2, h: 0.42, rectRadius: 0.08,
      fill: { color }, line: NO_LINE
    });
    slide.addText(tag, {
      x: x + 0.34, y: A.y + 0.34, w: 2.2, h: 0.42,
      fontFace: F.title || "맑은 고딕", fontSize: 12, bold: true,
      color: "FFFFFF", align: "center", valign: "middle", margin: 0
    });

    const titleText = data.title || data.name || "";
    slide.addText(titleText, {
      x: x + 0.34, y: A.y + 0.92, w: cardW - 0.68, h: 0.6,
      fontFace: F.title || "맑은 고딕", fontSize: fitText(titleText, cardW - 0.68, 0.6, 22, 15),
      bold: true, color: C.hero || "1A1A1A", align: "left", valign: "middle", margin: 0
    });

    const items = (data.items || data.points || []);
    const bodyTop = A.y + 1.62;
    const bodyH = A.y + cardH - 0.34 - bodyTop;
    const arr = Array.isArray(items) ? items.map(String) : [String(items)];
    const size = fitText(arr.join(" ") + "  ".repeat(arr.length * 4), cardW - 0.9, bodyH, 15, 10.5);
    slide.addText(bulletRuns(arr, { paraSpaceAfter: Math.max(6, size * 0.8) }), {
      x: x + 0.34, y: bodyTop, w: cardW - 0.68, h: bodyH,
      fontFace: F.body || "맑은 고딕", fontSize: size, color: C.gray || "5A6472",
      align: "left", valign: "top", lineSpacingMultiple: 1.22, margin: 0
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
  const A = contentArea(rect);
  const x = A.x, y = A.y, w = A.w, h = A.h;

  if (!chartData || !chartData.labels || !chartData.series || !chartData.series.length) {
    addCards(slide, [{ title: title, body: "차트 데이터 준비 중" }], themeInfo, rect);
    return;
  }

  const kind = String(chartData.kind || "bar").toLowerCase();
  const labels = chartData.labels.map(String);
  // 브랜드 계열만 쓰면 파이 조각이 전부 비슷한 파랑이라 구분이 안 된다.
  // 첫 색은 브랜드로 두고, 나머지는 명도·색상이 확실히 갈리는 값으로 채운다.
  const palette = [C.brand || "0038A3", "F2A33C", C.teal || "2A9D99",
                   "8C6BD6", "E2574C", "9BB4D4", C.hero || "123979"];
  // 격자선은 기본 ON — 값을 읽을 수 있어야 차트 구실을 한다.
  const grid = chartData.grid === false ? { style: "none" } : { color: "DDE3EC", size: 0.5 };
  const axis = {
    showTitle: false, catAxisLabelColor: C.gray || "5A6472", valAxisLabelColor: C.gray || "5A6472",
    catAxisLabelFontSize: 12, valAxisLabelFontSize: 12,
    valGridLine: grid, catGridLine: { style: "none" },
  };

  // 원형·도넛은 정사각형에 가깝게 그려야 예쁘다. 가로로 넓은 영역에 그대로 넣으면
  // 가운데 작은 원 하나에 양옆이 텅 빈다 → 파이는 가운데 두고 옆에 범례 겸 설명을 놓는다.
  if (kind === "pie" || kind === "doughnut") {
    const s0 = chartData.series[0];
    const side = Math.min(h, w * 0.56);
    // 파이 + 범례를 한 덩어리로 보고 가운데 정렬한다. 범례를 화면 오른쪽 끝까지
    // 늘리면 파이와 범례 사이가 텅 비어 두 개의 섬처럼 보인다.
    const legendW = (w > side + 2.6) ? Math.min(4.0, w - side - 0.6) : 0;
    const groupW = side + (legendW ? legendW + 0.5 : 0);
    const cx = x + Math.max(0, (w - groupW) / 2);
    slide.addChart(kind === "doughnut" ? prs.ChartType.doughnut : prs.ChartType.pie,
      [{ name: s0.name || "비율", labels, values: s0.values }], {
        x: cx, y: y + (h - side) / 2, w: side, h: side, chartColors: palette,
        showLegend: false,
        showValue: true, showPercent: false,
        dataLabelColor: C.white || "FFFFFF", dataLabelFontSize: 14, dataLabelFormatCode: '0"%"',
        holeSize: kind === "doughnut" ? 55 : undefined,
        showTitle: false,
      });
    // 오른쪽 범례를 직접 그린다(기본 범례는 글자가 너무 작다)
    if (legendW) {
      const lx = cx + side + 0.5;
      const lw = legendW;
      {
        const total = (s0.values || []).reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        const rowH = Math.min(0.72, h / Math.max(labels.length, 3));
        const top = y + (h - rowH * labels.length) / 2;
        labels.forEach((lb, i) => {
          const yy = top + i * rowH;
          slide.addShape('roundRect', {
            x: lx, y: yy + rowH * 0.22, w: 0.24, h: 0.24, rectRadius: 0.05,
            fill: { color: palette[i % palette.length] }, line: NO_LINE
          });
          slide.addText(`${lb}`, {
            x: lx + 0.4, y: yy, w: lw - 1.5, h: rowH,
            fontFace: F.body || "맑은 고딕", fontSize: 14, color: C.hero || "1A1A1A",
            align: "left", valign: "middle", margin: 0
          });
          slide.addText(`${Math.round((Number(s0.values[i]) || 0) / total * 100)}%`, {
            x: lx + lw - 1.1, y: yy, w: 1.1, h: rowH,
            fontFace: F.title || "맑은 고딕", fontSize: 15, bold: true,
            color: palette[i % palette.length], align: "right", valign: "middle", margin: 0
          });
        });
      }
    }
    return;
  }

  // 막대 + 추세선(복합 차트)
  if (chartData.trend && kind !== "line") {
    const s0 = chartData.series[0];
    const trend = linearTrend(s0.values);
    slide.addChart([
      { type: prs.ChartType.bar,
        data: [{ name: s0.name || "값", labels, values: s0.values }],
        options: { chartColors: [palette[0]], barGapWidthPct: 60,
                   showValue: true, dataLabelColor: C.hero || "1A1A1A", dataLabelFontSize: 12,
                   dataLabelPosition: "outEnd" } },
      { type: prs.ChartType.line,
        data: [{ name: "추세", labels, values: trend }],
        options: { chartColors: [C.med || "1970AE"], lineSize: 2.5, lineDataSymbol: "none" } },
    ], Object.assign({
      x, y, w, h,
      showLegend: true, legendPos: "b", legendColor: C.gray || "5A6472", legendFontSize: 12,
    }, axis));
    return;
  }

  const type = kind === "line" ? prs.ChartType.line : prs.ChartType.bar;
  const data = chartData.series.map((s) => ({
    name: s.name || "지표", labels, values: s.values,
  }));
  slide.addChart(type, data, Object.assign({
    x, y, w, h, chartColors: palette, barGapWidthPct: 60,
    showLegend: data.length > 1, legendPos: "b", legendColor: C.gray || "5A6472", legendFontSize: 12,
    showValue: kind !== "line", dataLabelColor: C.hero || "1A1A1A", dataLabelFontSize: 12,
    dataLabelPosition: kind === "line" ? undefined : "outEnd",
  }, axis));
}

/** 지정 영역에 그라데이션 패널(미리 렌더한 PNG)을 깐다. 카드보다 먼저 호출할 것. */
function addGradientPanel(slide, imgPath, rect) {
  if (!imgPath) return;
  const r = rect || {};
  slide.addImage({
    path: imgPath,
    x: r.x != null ? r.x : 0, y: r.y != null ? r.y : HEADER_H,
    w: r.w != null ? r.w : W, h: r.h != null ? r.h : (H - HEADER_H),
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
      path: imgPath, x: 0, y: HEADER_H, w: W, h: H - HEADER_H,
      sizing: { type: "cover", w: W, h: H - HEADER_H },
      transparency: o.transparency != null ? o.transparency : 70,
    });
    return;
  }
  const x = o.x != null ? o.x : 7.0, y = o.y != null ? o.y : BODY_TOP;
  const w = o.w != null ? o.w : 5.6, h = o.h != null ? o.h : BODY_H;
  slide.addImage({
    path: imgPath, x, y, w, h, sizing: { type: "contain", w, h },
    transparency: o.transparency || 0,
  });
}

/**
 * 배경 장식(그라데이션 + 사진을 파이썬에서 미리 한 장으로 합성한 것).
 * 한 장이라 순서를 틀릴 수가 없다 — 예전엔 모델이 그라데이션을 먼저 깔고
 * 그 위에 전면 배경 사진을 덮어 그라데이션이 통째로 사라졌다.
 */
function addDecor(slide, imgPath) {
  if (!imgPath) return;
  slide.addImage({ path: imgPath, x: 0, y: HEADER_H, w: W, h: H - HEADER_H });
}

module.exports = { fitText, isLight, mix, bulletRuns, addCover, addHeader, addLead, addFooter,
                   addCard, addCards, addStats, addCompare, addChart,
                   addGradientPanel, addSlideImage, addDecor };

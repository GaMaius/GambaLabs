// 감바랩스 샘플 2장 (표지 + 적응형 스탯 콘텐츠) — pptxgenjs
// 실행: node build_samples.js   (프로젝트 루트에서, node_modules 참조)
const path = require("path");
const pptxgen = require("pptxgenjs");

const A = (p) => path.join(__dirname, "..", "assets", p);
const OUT = path.join(__dirname, "gambalabs_samples.pptx");

// 테마 팔레트
const C = {
  hero: "123979", brand: "0038A3", med: "1970AE", deepbox: "153C7E",
  body: "ECECEC", white: "FFFFFF", muted: "C9D4E8", gray: "5A6472",
};
const F = { title: "HY견고딕", body: "맑은 고딕" };

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE"; // 13.333 x 7.5

// ── Slide 1: 표지 ─────────────────────────────────────────────
const s1 = pptx.addSlide();
s1.background = { path: A("backgrounds/bg_cover.png") };
// 우측 아치 기둥 (위만 둥근 라이트그레이 기둥, 은은)
s1.addShape(pptx.ShapeType.roundRect, {
  x: 9.55, y: 3.05, w: 1.95, h: 5.0, rectRadius: 0.97,
  fill: { color: "EAEAEA", transparency: 88 }, line: { type: "none" },
});
// 화이트 로고 (우상단)
s1.addImage({ path: A("logo/logo_white.png"), x: 10.05, y: 0.5, w: 2.55, h: 2.55 / 8.16 });
// 대제목
s1.addText("온디바이스 AI 음성인식으로\n더 안전하고 편리한 세상을", {
  x: 0.9, y: 2.15, w: 8.3, h: 2.2, fontFace: F.title, fontSize: 40, bold: true,
  color: C.white, align: "left", valign: "top", lineSpacingMultiple: 1.05, margin: 0,
});
// 부제
s1.addText("WordSense · 초소형 KWS 음성인식 엔진 & 스마트 솔루션", {
  x: 0.92, y: 4.35, w: 8.2, h: 0.6, fontFace: F.body, fontSize: 20, color: C.muted, margin: 0,
});
// 발표자 블록 (좌하단)
s1.addText(
  [
    { text: "감바랩스 주식회사 (Gamba Labs Co., Ltd.)", options: { fontSize: 15, color: C.white, bold: true, breakLine: true } },
    { text: "Proprietary Technology, Ultimate Result", options: { fontSize: 13, color: C.muted } },
  ],
  { x: 0.92, y: 6.0, w: 8.0, h: 1.0, fontFace: F.body, align: "left", valign: "top", margin: 0, paraSpaceAfter: 4 }
);

// ── Slide 2: 적응형 스탯 콘텐츠 ──────────────────────────────
const s2 = pptx.addSlide();
s2.background = { color: C.body };
// 상단 헤더 밴드(그라데이션 이미지) — 세로 1/7
s2.addImage({ path: A("backgrounds/band.png"), x: 0, y: 0, w: 13.333, h: 1.05 });
// 밴드 좌상단 화이트 아이콘
s2.addImage({ path: A("logo/icon_white.png"), x: 0.4, y: 0.27, w: 0.72 * 1.53, h: 0.72 });
// 밴드 위 제목 (전폭 가운데 수직중앙)
s2.addText("WordSense 핵심 성능 & 이식성", {
  x: 0, y: 0, w: 13.333, h: 1.05, fontFace: F.title, fontSize: 28, bold: true,
  color: C.white, align: "center", valign: "middle", margin: 0,
});
// 리드 문장
s2.addText("어떤 제약 조건에서도 뛰어난 인식률과 구동성을 보장합니다.", {
  x: 0.8, y: 1.35, w: 11.7, h: 0.5, fontFace: F.body, fontSize: 16, color: C.gray, margin: 0,
});
// 4개 스탯 카드 (큰 숫자 + 라벨)
const stats = [
  { num: "90%+", label: "SNR −20dB 극한 소음 환경\n음성 인식률" },
  { num: "수백KB", label: "초경량 모델 크기\n초소형 MCU 직접 탑재" },
  { num: "0건", label: "100시간 연속 테스트\n오인식(False Accept) 0" },
  { num: "0ms", label: "온디바이스 Zero Latency\n인터넷 연결 불필요" },
];
const n = stats.length, gap = 0.35, left0 = 0.8, usable = 11.733;
const cw = (usable - gap * (n - 1)) / n, cy = 2.1, ch = 4.6;
stats.forEach((st, i) => {
  const x = left0 + i * (cw + gap);
  s2.addShape(pptx.ShapeType.roundRect, {
    x, y: cy, w: cw, h: ch, rectRadius: 0.1,
    fill: { color: C.white }, line: { type: "none" },
    shadow: { type: "outer", color: "8A96A8", opacity: 0.35, blur: 8, offset: 3, angle: 90 },
  });
  // 상단 컬러 도트(모티프) — 스트라이프 대신 아이콘성 원
  s2.addShape(pptx.ShapeType.ellipse, {
    x: x + cw / 2 - 0.18, y: cy + 0.5, w: 0.36, h: 0.36,
    fill: { color: C.med }, line: { type: "none" },
  });
  s2.addText(st.num, {
    x, y: cy + 1.15, w: cw, h: 1.3, fontFace: F.title, fontSize: 40, bold: true,
    color: C.hero, align: "center", valign: "middle", margin: 0,
  });
  s2.addText(st.label, {
    x: x + 0.15, y: cy + 2.55, w: cw - 0.3, h: 1.7, fontFace: F.body, fontSize: 14.5,
    color: C.gray, align: "center", valign: "top", lineSpacingMultiple: 1.1, margin: 0,
  });
});

pptx.writeFile({ fileName: OUT }).then((f) => console.log("wrote", f));

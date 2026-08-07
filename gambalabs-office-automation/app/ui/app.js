// 감바랩스 오피스 AI — 프런트 로직 (v2)
let PPT = "", XLSX = "", EXP = "", lastUpdates = null;

function api() {
  if (!window.pywebview || !window.pywebview.api) throw new Error("백엔드 준비 중… 잠시 후 다시 시도하세요.");
  return window.pywebview.api;
}
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const bs = (s) => esc(s).replace(/\\/g, "\\\\");
function show(el, html) { el.classList.remove("hidden"); if (html !== undefined) el.innerHTML = html; }
function spin(el, msg) { show(el, `<span class="spin"></span>${msg || "처리 중…"}`); }
function setPath(id, p) { if (p) { $(id).textContent = p; $(id).classList.remove("empty"); } }

/* 테마 */
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  $("brandLogo").src = t === "light" ? "assets/logo_color.png" : "assets/logo_white.png";
  $("themeBtn").textContent = t === "light" ? "🌙 다크로" : "☀️ 라이트로";
  localStorage.setItem("theme", t);
}
$("themeBtn").onclick = () => applyTheme(document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light");
applyTheme(localStorage.getItem("theme") || "dark");

/* 탭 */
document.querySelectorAll(".nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll(".nav button").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); $("tab-" + b.dataset.tab).classList.add("active");
  };
});
/* ── 모드별 인라인 설명(무엇을·어떻게) ── */
const PPT_MODEHELP = {
  theme: ["var(--purple)", "✱", "테마 개발", "디자인 설정(색·폰트·배경)으로 재사용 가능한 나만의 브랜드 테마를 만들어 저장합니다. 만든 테마는 🎨 목록에서 골라 다른 발표에도 씁니다.", ["① 디자인 설정 입력", "② 테마 이름", "③ 만들기·저장"]],
  import: ["var(--purple)", "◈", "PPT 디자인", "내용과 설명을 적어둔 러프 PPT(pptx)를 넣으면, AI가 위치·설명을 해석해 브랜드 디자인 덱으로 만듭니다.", ["① PPTX 선택", "② 해석 미리보기", "③ 생성"]],
  auto: ["var(--purple)", "▤", "자동 생성 PPT", "문서(md·txt) 하나를 통째로 넣으면 AI가 슬라이드로 나눠 브랜드 덱을 자동 생성합니다.", ["① 문서 선택", "② 구성 미리보기", "③ 생성"]],
  prompt: ["var(--purple)", "✎", "프롬프트 생성", "디자인 설정과 주제를 묶어 GPT·Claude·Gemini 등 아무 LLM에 붙여넣을 프롬프트를 만들어 복사합니다.", ["① 주제 입력", "② 옵션", "③ 생성·복사"]],
};
const DATA_MODEHELP = {
  "exp-code": ["var(--teal)", "⚡", "실험 기록 코드 삽입", "수동 입력 없이 파이썬이나 C/C++ 코드 레벨에서 바로 트래커에 실험 결과를 기록합니다.", ["① 언어 선택", "② 코드 복사", "③ 스크립트 적용"]],
  "exp-analyze": ["var(--teal)", "🔎", "엑셀 분석/차트", "기록된 엑셀 데이터를 바탕으로 AI가 요약 분석하고 차트를 생성합니다.", ["① 트래커 선택", "② 질문 입력", "③ 분석 및 차트"]],
  "receipt": ["var(--teal)", "🧾", "자동 영수증 작성", "자연어 결제 내역을 영수증 표준 엑셀 폼에 깔끔하게 채워줍니다.", ["① 내역 입력", "② 양식 선택", "③ 영수증 생성"]],
};
function mhRender(el, spec) {
  if (!el || !spec) return;
  const [color, ic, t, d, steps] = spec;
  el.style.borderLeftColor = color;
  el.innerHTML = `<span class="modehelp-ic" style="background:${color}">${ic}</span><div><div class="modehelp-t">${esc(t)}</div><div class="modehelp-d">${esc(d)}</div><div class="modehelp-s">${steps.map((s) => `<span>${esc(s)}</span>`).join("")}</div></div>`;
}

/* 모드 토글 */
function pptMode(m) {
  document.querySelectorAll('#tab-ppt .seg button').forEach((x) => x.classList.toggle("on", x.dataset.m === m));
  ["theme", "import", "auto", "prompt"].forEach((k) => $("ppt-" + k).classList.toggle("hidden", k !== m));
  $("ppt-float").classList.add("hidden");  // 플로팅 편집기: 현재 숨김(코드 보존)
  $("designForm").classList.remove("hidden");  // 디자인 설정: 모드 공통 노출
  mhRender($("ppt-modehelp"), PPT_MODEHELP[m]);
}
function dataMode(m) {
  document.querySelectorAll('#tab-data .seg button').forEach((x) => x.classList.toggle("on", x.dataset.m === m));
  ["exp-code", "exp-analyze", "receipt"].forEach((k) => {
    const el = $("data-" + k);
    if (el) el.classList.toggle("hidden", k !== m);
  });
  mhRender($("data-modehelp"), DATA_MODEHELP[m]);
}
/* 클립보드 복사(공용) */
function copyText(txt) {
  let ok = false;
  const ta = document.createElement("textarea");
  ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.focus(); ta.select();
  try { ok = document.execCommand("copy"); } catch (e) {}
  try { if (navigator.clipboard) { navigator.clipboard.writeText(txt); ok = true; } } catch (e) {}
  document.body.removeChild(ta); return ok;
}
/* 실험 로거 스니펫 */
async function setSnippetLang(lang) {
  const el = $("expSnippet"); if (!el) return;
  let dir = "";
  try { dir = await api().project_dir(); } catch (e) {}
  document.querySelectorAll('#data-exp-code .seg button').forEach(b => b.classList.toggle("on", b.dataset.lang === lang));
  
  if (lang === "python") {
    el.textContent =
      `import os, sys\n` +
      `ROOT_DIR = r"${dir || '...\\\\gambalabs-office-automation'}"\n` +
      `if ROOT_DIR not in sys.path: sys.path.insert(0, ROOT_DIR)\n\n` +
      `from gamba_log import enable_print_logger\n\n` +
      `# 🌟 최상단에 선언해 두면 이후 모든 print() 출력이 엑셀로 자동 파싱/기록됩니다!\n` +
      `TRACKER_PATH = os.path.join(ROOT_DIR, "output", "excel", "tracker", "log.xlsx")\n` +
      `enable_print_logger(tracker=TRACKER_PATH, sheet="실험기록")\n\n` +
      `# -----------------------------------------------------------------\n` +
      `# (기존 코드 수정 없이) 아래처럼 print()만 찍으시면 엑셀에 자동 저장됩니다!\n` +
      `print("Epoch 1 - accuracy: 91.2% snr: -20dB loss: 0.245 (기본 모델)")`;
    el.className = "codebox hljs language-python";
  } else if (lang === "c") {
    const escDir = (dir || "...\\\\gambalabs-office-automation").replace(/\\/g, "\\\\");
    el.textContent =
      `#include "gamba_log.h"\n\n` +
      `// 빌드 시 gamba_log.c 포함 필요\n` +
      `gamba_log_set_tracker("${escDir}\\\\output\\\\excel\\\\tracker\\\\log.xlsx");\n` +
      `gamba_log_add_float("정확도(%)", 92.3f);\n` +
      `gamba_log_add_int("오인식(건)", 1);\n` +
      `gamba_log_add_string("비고", "튜닝");\n` +
      `gamba_log_commit();`;
    el.className = "codebox hljs language-c";
  }
  if (window.hljs) hljs.highlightElement(el);
}
function copySnippet() { const el = $("expSnippet"); if (el) copyText(el.textContent); }

/* 상태 */
const MODEL_LABEL = (m) => ({ "qwen2.5:7b-instruct": "Qwen2.5 7B · 정확·느림", "qwen2.5:3b-instruct": "Qwen2.5 3B · 빠름", "gpt-4o": "GPT-4o (온라인)" }[m] || m);
async function initStatus() {
  try {
    api().llm_status().then((s) => ($("llmStatus").textContent = s));
    api().img_status().then((s) => ($("imgStatus").textContent = s));
    const r = await api().get_llm();
    const sel = $("modelSel"); sel.innerHTML = "";
    r.options.forEach((m) => { const o = document.createElement("option"); o.value = m; o.textContent = MODEL_LABEL(m); if (m === r.current) o.selected = true; sel.appendChild(o); });
    refreshThemes(await api().get_themes());
    setSnippetLang('python');
  } catch (e) {}
}
let THEME_OPTS = [];
function refreshThemes(th) {
  THEME_OPTS = th.options || [];
  const ts = $("themeSel"); ts.innerHTML = "";
  THEME_OPTS.forEach((t) => { const o = document.createElement("option"); o.value = t.id; o.textContent = t.label + (t.custom ? " (커스텀)" : ""); o.title = t.desc || ""; if (t.id === th.current) o.selected = true; ts.appendChild(o); });
  updateThemeDel();
  refreshSeedThemes();
}
function updateThemeDel() {
  const cur = THEME_OPTS.find((t) => t.id === $("themeSel").value);
  $("themeDelBtn").classList.toggle("hidden", !(cur && cur.custom));
}
async function onModelChange() {
  try {
    const r = await api().set_model($("modelSel").value);
    // 폐기된 모델을 골랐으면 백엔드가 거부하고 목록을 갱신해 준다 → 드롭다운을 다시 그린다
    if (r && r.options) {
      const sel = $("modelSel"); sel.innerHTML = "";
      r.options.forEach((m) => {
        const o = document.createElement("option");
        o.value = m; o.textContent = MODEL_LABEL(m);
        if (m === r.current) o.selected = true;
        sel.appendChild(o);
      });
    }
    if (r && r.error) alert(r.error);
  } catch (e) {}
  resetChat();  // 모델 바뀌면 백엔드 대화가 초기화됨 → 프런트도 리셋
}
async function onThemeChange() { try { await api().set_theme($("themeSel").value); } catch (e) {} updateThemeDel(); }

/* ── 테마 추가/제작 모달 ── */
function openThemeModal() { $("themeModal").classList.remove("hidden"); tmPreview(); }
function closeThemeModal() { $("themeModal").classList.add("hidden"); }
function themeTab(which) {
  document.querySelectorAll("#themeModal .modal-seg button").forEach((b) => b.classList.toggle("on", b.dataset.tm === which));
  $("tm-build").classList.toggle("hidden", which !== "build");
  $("tm-upload").classList.toggle("hidden", which !== "upload");
}
function tmPreview() {
  const bg = $("tmBg").value, ac = $("tmAccent").value, ink = $("tmInk").value, band = $("tmBand").checked;
  $("tmPrev").innerHTML =
    `<div class="tmslide" style="background:${bg};color:${ink}">
       <div class="tmband" style="background:${band ? ac : bg};color:${band ? "#fff" : ink};${band ? "" : "border-bottom:1px solid " + ink + "33"}">제목 밴드</div>
       <div class="tmbody"><div class="tmbar" style="background:${ac}"></div><b>슬라이드 제목</b><br><span style="opacity:.7">본문 텍스트 미리보기 · <span style="color:${ac};font-weight:700">강조</span></span></div>
     </div>`;
}
async function themeUpload() {
  const box = $("tmUpResult"); spin(box, "파일 확인 중…"); show(box);
  const r = await api().add_theme_upload($("tmUpName").value.trim());
  if (r.cancelled) return box.classList.add("hidden");
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  refreshThemes({ options: r.options, current: r.current });
  show(box, `<span class="ok">✅ '${esc(r.added.label)}' 추가·적용됨</span>`);
  setTimeout(closeThemeModal, 900);
}
async function themeBuild() {
  const name = $("tmName").value.trim(); if (!name) return alert("테마 이름을 입력하세요.");
  const box = $("tmBuildResult"); spin(box, "생성 중…"); show(box);
  const hx = (id) => $(id).value.replace("#", "");
  const r = await api().add_theme_build(name, hx("tmBg"), hx("tmAccent"), hx("tmInk"), $("tmBand").checked);
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  refreshThemes({ options: r.options, current: r.current });
  show(box, `<span class="ok">✅ '${esc(r.added.label)}' 생성·적용됨</span>`);
  setTimeout(closeThemeModal, 900);
}
async function deleteCurrentTheme() {
  const id = $("themeSel").value; const cur = THEME_OPTS.find((t) => t.id === id);
  if (!cur || !cur.custom) return;
  if (!confirm(`'${cur.label}' 테마를 삭제할까요?`)) return;
  const r = await api().delete_theme(id);
  refreshThemes({ options: r.options, current: r.current });
}

/* ── skill 기반 디자인 설정 폼 ── */
let REFS = [];        // 참고자료 경로 목록(여러 개)
let PALETTE = null;   // 최근 추출한 팔레트 {colors,accent,bg,ink}
function qPick(group, btn) {
  const box = $(group);
  box.querySelectorAll(".qchip").forEach((c) => c.classList.remove("on"));
  btn.classList.add("on");
  box.dataset.val = btn.dataset.v;
}
/* 참고자료: 여러 개 추가/삭제 */
async function addRef() {
  const p = await api().pick_file("doc");
  if (p && !REFS.includes(p)) { REFS.push(p); renderRefs(); markFilled(); }
}
function removeRef(i) { REFS.splice(i, 1); renderRefs(); markFilled(); }
function renderRefs() {
  const box = $("refList");
  if (!REFS.length) { box.innerHTML = `<div class="qnote">추가된 참고자료 없음</div>`; return; }
  box.innerHTML = REFS.map((p, i) => {
    const name = p.split(/[\\/]/).pop();
    return `<span class="refchip" title="${esc(p)}">📄 ${esc(name)}<button onclick="removeRef(${i})">✕</button></span>`;
  }).join("");
}
/* 컬러 스와치 미리보기 갱신 */
function refreshSwatches() {
  $("swAccent").style.background = $("qAccent").value;
  $("swInk").style.background = $("qInk").value;
}
/* 무드 프리셋 — 배경·강조·글자를 한 세트로. 색 3개를 따로 고르게 하면 대비가 깨진 조합이 나온다. */
const MOODS = {
  navy:  { bg: "#f4f6fa", accent: "#0038a3", ink: "#123979" },
  clean: { bg: "#ffffff", accent: "#2456c7", ink: "#222222" },
  dark:  { bg: "#141a2b", accent: "#4e86c6", ink: "#f2f5fb" },
  warm:  { bg: "#faf7f2", accent: "#b4541f", ink: "#2e2621" },
};
function applyMood(btn) {
  qPick("qMood", btn);
  const m = MOODS[btn.dataset.v];
  if (m) { $("qBgColor").value = m.bg; $("qAccent").value = m.accent; $("qInk").value = m.ink; }
  markFilled();
}
/* 색을 직접 만지면 무드 선택은 해제한다(어떤 프리셋도 아닌 상태) */
function onColorEdit() { setChip("qMood", ""); markFilled(); }
function toggleFontInput() {
  $("qFontCustom").classList.toggle("hidden", $("qFont").dataset.val !== "__custom");
}

/* 채운 항목 배지(●) 표시 — 기본값과 다르면 채운 것으로 본다 */
function markFilled() {
  refreshSwatches();
  const set = (id, on) => { const e = $(id); if (e) e.textContent = on ? "●" : ""; };
  const v = (id) => $(id).dataset.val;
  set("b_purpose", $("qPurpose").value.trim());
  set("b_shape", v("qUsage") !== "talk" || v("qLength") !== "auto");
  set("b_color", v("qMood") !== "navy" || $("qSeedTheme").value);
  set("b_visual", v("qPhotos") !== "auto" || v("qBg") !== "solid"
    || v("qRatio") !== "16:9" || v("qFont") !== "맑은 고딕");
  set("b_extra", $("qDirection").value.trim() || REFS.length);
}
/* 저장 테마 → 폼 색 시드 */
async function seedFromTheme() {
  const id = $("qSeedTheme").value; if (!id) return;
  try {
    const c = await api().theme_colors(id);
    if (c && c.accent) $("qAccent").value = "#" + c.accent;
    if (c && c.ink) $("qInk").value = "#" + c.ink;
    if (c && c.bg) $("qBgColor").value = "#" + c.bg;
    setChip("qMood", "");
    markFilled();
  } catch (e) {}
}
function setChip(group, v) {
  const box = $(group); box.dataset.val = v;
  box.querySelectorAll(".qchip").forEach((c) => c.classList.toggle("on", c.dataset.v === v));
}
/* 참고 이미지에서 색 추출 */
async function pickPalette() {
  $("palFile").textContent = "추출 중…";
  try {
    const r = await api().extract_palette();
    if (r.cancelled) { $("palFile").textContent = ""; return; }
    if (r.error) { $("palFile").textContent = r.error; return; }
    PALETTE = r; $("palFile").textContent = r.file ? `“${r.file}” 에서` : "";
    show($("palRow"), r.colors.map((h) => `<button class="palsw" style="background:#${h}" title="#${h} → 강조색" onclick="useSwatch('${h}')"></button>`).join(""));
    $("palCta").classList.remove("hidden");
  } catch (e) { $("palFile").textContent = String(e.message || e); }
}
function useSwatch(h) { $("qAccent").value = "#" + h; onColorEdit(); }
function applyAutoPalette() {
  if (!PALETTE) return;
  if (PALETTE.accent) $("qAccent").value = "#" + PALETTE.accent;
  if (PALETTE.ink) $("qInk").value = "#" + PALETTE.ink;
  if (PALETTE.bg) $("qBgColor").value = "#" + PALETTE.bg;
  onColorEdit();
}
function readDesignForm() {
  const v = (id) => $(id).dataset.val;
  const font = v("qFont") === "__custom" ? ($("qFontCustom").value.trim() || "맑은 고딕") : v("qFont");
  return {
    purpose: $("qPurpose").value.trim(),
    direction: $("qDirection").value.trim(),
    usage: v("qUsage"), length: v("qLength"), photos: v("qPhotos"),
    ratio: v("qRatio"),
    bg: $("qBgColor").value.replace("#", ""),
    accent: $("qAccent").value.replace("#", ""),
    ink: $("qInk").value.replace("#", ""),
    band_fill: true, gradient: v("qBg") === "gradient",
    font, refs: REFS.slice(),
  };
}
async function applyFormTheme() {
  const f = readDesignForm();
  try { await api().set_form_theme(f.bg, f.accent, f.ink, f.band_fill, f.font, f.gradient, f.ratio); } catch (e) {}
  try { await api().set_design_brief(f.purpose, f.direction, f.refs, f.usage, f.length, f.photos); } catch (e) {}
  return f;
}
async function makeThemeFromForm() {
  const name = $("themeName").value.trim(); if (!name) return alert("테마 이름을 입력하세요.");
  const f = readDesignForm(); const box = $("themeMakeResult"); spin(box, "테마 생성 중…"); show(box);
  try {
    const r = await api().add_theme_build(name, f.bg, f.accent, f.ink, f.band_fill, f.font);
    if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
    refreshThemes({ options: r.options, current: r.current });
    refreshSeedThemes();
    show(box, `<span class="ok">✅ '${esc(r.added.label)}' 테마 생성·적용됨</span> — 🎨 목록에서 선택되고, PPT 디자인/자동 생성에도 쓰입니다.`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}
/* 기반 테마 셀렉트 채우기(폼 내부) */
function refreshSeedThemes() {
  const sel = $("qSeedTheme"); if (!sel) return;
  const keep = sel.value;
  sel.innerHTML = `<option value="">직접 지정</option>`;
  (THEME_OPTS || []).forEach((t) => { const o = document.createElement("option"); o.value = t.id; o.textContent = t.label + (t.custom ? " (커스텀)" : ""); sel.appendChild(o); });
  sel.value = keep;
}

/* ── 프롬프트 생성(범용 LLM에 붙여넣기) ── */
async function genPrompt() {
  const f = readDesignForm();
  const tsel = $("themeSel");
  const themeLabel = (tsel && tsel.selectedOptions[0]) ? tsel.selectedOptions[0].textContent : "";
  const payload = {
    topic: $("promptTopic").value.trim(),
    purpose: f.purpose, direction: f.direction, ratio: f.ratio,
    bg_tone: $("qBgTone").dataset.val, accent: f.accent, ink: f.ink,
    gradient: f.gradient, font: f.font, refs: f.refs,
    theme_label: themeLabel, output: $("promptOut").value, strict: $("promptStrict").value === "1",
  };
  const box = $("promptResult"); spin(box, "프롬프트 조립 중…"); show(box);
  try {
    const r = await api().gen_ppt_prompt(payload);
    if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
    const ta = $("promptOutput"); ta.value = r.prompt; ta.classList.remove("hidden");
    $("promptCopyBtn").classList.remove("hidden");
    show(box, `<span class="ok">✅ 생성됨</span> — 복사해서 GPT · Claude · Gemini 등에 붙여넣으세요. (${r.prompt.length}자)`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}
function copyPrompt() {
  const ta = $("promptOutput"); if (!ta.value) return;
  ta.focus(); ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) {}
  try { if (navigator.clipboard) { navigator.clipboard.writeText(ta.value); ok = true; } } catch (e) {}
  const b = $("promptCopyBtn"); const t = b.textContent;
  b.textContent = ok ? "✓ 복사됨" : "복사 실패"; setTimeout(() => (b.textContent = t), 1200);
}

/* ── 플로팅 편집기(현재 UI 숨김, 코드 보존) ── */
async function openFloat() {
  const box = $("floatResult"); if (!box) return; show(box, `<span class="spin"></span>여는 중…`);
  try {
    const r = await api().open_float();
    show(box, r && r.error ? `<span class="err">${esc(r.error)}</span>` : `<span class="ok">✅ 플로팅 창을 열었어요.</span> 화면 위에 항상 떠 있어요(닫기 전까지).`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}

/* ── API 키 설정 ──
   키는 .env 파일에만 저장한다. 이미 저장된 키는 마스킹해서 placeholder로만 보여주고,
   입력란은 항상 비워 둔다 → 빈 칸으로 저장하면 기존 값이 유지된다(실수로 날리는 것 방지). */
const API_GROUPS = { groq: "apiGroq", openai: "apiOpenai", ollama: "apiOllama" };

async function openApiModal() {
  $("apiModal").classList.remove("hidden");
  $("apiResult").classList.add("hidden");
  ["apiGroqKey", "apiGroqKey2", "apiOpenaiKey", "apiPexels"].forEach((id) => ($(id).value = ""));
  try {
    const s = await api().settings_get();
    $("apiEnvPath").textContent = s._path || ".env";
    $("apiProvider").value = s._provider || "groq";
    const ph = (id, f) => {
      const v = s[f];
      $(id).placeholder = v && v.set ? `${v.display}  (저장됨 · 그대로 두면 유지)` : $(id).placeholder;
    };
    ph("apiGroqKey", "GROQ_API_KEY"); ph("apiGroqKey2", "GROQ_API_KEY2");
    ph("apiOpenaiKey", "OPENAI_API_KEY"); ph("apiPexels", "PEXELS_API_KEY");
    $("apiOpenaiModel").value = (s.OPENAI_MODEL && s.OPENAI_MODEL.display) || "";
    $("apiOllamaModel").value = (s.OPENAI_MODEL && s.OPENAI_MODEL.display) || "";
    $("apiBaseUrl").value = (s.OPENAI_BASE_URL && s.OPENAI_BASE_URL.display) || "";
    apiSwitchGroup();
  } catch (e) { show($("apiResult"), `<span class="err">${esc(e.message || e)}</span>`); }
}
function closeApiModal() { $("apiModal").classList.add("hidden"); }

function apiSwitchGroup() {
  const p = $("apiProvider").value;
  Object.entries(API_GROUPS).forEach(([k, id]) => $(id).classList.toggle("hidden", k !== p));
}

async function apiSave() {
  const p = $("apiProvider").value;
  const vals = { LLM_PROVIDER: p, PEXELS_API_KEY: $("apiPexels").value };
  if (p === "groq") {
    vals.GROQ_API_KEY = $("apiGroqKey").value;
    vals.GROQ_API_KEY2 = $("apiGroqKey2").value;
  } else if (p === "openai") {
    vals.OPENAI_API_KEY = $("apiOpenaiKey").value;
    vals.OPENAI_MODEL = $("apiOpenaiModel").value;
    vals.OPENAI_BASE_URL = "-";                 // 공식 엔드포인트로 되돌린다
  } else {
    vals.OPENAI_BASE_URL = $("apiBaseUrl").value || "http://localhost:11434/v1";
    vals.OPENAI_MODEL = $("apiOllamaModel").value;
  }
  const box = $("apiResult");
  spin(box, "저장 중…");
  try {
    const r = await api().settings_save(vals);
    if (r.error) { show(box, `<span class="err">${esc(r.error)}</span>`); return; }
    show(box, `<span class="ok">✅ 저장했어요.</span> 바로 적용됩니다 · <span class="mono">${esc(r.path)}</span>`);
    ["apiGroqKey", "apiGroqKey2", "apiOpenaiKey", "apiPexels"].forEach((id) => ($(id).value = ""));
    initStatus();
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}

async function apiTest() {
  const box = $("apiResult");
  spin(box, "연결 확인 중…");
  try {
    const r = await api().settings_test();
    show(box, r.ok
      ? `<span class="ok">✅ 연결됨</span> — 모델 <span class="mono">${esc(r.model)}</span>`
      : `<span class="err">연결 실패: ${esc(r.error)}</span>`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}

/* ── 사용 가이드(온보딩) ── */
function openHelp() { $("helpModal").classList.remove("hidden"); }
function closeHelp() { $("helpModal").classList.add("hidden"); }
function helpDontShow() { localStorage.setItem("helpHide", $("helpDontShow").checked ? "1" : "0"); }
// 온보딩 모달은 자동으로 띄우지 않는다 — 각 탭·모드에 인라인 설명이 항상 보이므로.
// 전체 개요가 필요하면 사이드바 ❓로 연다.
window.addEventListener("pywebviewready", initStatus);
renderRefs(); markFilled();   // 폼 초기 상태(참고자료 목록·배지·스와치)
mhRender($("ppt-modehelp"), PPT_MODEHELP.theme);   // 초기 모드 설명
mhRender($("data-modehelp"), DATA_MODEHELP["exp-code"]);
setSnippetLang('python');   // 경로 미확정 시 폴백 표시(이후 initStatus에서 실제 경로로 갱신)

/* ── PPT 풀 자동 ── */
async function pickPpt() { const p = await api().pick_file("doc"); if (p) { PPT = p; setPath("pptPath", p); } }
async function previewPpt() {
  if (!PPT) return alert("문서를 선택하세요.");
  const llm = true;   // LLM 항상 사용
  spin($("pptOutline"), llm ? "AI가 문서를 구조화 중… (로컬 모델이면 수십 초~수 분)" : "분석 중…"); show($("pptOutline"));
  const r = await api().ppt_preview(PPT, llm);
  if (r.error) return show($("pptOutline"), `<span class="err">${esc(r.error)}</span>`);
  const li = r.outline.map((s, i) => `<li><b>${i + 1}</b> ${esc(s.title)} <span class="t">${esc(s.type)}</span></li>`).join("");
  show($("pptOutline"), `<div class="pill">${esc(r.engine || "")} · 표지 + ${r.outline.length} 본문 + 마무리</div><div style="margin-top:6px"><b>${esc(r.title)}</b></div><ul class="outline-list">${li}</ul>`);
}
async function makePpt() {
  if (!PPT) return alert("문서를 선택하세요.");
  const llm = true;   // LLM 항상 사용
  spin($("pptResult"), llm ? "AI 구조화 후 생성 중…" : "생성 중…"); show($("pptResult")); $("pptGoBtn").disabled = true;
  await applyFormTheme();   // 디자인 설정을 테마로 적용
  const r = await api().ppt_make_full(PPT, llm); $("pptGoBtn").disabled = false;
  if (r.error) return show($("pptResult"), `<span class="err">${esc(r.error)}</span>`);
  show($("pptResult"), `<span class="ok">✅ 생성 완료</span> <span class="t">${esc(r.engine || "")}</span> <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
}

/* ── PPT 디자인 보조(스펙) ── */
const SPEC_SAMPLE = `@title: WordSense 성능 리포트
@subtitle: 실험 결과 요약

# 핵심 성능 지표
> 어떤 제약 조건에서도 높은 인식률
- SNR -20dB에서 90%+ 인식률 [강조]
- 수백KB 초경량 모델
- 100시간 오인식 0건
[차트: 막대, 데이터=88.5,90.1,91.4,92.3]

# 배포 방식 비교
- A안: 온디바이스 (권장) [강조]
- B안: 클라우드 의존
[차트: 원형, 데이터=온디바이스:55, 클라우드:30, 하이브리드:15]
[이미지: AI 음성인식 느낌, 배경, 투명15]`;
function fillSpecSample() { $("specText").value = SPEC_SAMPLE; }
async function previewSpec() {
  spin($("specOutline")); show($("specOutline"));
  const r = await api().ppt_spec_preview($("specText").value);
  if (r.error) return show($("specOutline"), `<span class="err">${esc(r.error)}</span>`);
  const li = r.outline.map((s, i) => `<li><b>${i + 1}</b> ${esc(s.title)} ${s.extras ? `<span class="t">${esc(s.extras)}</span>` : ""}</li>`).join("");
  show($("specOutline"), `<div class="pill">${r.outline.length} 슬라이드</div><ul class="outline-list">${li}</ul>`);
}
async function makeSpec() {
  spin($("specResult")); show($("specResult")); $("specGoBtn").disabled = true;
  const r = await api().ppt_make_spec($("specText").value); $("specGoBtn").disabled = false;
  if (r.error) return show($("specResult"), `<span class="err">${esc(r.error)}</span>`);
  const note = r.images ? "" : " (이미지는 플레이스홀더 — 스톡 키 설정 시 실제 삽입)";
  show($("specResult"), `<span class="ok">✅ 생성 완료${note}</span> <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
}

/* ── PPT AI 대화형 (GPT/Claude식 단일 채팅면) ── */
let chatStarted = false;
function addMsg(who, html) {
  const empty = $("chatEmpty"); if (empty) empty.remove();
  const wrap = document.createElement("div");
  wrap.className = "msg " + who;
  wrap.innerHTML = `<div class="ava">${who === "user" ? "나" : "G"}</div><div class="bubble">${html}</div>`;
  $("chatLog").appendChild(wrap); $("chatLog").scrollTop = 1e9;
  return wrap;
}
function thinking() { return addMsg("agent", `<span class="spin"></span>생각 중…`); }
function autoGrow(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 150) + "px"; }
function chatKey(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); chatSend(); } }
function chatFill(t) { const el = $("chatInput"); el.value = t; autoGrow(el); el.focus(); }
function resetChat() {
  chatStarted = false;
  const log = $("chatLog"); if (!log) return;
  log.innerHTML = `<div id="chatEmpty" class="chatempty"><div class="chatempty-ico">◆</div><h2>무엇을 만들까요?</h2><p>주제·자료를 적어 보내면, 에이전트가 필요한 걸 <b>질문하며</b> 함께 만들어요.</p></div>`;
}
async function chatSend() {
  const el = $("chatInput"); const v = el.value.trim(); if (!v) return;
  el.value = ""; el.style.height = "auto";
  addMsg("user", esc(v)); const t = thinking();
  const first = !chatStarted; chatStarted = true;
  try {
    const r = first ? await api().chat_start(v) : await api().chat_reply(v);
    t.remove(); renderAgent(r);
    if (r && (r.error || r.type === "error")) chatStarted = false;  // 시작 실패 시 재시도 허용
  } catch (e) { t.remove(); chatStarted = false; addMsg("agent", `<span class="err">${esc(e.message || e)}</span>`); }
  $("chatInput").focus();
}
function opt(v) { addMsg("user", esc(v)); const t = thinking(); api().chat_reply(v).then((r) => { t.remove(); renderAgent(r); }).catch((e) => { t.remove(); addMsg("agent", `<span class="err">${esc(e.message || e)}</span>`); }); }
function renderAgent(r) {
  if (!r || r.error || r.type === "error") return addMsg("agent", `<span class="err">${esc((r && r.error) || "오류")}</span>`);
  if (r.type === "question") {
    const opts = (r.options && r.options.length) ? `<div class="opts">${r.options.map((o) => `<button class="btn btn-util opt" onclick="opt('${bs(o)}')">${esc(o)}</button>`).join("")}</div>` : "";
    addMsg("agent", `${esc(r.text)}${opts}`);
    return;
  }
  const li = (r.outline || []).map((t, i) => `${i + 1}. ${esc(t)}`).join("<br>");
  const rerr = r.render_error ? `<div class="err" style="margin-top:6px">렌더 오류: ${esc(r.render_error)}</div>` : "";
  const open = r.out ? `<div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>` : "";
  const cta = r.type === "sample" ? `<div class="opts"><button class="btn btn-primary opt" onclick="opt('이대로 전체 만들어줘')">이대로 진행</button><button class="btn btn-util opt" onclick="$('chatInput').focus()">수정 요청</button></div>` : "";
  addMsg("agent", `<b>${r.type === "final" ? "✅ 완성했어요" : "🔎 샘플 2장이에요"}</b><br>${esc(r.message || "")}<div style="margin:8px 0;font-size:13px;color:var(--ink-muted)">${li}</div>${rerr}${open}${cta}`);
}

/* ── PPT 입력(파워포인트 설명 파악) ── */
let IMPORT = "";
async function pickImport() { const p = await api().pick_file("pptx"); if (p) { IMPORT = p; setPath("importPath", p); } }
async function previewImport() {
  if (!IMPORT) return alert("PPTX를 선택하세요.");
  const llm = true;   // LLM 항상 사용
  spin($("importOutline"), llm ? "AI가 해석 중… (로컬 모델이면 수십 초~수 분)" : "해석 중…"); show($("importOutline"));
  const r = await api().ppt_import_preview(IMPORT, llm);
  if (r.error) return show($("importOutline"), `<span class="err">${esc(r.error)}</span>`);
  const sub = r.subtitle ? ` · <span style="color:var(--ink-muted)">${esc(r.subtitle)}</span>` : "";
  const li = r.outline.map((s, i) => `<li><b>${i + 1}</b> ${esc(s.title)} ${s.extras ? `<span class="t">${esc(s.extras)}</span>` : ""}</li>`).join("");
  show($("importOutline"), `<div class="pill">${esc(r.engine || "")} · ${r.outline.length} 슬라이드</div><div style="margin-top:6px"><b>${esc(r.title || "")}</b>${sub}</div><ul class="outline-list">${li}</ul>`);
}
async function makeImport() {
  if (!IMPORT) return alert("PPTX를 선택하세요.");
  const llm = true;   // LLM 항상 사용
  spin($("importResult"), llm ? "AI 해석 후 생성 중…" : "생성 중…"); show($("importResult")); $("importGoBtn").disabled = true;
  await applyFormTheme();   // 디자인 설정을 테마로 적용
  const r = await api().ppt_import_make(IMPORT, llm); $("importGoBtn").disabled = false;
  if (r.error) return show($("importResult"), `<span class="err">${esc(r.error)}</span>`);
  show($("importResult"), `<span class="ok">✅ ${r.count}장 생성</span> <span class="t">${esc(r.engine || "")}</span> <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
}

/* ── 데이터: 실험 기록 ── */
async function pickExp() { const p = await api().pick_file("xlsx"); if (p) { EXP = p; setPath("expPath", p); } }
async function newTracker() {
  const headers = $("tkHeaders").value.trim(); const box = $("tkResult");
  if (!headers) return alert("컬럼(헤더)을 쉼표로 구분해 입력하세요.");
  spin(box, "트래커 생성 중…"); show(box);
  try {
    const r = await api().create_tracker(headers, $("tkName").value.trim());
    if (r.cancelled) return box.classList.add("hidden");
    if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
    EXP = r.out; setPath("expPath", r.out);   // 만든 트래커를 바로 현재 대상으로
    show(box, `<span class="ok">✅ 트래커 생성됨</span> <span class="mono">${esc(r.headers.join(" · "))}</span><div style="margin-top:6px">이제 <b>코드 삽입</b> 탭에서 스크립트에 로거를 추가하세요. <button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}
async function analyzeExpData() {
  if (!EXP) return alert("트래커 엑셀을 선택하세요.");
  const box = $("analyzeResult");
  spin(box, "AI가 데이터를 분석하고 있습니다… (수십 초 이상 소요될 수 있습니다)"); show(box);
  const q = $("analyzeQ").value.trim();
  const r = await api().tracker_analyze(EXP, q);
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  
  // r.answer 에 마크다운 텍스트(표, 통계 포함) 반환됨. 간단히 렌더링.
  // hljs 나 marked 가 있다면 좋겠지만 없으면 esc 후 보존
  const formatted = esc(r.answer).replace(/\n/g, "<br>");
  show(box, `<span class="ok">✅ 분석 완료</span><div style="margin-top:10px; font-size:14px; line-height:1.6; color:var(--ink-2); background:var(--canvas); padding:12px; border-radius:8px;">${formatted}</div>`);
}


/* ── 데이터: 자동 영수증 작성 ── */
let RECEIPT_TPL = ""; // 사용자 선택 양식 (기본값 설정됨)
async function initReceiptTpl() {
  let dir = "";
  try { dir = await api().project_dir(); } catch (e) {}
  if(dir) {
    RECEIPT_TPL = dir + "\\planing\\엑셀 간이영수증 표준 양식 v2.0.xlsx";
    setPath("receiptTplPath", RECEIPT_TPL);
  }
}
async function pickReceiptTpl() {
  const p = await api().pick_file("xlsx");
  if (p) { RECEIPT_TPL = p; setPath("receiptTplPath", p); }
}
async function makeReceipt() {
  const text = $("receiptText").value.trim();
  if (!text) return alert("영수증 내용(텍스트)을 입력하세요.");
  // Default to standard template if not selected
  if (!RECEIPT_TPL) {
    await initReceiptTpl();
  }
  const box = $("receiptResult"); spin(box, "AI가 영수증 분석 및 엑셀 생성 중…"); show(box); $("receiptGoBtn").disabled = true;
  try {
    const r = await api().excel_make_receipt(text, RECEIPT_TPL);
    if (r.error) show(box, `<span class="err">${esc(r.error)}</span>`);
    else show(box, `<span class="ok">✅ 자동 작성 완료 (수식 보존)</span> <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
  $("receiptGoBtn").disabled = false;
}

/* ── 벡터 변환 (비트맵 → SVG) ── */
let VEC = "";
async function pickVec() { const p = await api().pick_file("image"); if (p) { VEC = p; setPath("vecPath", p); } }
const VEC_CATNAME = { lineart: "흑백 선화", diagram: "컬러 도식", logo: "로고·아이콘", photo: "사진" };
// 수동 설정 칸은 '수동 직접 설정'일 때만 열어 둔다 — 그 외에는 유형별 프리셋이 값을 정한다.
function onVecPresetChange(preset) {
  const manual = preset === "custom";
  ["vecColor", "vecMode", "vecSpeckle", "vecQuant"].forEach((id) => { $(id).disabled = !manual; });
}

async function vectorize() {
  if (!VEC) return alert("이미지를 선택하세요.");
  const rmbg = $("vecRmBg").checked;
  const at = $("vecAutotune").checked;
  const box = $("vecResult");
  spin(box, (rmbg ? "배경 제거 후 " : "") + (at ? "정밀 자동 튜닝 중(후보 여러 개 비교)… " : "벡터 변환 중… ") + "오래 걸리면 ■ 중지로 취소하세요");
  show(box); $("vecBtn").disabled = true;
  $("vecStop").classList.remove("hidden");
  $("vecPreview").classList.add("hidden");
  try {
    const r = await api().vectorize(VEC, $("vecColor").value, $("vecMode").value, $("vecSpeckle").value, rmbg, $("vecQuant").value, $("vecRes").value, $("vecPreset").value, at);
    if (r.cancelled) { show(box, `<span class="err">■ 변환을 중지했습니다.</span>`); }
    else if (r.error) { show(box, `<span class="err">${esc(r.error)}</span>`); }
    else {
      const kb = (n) => (n / 1024).toFixed(0) + "KB";
      const dm = r.dims ? ` · ${r.dims[0]}×${r.dims[1]}px${r.upscaled ? "(확대 트레이스)" : ""}` : "";
      const ds = dm + (r.removed_bg ? " · 배경 제거됨" : "");
      const cat = ` · 유형: <b>${VEC_CATNAME[r.category] || r.category || "auto"}</b>` + (r.variant && r.variant !== "기본" ? `(${esc(r.variant)})` : "");
      // 점수는 실제로 측정됐을 때만 표시한다 (node/resvg 없으면 생략)
      const q = (r.ssim != null) ? ` · 재현도 SSIM <b>${r.ssim}%</b>${r.ink_f1 != null ? ` · 획 보존 <b>${r.ink_f1}%</b>` : ""}` : "";
      const wn = r.warn ? `<div class="warn" style="margin-top:8px">⚠️ ${esc(r.warn)}</div>` : "";
      show(box, `<span class="ok">✅ 변환 완료</span> <span class="mono">${kb(r.in_size)} → ${kb(r.out_size)} SVG</span>${ds}${cat}${q} <span class="mono">${esc(r.out)}</span>${wn}<div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
      if (r.preview && r.svg) {
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기 (벡터)</div><div class="vecprev-box">${r.svg}</div>`);
      } else if (r.preview_png) {
        // SVG가 커서 인라인 렌더는 위험 → 결과물을 이미지로 렌더해 보여준다(실제 파일은 벡터).
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기 (변환 결과를 이미지로 렌더)</div><div class="vecprev-box"><img src="${r.preview_png}" style="max-width:100%;display:block;margin:0 auto"></div>`);
      } else {
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기</div><div class="vecprev-box" style="padding:24px;color:var(--ink-muted)">SVG 용량이 커서 인라인 미리보기는 생략했어요. <b>폴더 열기</b>로 확인하세요.</div>`);
      }
    }
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
  $("vecBtn").disabled = false;
  $("vecStop").classList.add("hidden");
}
async function cancelVec() {
  try { await api().cancel_vectorize(); } catch (e) {}
  $("vecStop").classList.add("hidden");
}


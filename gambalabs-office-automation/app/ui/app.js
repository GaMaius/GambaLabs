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
  exp: ["var(--teal)", "📈", "실험/재무 기록 + 자동 차트", "결과를 자연어로 적으면 트래커에 한 줄로 기록하고 추이 차트를 자동 갱신합니다. 같은 파일에 계속 누적돼요.", ["① 트래커 선택/생성", "② 기록 미리보기", "③ 기록 + 차트"]],
  dash: ["var(--teal)", "▤", "대시보드 수정", "기존 엑셀을 자연어로 수정합니다. 수식·차트는 그대로 두고 값만 바꿔요.", ["① 엑셀 선택 + 요청", "② 변경 미리보기", "③ 적용"]],
  analyze: ["var(--teal)", "🔎", "분석 · 요약", "엑셀을 AI가 읽고 핵심 요약·추세·이상치·최적 조건을 알려줍니다.", ["① 엑셀 선택", "② 분석/요약"]],
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
  ["exp", "dash", "analyze"].forEach((k) => $("data-" + k).classList.toggle("hidden", k !== m));
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
/* 실험 로거 스니펫(실제 프로젝트 경로 삽입) */
async function fillSnippet() {
  const el = $("expSnippet"); if (!el) return;
  let dir = "";
  try { dir = await api().project_dir(); } catch (e) {}
  el.textContent =
    `import sys; sys.path.insert(0, r"${dir || '...\\\\gambalabs-office-automation'}")\n` +
    `from gamba_log import log_result\n\n` +
    `log_result({"정확도(%)": 92.3, "SNR(dB)": -20, "오인식(건)": 1, "비고": "튜닝"})`;
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
    fillSnippet();
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
  try { await api().set_model($("modelSel").value); } catch (e) {}
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
/* 채운 항목 배지(●) 표시 */
function markFilled() {
  refreshSwatches();
  const set = (id, on) => { const e = $(id); if (e) e.textContent = on ? "●" : ""; };
  set("b_purpose", $("qPurpose").value.trim());
  set("b_direction", $("qDirection").value.trim());
  set("b_ratio", $("qRatio").dataset.val !== "16:9");
  set("b_color", $("qAccent").value.toLowerCase() !== "#0038a3" || $("qInk").value.toLowerCase() !== "#1a1a1a" || $("qBgTone").dataset.val !== "light" || $("qSeedTheme").value);
  set("b_bg", $("qBg").dataset.val !== "solid");
  set("b_font", $("qFont").dataset.val !== "맑은 고딕");
  set("b_refs", REFS.length);
}
/* 기반 테마 → 폼 색 시드 */
async function seedFromTheme() {
  const id = $("qSeedTheme").value; if (!id) return;
  try {
    const c = await api().theme_colors(id);
    if (c && c.accent) $("qAccent").value = "#" + c.accent;
    if (c && c.ink) $("qInk").value = "#" + c.ink;
    if (c && c.bg) { const dark = parseInt(c.bg.slice(0, 2), 16) * 0.299 + parseInt(c.bg.slice(2, 4), 16) * 0.587 + parseInt(c.bg.slice(4, 6), 16) * 0.114 < 140; setChip("qBgTone", dark ? "dark" : "light"); }
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
function useSwatch(h) { $("qAccent").value = "#" + h; markFilled(); }
function applyAutoPalette() {
  if (!PALETTE) return;
  if (PALETTE.accent) $("qAccent").value = "#" + PALETTE.accent;
  if (PALETTE.ink) $("qInk").value = "#" + PALETTE.ink;
  if (PALETTE.bg) { const b = PALETTE.bg; const dark = parseInt(b.slice(0, 2), 16) * 0.299 + parseInt(b.slice(2, 4), 16) * 0.587 + parseInt(b.slice(4, 6), 16) * 0.114 < 140; setChip("qBgTone", dark ? "dark" : "light"); }
  markFilled();
}
function readDesignForm() {
  const bgTone = $("qBgTone").dataset.val;
  const bg = bgTone === "dark" ? "141a2b" : "f6f8fc";   // 배경 톤 → 배경색
  const font = $("qFont").dataset.val === "__custom" ? ($("qFontCustom").value.trim() || "맑은 고딕") : $("qFont").dataset.val;
  return {
    purpose: $("qPurpose").value.trim(),
    direction: $("qDirection").value.trim(),
    ratio: $("qRatio").dataset.val,
    bg, accent: $("qAccent").value.replace("#", ""), ink: $("qInk").value.replace("#", ""),
    band_fill: true, gradient: $("qBg").dataset.val === "gradient",
    font, refs: REFS.slice(),
  };
}
async function applyFormTheme() {
  const f = readDesignForm();
  try { await api().set_form_theme(f.bg, f.accent, f.ink, f.band_fill, f.font, f.gradient); } catch (e) {}
  try { await api().set_design_brief(f.purpose, f.direction, f.refs); } catch (e) {}
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

/* ── 사용 가이드(온보딩) ── */
function openHelp() { $("helpModal").classList.remove("hidden"); }
function closeHelp() { $("helpModal").classList.add("hidden"); }
function helpDontShow() { localStorage.setItem("helpHide", $("helpDontShow").checked ? "1" : "0"); }
// 온보딩 모달은 자동으로 띄우지 않는다 — 각 탭·모드에 인라인 설명이 항상 보이므로.
// 전체 개요가 필요하면 사이드바 ❓로 연다.
window.addEventListener("pywebviewready", initStatus);
renderRefs(); markFilled();   // 폼 초기 상태(참고자료 목록·배지·스와치)
mhRender($("ppt-modehelp"), PPT_MODEHELP.theme);   // 초기 모드 설명
mhRender($("data-modehelp"), DATA_MODEHELP.exp);
fillSnippet();   // 경로 미확정 시 폴백 표시(이후 initStatus에서 실제 경로로 갱신)

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
    show(box, `<span class="ok">✅ 트래커 생성됨</span> <span class="mono">${esc(r.headers.join(" · "))}</span><div style="margin-top:6px">이제 아래에 결과를 적고 <b>기록</b>하세요. <button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
}
function expRowTable(headers, mapped, blanks) {
  const bset = new Set(blanks || []);
  const th = headers.map((h) => `<th>${esc(h)}</th>`).join("");
  const td = headers.map((h) => { const v = mapped[h]; const empty = bset.has(h) || v === "" || v == null; return `<td class="${empty ? "to" : ""}">${empty ? "—" : esc(v)}</td>`; }).join("");
  return `<table class="chg"><tr>${th}</tr><tr>${td}</tr></table>`;
}
async function previewExp() {
  if (!EXP) return alert("트래커 엑셀을 선택하세요.");
  const llm = true; const box = $("expPreview");   // LLM 항상 사용
  spin(box, llm ? "AI가 해석 중… (로컬 모델이면 수 초~수십 초)" : "해석 중…"); show(box);
  const r = await api().exp_log_preview(EXP, $("expText").value, llm);
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  const warn = (r.blanks && r.blanks.length) ? `<div class="hint" style="margin-top:6px">빈 칸(설명에 근거 없음): ${r.blanks.map(esc).join(", ")}</div>` : "";
  show(box, `<div class="pill">${esc(r.engine)} · ${esc(r.sheet)}</div>${expRowTable(r.headers, r.mapped, r.blanks)}${warn}`);
}
async function logExp() {
  if (!EXP) return alert("트래커 엑셀을 선택하세요."); const llm = true; const cm = $("expChart").value;   // LLM 항상 사용
  const inPlace = $("expInPlace").checked;
  const box = $("expResult"); spin(box, llm ? "AI 파싱 후 기록 중…" : "기록 중…"); show(box); $("expGoBtn").disabled = true;
  const r = await api().exp_log(EXP, $("expText").value, llm, cm, inPlace); $("expGoBtn").disabled = false;
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  const rowHtml = Object.entries(r.appended).map(([k, v]) => `<div class="mono">• ${esc(k)}: ${esc(v === null || v === "" ? "—" : v)}</div>`).join("");
  const metric = r.chart_metric ? ` · 차트 지표: <b>${esc(r.chart_metric)}</b>` : "";
  EXP = r.out; setPath("expPath", r.out);   // 누적: 방금 기록한 파일을 다음 기록의 대상으로 자동 연결
  show(box, `<span class="ok">✅ ${esc(r.sheet)}에 기록 (총 ${r.total_rows}행)</span> <span class="t">${esc(r.engine || "")}</span>${metric}${rowHtml}<span class="mono">${esc(r.out)}</span><div style="margin-top:6px"><span class="hint">${r.in_place ? "선택한 파일에 직접 누적됩니다." : "이 로그 파일에 계속 누적됩니다(한 개)."}</span> <button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
}

/* ── 데이터: Excel→LLM 분석/요약 ── */
let ANALYZE = "";
async function pickAnalyze() { const p = await api().pick_file("xlsx"); if (p) { ANALYZE = p; setPath("analyzePath", p); } }
async function analyzeExcel() {
  if (!ANALYZE) return alert("엑셀을 선택하세요."); const box = $("analyzeResult"); spin(box, "분석 중… (로컬 모델이면 시간이 걸려요)"); show(box); $("analyzeBtn").disabled = true;
  try {
    const r = await api().excel_analyze(ANALYZE, $("analyzeQ").value);
    if (r.error) show(box, `<span class="err">${esc(r.error)}</span>`);
    else show(box, `<div style="white-space:pre-wrap;line-height:1.6">${esc(r.answer)}</div>`);
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
  $("analyzeBtn").disabled = false;
}

/* ── 벡터 변환 (비트맵 → SVG) ── */
let VEC = "";
async function pickVec() { const p = await api().pick_file("image"); if (p) { VEC = p; setPath("vecPath", p); } }
async function vectorize() {
  if (!VEC) return alert("이미지를 선택하세요.");
  const rmbg = $("vecRmBg").checked;
  const box = $("vecResult"); spin(box, (rmbg ? "배경 제거 후 " : "") + "벡터 변환 중… 오래 걸리면 ■ 중지로 취소하세요"); show(box); $("vecBtn").disabled = true;
  $("vecStop").classList.remove("hidden");
  $("vecPreview").classList.add("hidden");
  try {
    const r = await api().vectorize(VEC, $("vecColor").value, $("vecMode").value, $("vecSpeckle").value, rmbg, $("vecQuant").value, $("vecRes").value);
    if (r.cancelled) { show(box, `<span class="err">■ 변환을 중지했습니다.</span>`); }
    else if (r.error) { show(box, `<span class="err">${esc(r.error)}</span>`); }
    else {
      const kb = (n) => (n / 1024).toFixed(0) + "KB";
      const dm = r.dims ? ` · ${r.dims[0]}×${r.dims[1]}px` + (r.orig_dims && r.dims[0] === r.orig_dims[0] ? "(원본)" : "") : "";
      const ds = dm + (r.removed_bg ? " · 배경 제거됨" : "");
      show(box, `<span class="ok">✅ 변환 완료</span> <span class="mono">${kb(r.in_size)} → ${kb(r.out_size)} SVG</span>${ds} <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
      if (r.preview && r.svg) {
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기 (벡터)</div><div class="vecprev-box">${r.svg}</div>`);
      } else {
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기</div><div class="vecprev-box" style="padding:24px;color:var(--ink-muted)">SVG 용량이 커서 인라인 미리보기는 생략했어요. <b>폴더 열기</b>로 확인하세요. (사진보다 로고·아이콘에서 결과가 깔끔합니다)</div>`);
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

/* ── 데이터: 대시보드 수정 ── */
async function pickXlsx() { const p = await api().pick_file("xlsx"); if (p) { XLSX = p; setPath("xlsxPath", p); } }
async function previewExcel() {
  if (!XLSX) return alert("엑셀을 선택하세요."); const box = $("excelPreview"); spin(box); show(box);
  const r = await api().excel_preview($("reqText").value, XLSX);
  if (r.error) return show(box, `<div class="result"><span class="err">${esc(r.error)}</span></div>`);
  lastUpdates = r.updates;
  if (!r.updates.length) return show(box, `<div class="result">감지된 변경이 없습니다.</div>`);
  const rows = r.updates.map((u) => `<tr><td>${esc(u.sheet_name)}</td><td>${esc(u.item_name)}</td><td>${esc(u.column_name)}</td><td class="to">${esc(u.new_value)}</td></tr>`).join("");
  show(box, `<div class="pill">엔진: ${esc(r.engine)} · ${r.updates.length}건</div><table class="chg"><tr><th>시트</th><th>항목</th><th>컬럼</th><th>변경값</th></tr>${rows}</table>`);
}
async function applyExcel() {
  if (!XLSX) return alert("엑셀을 선택하세요."); const box = $("excelResult"); spin(box); show(box);
  const r = await api().excel_apply($("reqText").value, XLSX, lastUpdates);
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  const logs = r.logs.map((l) => `<div class="mono">• ${esc(l)}</div>`).join("");
  show(box, `<span class="ok">✅ 적용 완료 (수식·차트 보존)</span>${logs}<span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
}

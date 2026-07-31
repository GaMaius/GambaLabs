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
/* 모드 토글 */
function pptMode(m) {
  document.querySelectorAll('#tab-ppt .seg button').forEach((x) => x.classList.toggle("on", x.dataset.m === m));
  ["auto", "spec", "chat", "import"].forEach((k) => $("ppt-" + k).classList.toggle("hidden", k !== m));
}
function dataMode(m) {
  document.querySelectorAll('#tab-data .seg button').forEach((x) => x.classList.toggle("on", x.dataset.m === m));
  ["exp", "dash", "analyze"].forEach((k) => $("data-" + k).classList.toggle("hidden", k !== m));
}

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
  } catch (e) {}
}
let THEME_OPTS = [];
function refreshThemes(th) {
  THEME_OPTS = th.options || [];
  const ts = $("themeSel"); ts.innerHTML = "";
  THEME_OPTS.forEach((t) => { const o = document.createElement("option"); o.value = t.id; o.textContent = t.label + (t.custom ? " (커스텀)" : ""); o.title = t.desc || ""; if (t.id === th.current) o.selected = true; ts.appendChild(o); });
  updateThemeDel();
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

/* ── 디자인 보조(스펙) 모드 숨김 토글 ── */
let SPEC_ON = localStorage.getItem("specMode") === "1";
function applySpecVisibility() {
  $("segSpec").style.display = SPEC_ON ? "" : "none";
  $("specToggle").textContent = SPEC_ON ? "－ 디자인 보조(스펙) 모드 숨기기" : "＋ 디자인 보조(스펙) 모드 표시";
  if (!SPEC_ON && $("segSpec").classList.contains("on")) pptMode("auto");
}
function toggleSpec() { SPEC_ON = !SPEC_ON; localStorage.setItem("specMode", SPEC_ON ? "1" : "0"); applySpecVisibility(); }
applySpecVisibility();
window.addEventListener("pywebviewready", initStatus);

/* ── PPT 풀 자동 ── */
async function pickPpt() { const p = await api().pick_file("doc"); if (p) { PPT = p; setPath("pptPath", p); } }
async function previewPpt() {
  if (!PPT) return alert("문서를 선택하세요.");
  const llm = $("autoLLM").checked;
  spin($("pptOutline"), llm ? "AI가 문서를 구조화 중… (로컬 모델이면 수십 초~수 분)" : "분석 중…"); show($("pptOutline"));
  const r = await api().ppt_preview(PPT, llm);
  if (r.error) return show($("pptOutline"), `<span class="err">${esc(r.error)}</span>`);
  const li = r.outline.map((s, i) => `<li><b>${i + 1}</b> ${esc(s.title)} <span class="t">${esc(s.type)}</span></li>`).join("");
  show($("pptOutline"), `<div class="pill">${esc(r.engine || "")} · 표지 + ${r.outline.length} 본문 + 마무리</div><div style="margin-top:6px"><b>${esc(r.title)}</b></div><ul class="outline-list">${li}</ul>`);
}
async function makePpt() {
  if (!PPT) return alert("문서를 선택하세요.");
  const llm = $("autoLLM").checked;
  spin($("pptResult"), llm ? "AI 구조화 후 생성 중…" : "생성 중…"); show($("pptResult")); $("pptGoBtn").disabled = true;
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
  const llm = $("importLLM").checked;
  spin($("importOutline"), llm ? "AI가 해석 중… (로컬 모델이면 수십 초~수 분)" : "해석 중…"); show($("importOutline"));
  const r = await api().ppt_import_preview(IMPORT, llm);
  if (r.error) return show($("importOutline"), `<span class="err">${esc(r.error)}</span>`);
  const sub = r.subtitle ? ` · <span style="color:var(--ink-muted)">${esc(r.subtitle)}</span>` : "";
  const li = r.outline.map((s, i) => `<li><b>${i + 1}</b> ${esc(s.title)} ${s.extras ? `<span class="t">${esc(s.extras)}</span>` : ""}</li>`).join("");
  show($("importOutline"), `<div class="pill">${esc(r.engine || "")} · ${r.outline.length} 슬라이드</div><div style="margin-top:6px"><b>${esc(r.title || "")}</b>${sub}</div><ul class="outline-list">${li}</ul>`);
}
async function makeImport() {
  if (!IMPORT) return alert("PPTX를 선택하세요.");
  const llm = $("importLLM").checked;
  spin($("importResult"), llm ? "AI 해석 후 생성 중…" : "생성 중…"); show($("importResult")); $("importGoBtn").disabled = true;
  const r = await api().ppt_import_make(IMPORT, llm); $("importGoBtn").disabled = false;
  if (r.error) return show($("importResult"), `<span class="err">${esc(r.error)}</span>`);
  show($("importResult"), `<span class="ok">✅ ${r.count}장 생성</span> <span class="t">${esc(r.engine || "")}</span> <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
}

/* ── 데이터: 실험 기록 ── */
async function pickExp() { const p = await api().pick_file("xlsx"); if (p) { EXP = p; setPath("expPath", p); } }
async function logExp() {
  if (!EXP) return alert("트래커 엑셀을 선택하세요."); const box = $("expResult"); spin(box); show(box);
  const r = await api().exp_log(EXP, $("expText").value);
  if (r.error) return show(box, `<span class="err">${esc(r.error)}</span>`);
  const rowHtml = Object.entries(r.appended).map(([k, v]) => `<div class="mono">• ${esc(k)}: ${esc(v)}</div>`).join("");
  show(box, `<span class="ok">✅ ${esc(r.sheet)}에 기록 (총 ${r.total_rows}행) · 차트 자동 갱신</span>${rowHtml}<span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
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
  const box = $("vecResult"); spin(box, rmbg ? "배경 제거 후 벡터 변환 중… (첫 사용은 모델 준비로 잠깐)" : "벡터 변환 중… (사진·큰 이미지는 다소 걸릴 수 있어요)"); show(box); $("vecBtn").disabled = true;
  $("vecPreview").classList.add("hidden");
  try {
    const r = await api().vectorize(VEC, $("vecColor").value, $("vecMode").value, $("vecSpeckle").value, rmbg);
    if (r.error) { show(box, `<span class="err">${esc(r.error)}</span>`); }
    else {
      const kb = (n) => (n / 1024).toFixed(0) + "KB";
      const ds = (r.downscaled ? " · 축소 후 변환" : "") + (r.removed_bg ? " · 배경 제거됨" : "");
      show(box, `<span class="ok">✅ 변환 완료</span> <span class="mono">${kb(r.in_size)} → ${kb(r.out_size)} SVG</span>${ds} <span class="mono">${esc(r.out)}</span><div style="margin-top:8px"><button class="btn btn-util" onclick="api().open_folder('${bs(r.out)}')">폴더 열기</button></div>`);
      if (r.preview && r.svg) {
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기 (벡터)</div><div class="vecprev-box">${r.svg}</div>`);
      } else {
        show($("vecPreview"), `<div class="vecprev-lbl">미리보기</div><div class="vecprev-box" style="padding:24px;color:var(--ink-muted)">SVG 용량이 커서 인라인 미리보기는 생략했어요. <b>폴더 열기</b>로 확인하세요. (사진보다 로고·아이콘에서 결과가 깔끔합니다)</div>`);
      }
    }
  } catch (e) { show(box, `<span class="err">${esc(e.message || e)}</span>`); }
  $("vecBtn").disabled = false;
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

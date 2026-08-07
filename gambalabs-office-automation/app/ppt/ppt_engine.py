# -*- coding: utf-8 -*-
"""문서(md/txt) → 슬라이드 플랜(JSON) → pptxgenjs 렌더 → 브랜드 .pptx.

원칙: LLM은 '무엇을 담을지' 구조화만, 렌더링은 결정적(render_deck.js).
키가 있으면 GPT가 플랜을 짜고, 없으면 결정적 파서가 짠다. antigravity 결함
(빈 표지 슬라이드·마크다운 노출·중첩 붕괴)을 파서 단계에서 방지한다.
"""
import os
import re
import json
import subprocess
import tempfile

from src.common import paths

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ASSETS = paths.ASSETS_DIR
RENDERER = os.path.join(HERE, "render_deck.js")


def _strip_md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)          # bold
    s = re.sub(r"`([^`]+)`", r"\1", s)              # code
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)  # link
    s = s.replace("**", "").replace("`", "")
    return s.strip()


def _clean_title(s: str) -> str:
    s = re.sub(r"^#+\s*", "", s)
    s = re.sub(r"^\s*\[[^\]]*\]\s*", "", s)            # 앞쪽 [태그] 제거
    s = re.sub(r"^[^\w가-힣]*", "", s)                 # 앞쪽 이모지/기호 제거
    s = re.sub(r"^Slide\s*\d+\s*[.:]\s*", "", s, flags=re.I)
    return _strip_md(s).strip()


def build_plan_rules(doc_path: str) -> dict:
    with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    lines = raw.splitlines()

    title = os.path.splitext(os.path.basename(doc_path))[0]
    for ln in lines:
        if ln.strip().startswith("# ") and not ln.strip().startswith("## "):
            title = _clean_title(ln); break

    # H2(##) 기준으로 블록 분할
    blocks, cur = [], None
    for ln in lines:
        s = ln.rstrip()
        if s.startswith("## "):
            if cur:
                blocks.append(cur)
            cur = {"title": _clean_title(s), "lines": []}
        elif cur is not None:
            cur["lines"].append(s)
    if cur:
        blocks.append(cur)

    plan = {"title": title, "subtitle": "", "slides": [],
            "tagline": "Proprietary Technology, Ultimate Result",
            "contact": "Contact: contact@gambalabs.ai  |  https://gambalabs.ai"}

    def parse_block(b):
        lead, bullets, rows, content = "", [], [], []
        for ln in b["lines"]:
            t = ln.strip()
            if not t:
                continue
            if t.startswith("### ") or (not lead and re.fullmatch(r"\*\*.+\*\*", t)):
                if not lead:
                    lead = _clean_title(t)
                continue
            if t.startswith("|") and t.endswith("|"):
                if "---" in t:
                    continue
                rows.append([c.strip() for c in t.strip("|").split("|")])
                continue
            if re.match(r"^[-*]\s+", t) or re.match(r"^\d+\.\s+", t):
                bullets.append(_strip_md(re.sub(r"^([-*]|\d+\.)\s+", "", t)))
                continue
            if not t.startswith("```") and not t.startswith("["):
                content.append(_strip_md(t))
        return lead, bullets, rows, content

    for i, b in enumerate(blocks):
        lead, bullets, rows, content = parse_block(b)
        title_l = b["title"].lower()
        is_cover = any(k in b["title"] for k in ["표지"]) or any(k in title_l for k in ["title", "cover"])
        is_closing = any(k in b["title"] for k in ["문의", "감사", "Q&A", "Contact"]) or "contact" in title_l

        if is_cover:
            if lead:
                plan["subtitle"] = lead
            continue
        if is_closing:
            if lead:
                plan["tagline"] = lead
            for c in bullets + content:
                if "@" in c or "http" in c:
                    plan["contact"] = c
            continue

        if rows:
            plan["slides"].append({"type": "table", "title": b["title"], "lead": lead, "rows": rows})
        elif bullets:
            short = 2 <= len(bullets) <= 4 and all(len(x) <= 60 for x in bullets)
            if short:
                plan["slides"].append({"type": "cards", "title": b["title"], "lead": lead, "items": bullets})
            else:
                plan["slides"].append({"type": "text", "title": b["title"], "lead": lead, "bullets": bullets})
        else:
            plan["slides"].append({"type": "text", "title": b["title"], "lead": lead, "bullets": content[:8]})

    return plan


PLAN_SCHEMA = """PLAN(JSON) = {"title","subtitle","slides":[...]}. 각 슬라이드는 내용 성격에 가장 잘 맞는 풍부한 레이아웃 type을 자유롭게 선택하라:
- "metrics"(핵심 수치/지표 강조 카드): {"type":"metrics","title","lead","metrics":[{"value":"90%+","label":"인식률","desc":"SNR -20dB 조건"}]}
- "compare"(두 대상/전후 비교): {"type":"compare","title","lead","left":{"name":"A안","points":[".."]},"right":{"name":"B안","points":[".."]},"chart":{"kind":"doughnut","cats":["A","B"],"vals":[70,30]}}
- "cards"(병렬 핵심 항목 2~4개): {"type":"cards","title","lead","items":["..",".."]}
- "table"(표 수치/비교): {"type":"table","title","lead","rows":[["헤더1","헤더2"],["..",".."]]}
- "content"(불릿 + 차트/이미지/그라데이션): {"type":"content","title","lead","bullets":[{"text": "강조할 내용", "emphasis": true}, "일반 내용"],"chart":{"kind":"bar|pie|line|doughnut","trend":true,"cats":["2024","2025"],"vals":[50,90]},"image":{"query":"voice recognition","mode":"background"}}
- "text"(요약 불릿 목록): {"type":"text","title","lead","bullets":["..",".."]}"""


def _brief_block(brief: str) -> str:
    """디자인 브리프(목적·자유 디렉션·참고자료)를 프롬프트 상단 지시로 변환."""
    b = (brief or "").strip()
    if not b:
        return ""
    return ("\n[제작자 브리프 — 아래 목적·디렉션·참고자료를 슬라이드 구성·강조·문구에 최대한 반영하라. "
            "참고자료는 사실 근거로만 쓰고 그대로 복붙하지 마라.]\n" + b[:30000] + "\n")


def interpret_llm(raw_text: str, title_hint: str = "", strict: bool = True, brief: str = "") -> dict:
    """문서를 LLM(Groq/GPT-4o)이 읽고 슬라이드 구조로 나눈다. strict=False면 온전한 Freeform 설계."""
    from src.common.llm_client import get_llm_client_and_model
    client, model_name = get_llm_client_and_model()
    doc = raw_text[:120000]  # 대용량 모델 128k 컨텍스트 지원 (전체 문서 수용)

    if not strict:
        prompt = f"""너는 세계 최고의 발표자료(PPT) 디자이너다. 고정된 규칙이나 템플릿에 얽매이지 말고, 제공된 문서를 해석하여 가장 매력적이고 입체적인 발표자료 PLAN(JSON)을 '온전히 너의 자율적 판단'으로 설계하라.

[FREEFORM 완전 자율 설계 지침]
1. 문서의 핵심 주제, 논리 흐름, 강조해야 할 메시지를 스스로 분석하여 최선의 슬라이드 구성(개수, 유형, 강조점)을 결정하라.
2. 특정 템플릿 패턴에 치우치지 말고, 수치 지표("metrics"), 비교("compare"), 차트/이미지/그라데이션("content"), 카드 그리드("cards"), 데이터 표("table"), 요약 불릿("text") 등 슬라이드마다 가장 효과적인 레이아웃을 자유롭게 조합하라.
3. 시각적 완성도를 높이기 위해, PLAN(JSON) 최상위(plan 레벨)에 `fontScale` (예: 1.1), `titleFont` (예: "Pretendard", "나눔스퀘어"), `bodyFont`를 자유롭게 지정해 폰트와 크기를 바꾸고, 본문 내 텍스트는 `{"text": "내용", "emphasis": true}` 형태를 활용하여 핵심을 강조하라.
4. 원문 복붙을 금지하고 발표용으로 임팩트 있고 명확하게 문구를 다듬어라.

{PLAN_SCHEMA}
{_brief_block(brief)}
[문서]
{doc}"""
    else:
        prompt = f"""다음 문서를 감바랩스 발표자료 PLAN(JSON)으로 구조화하라. 규칙을 반드시 지켜라.

[규칙]
- title: 문서 전체를 대표하는 제목. subtitle: 한 줄 부제(없으면 "").
- 문서의 실제 길이와 분량, 논리 전개에 맞춰 필요한 슬라이드 개수를 자유롭게 생성하라. (단문은 3~5개, 장문 보고서/논문은 8~15개 이상으로 풍부하게 나눌 것)
- 각 슬라이드의 title은 핵심을 담아 짧고 명확하게 작성하라.
- 슬라이드 유형(type)을 내용 성격에 맞게 입체적이고 다양하게 선택하라:
  · 핵심 숫자/지표/성과가 나오면 ➡️ "metrics" (큰 수치 카드)
  · A vs B 비교, 전/후 비교, 장단점 ➡️ "compare" (2열 비교 및 도넛 차트)
  · 차트/그래프/이미지 필요 시 ➡️ "content" (chart 또는 image 포함)
  · 주요 항목 2~4개 병렬 배치 ➡️ "cards" (카드 그리드)
  · 데이터 수치/표 ➡️ "table" (행/열 데이터)
  · 일반 설명/요약 ➡️ "text" (불릿 리스트)
- bullets/items는 원문 복붙 금지 — 한 항목을 한 줄로 간결하고 임팩트 있게 요약. 마크다운 기호(#,*,`,|) 제거.
- 표지·목차·마무리는 만들지 마라(렌더러가 자동 생성한다).
- 색/폰트/테마는 절대 넣지 마라. 설명 없이 오직 JSON만 출력.
{PLAN_SCHEMA}
{_brief_block(brief)}
[문서]
{doc}"""
    resp = client.chat.completions.create(
        model=model_name, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": "You output only valid JSON. 한국어 내용은 그대로 보존한다."},
                  {"role": "user", "content": prompt}])
    return _normalize_llm(json.loads(resp.choices[0].message.content), title_hint, strict=strict)


def _normalize_llm(plan: dict, title_hint: str = "", strict: bool = True) -> dict:
    """LLM 출력 보정: 다양한 슬라이드 유형(metrics, compare, content, table, cards, text) 보존 및 검증."""
    if not isinstance(plan, dict):
        plan = {}
    if not (plan.get("title") or "").strip():
        plan["title"] = title_hint or "발표자료"
    plan.setdefault("subtitle", "")

    # Freeform 모드(strict=False)일 경우, 강제 규격화(type 덮어쓰기, 속성 제거)를 
    # 완전히 우회하여 LLM의 자율적 판단(fontScale, 강조 등)을 온전히 렌더러에 전달한다.
    if not strict:
        if not isinstance(plan.get("slides"), list):
            plan["slides"] = []
        return plan

    out = []
    for sl in (plan.get("slides") or []):
        if not isinstance(sl, dict):
            continue
        t = _clean_title(str(sl.get("title") or ""))
        lead = _strip_md(str(sl.get("lead") or "")).strip()
        typ = str(sl.get("type") or "text").strip().lower()

        # 1. metrics 수치 지표 카드
        if typ == "metrics" and sl.get("metrics"):
            mets = []
            for m in sl.get("metrics", []):
                if isinstance(m, dict) and m.get("value"):
                    mets.append({
                        "value": str(m.get("value")),
                        "label": str(m.get("label") or ""),
                        "desc": str(m.get("desc") or "")
                    })
            if mets:
                out.append({"type": "metrics", "title": t, "lead": lead, "metrics": mets[:4]})
                continue

        # 2. compare 비교 슬라이드
        if typ == "compare" and (sl.get("left") or sl.get("right")):
            left = sl.get("left") if isinstance(sl.get("left"), dict) else {"name": "A안", "points": []}
            right = sl.get("right") if isinstance(sl.get("right"), dict) else {"name": "B안", "points": []}
            cmp_dict = {"type": "compare", "title": t, "lead": lead, "left": left, "right": right}
            if isinstance(sl.get("chart"), dict):
                cmp_dict["chart"] = sl["chart"]
            out.append(cmp_dict)
            continue

        # 3. table 표 슬라이드
        if typ == "table":
            rows = [[str(c).strip() for c in r] for r in (sl.get("rows") or []) if isinstance(r, (list, tuple)) and r]
            if rows:
                out.append({"type": "table", "title": t, "lead": lead, "rows": rows})
                continue

        # 4. content 차트/이미지/그라데이션 포함 슬라이드
        if typ == "content" or sl.get("chart") or sl.get("image") or sl.get("gradient"):
            cnt_dict = {"type": "content", "title": t, "lead": lead}
            bullets = [_strip_md(str(x)).strip() for x in (sl.get("bullets") or []) if str(x).strip()]
            if bullets:
                cnt_dict["bullets"] = bullets[:8]
            if isinstance(sl.get("chart"), dict):
                cnt_dict["chart"] = sl["chart"]
            if isinstance(sl.get("image"), dict):
                cnt_dict["image"] = sl["image"]
            if isinstance(sl.get("gradient"), dict):
                cnt_dict["gradient"] = sl["gradient"]
            out.append(cnt_dict)
            continue

        # 5. cards 병렬 카드 또는 text 서술형 불릿
        items = [_strip_md(str(x)).strip() for x in (sl.get("items") or []) if str(x).strip()]
        bullets = [_strip_md(str(x)).strip() for x in (sl.get("bullets") or []) if str(x).strip()]
        pool = items or bullets
        if not t and not pool:
            continue

        if typ == "cards" or (strict and 2 <= len(pool) <= 4 and all(len(x) <= 60 for x in pool)):
            out.append({"type": "cards", "title": t, "lead": lead, "items": pool[:4]})
        else:
            out.append({"type": "text", "title": t, "lead": lead, "bullets": pool[:8]})

    if not out:
        raise ValueError("LLM 플랜이 비었음")
    plan["slides"] = out
    return plan


def build_plan(doc_path: str, use_llm: bool = False, brief: str = "") -> dict:
    """기본은 규칙 기반(즉시·안정). use_llm=True면 LLM이 문서를 구조화(로컬이면 느림), 실패 시 규칙으로 폴백."""
    if use_llm and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
        from app.ppt import design_policy
        try:
            with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            title_hint = os.path.splitext(os.path.basename(doc_path))[0]
            return interpret_llm(raw, title_hint, strict=design_policy.is_strict(), brief=brief)
        except Exception as e:
            print(f"[ppt_engine] LLM 구조화 실패({e}) → 규칙 기반")
    return build_plan_rules(doc_path)


def generate(doc_path: str, out_pptx: str, assets_dir: str = DEFAULT_ASSETS, theme: str = None,
             use_llm: bool = False, theme_config: dict = None, brief: str = "") -> str:
    # 강한 모델이면 freeform 엔진(LLM이 pptxgenjs 코드 직접 생성) 시도
    if use_llm and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
        from app.ppt import design_policy
        if not design_policy.is_strict():
            try:
                from app.ppt.freeform_engine import generate_freeform_from_file
                return generate_freeform_from_file(
                    doc_path, out_pptx, assets_dir, theme, theme_config, brief)
            except Exception as e:
                print(f"[ppt_engine] freeform 생성 실패({e}) → 기존 렌더러로 폴백")

    # 폴백: 기존 JSON Plan → render_deck.js 경로
    plan = build_plan(doc_path, use_llm=use_llm, brief=brief)
    if theme:
        plan["theme"] = theme
    if theme_config:
        plan["themeConfig"] = theme_config
    os.makedirs(os.path.dirname(os.path.abspath(out_pptx)), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(plan, tf, ensure_ascii=False)
        plan_path = tf.name
    try:
        res = subprocess.run([paths.node_exe(), RENDERER, plan_path, assets_dir, out_pptx],
                             capture_output=True, text=True, cwd=paths.node_cwd())
        if res.returncode != 0:
            raise RuntimeError(f"render_deck.js 실패: {res.stderr[-500:]}")
    finally:
        os.unlink(plan_path)
    return out_pptx


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("사용법: python -m app.ppt.ppt_engine <문서.md> [출력.pptx]")
        raise SystemExit(2)
    doc = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(paths.OUTPUT_DIR, "gambalabs_deck.pptx")
    print("생성:", generate(doc, out))
    print("슬라이드 플랜 미리보기:")
    print(json.dumps(build_plan(doc), ensure_ascii=False, indent=2)[:800])

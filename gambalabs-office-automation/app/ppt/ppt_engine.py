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

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(HERE))
DEFAULT_ASSETS = os.path.join(PROJECT_DIR, "ppt-skill", "assets")
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


PLAN_SCHEMA = ('PLAN JSON: {"title","subtitle","slides":[{"type":"text|cards|table",'
               '"title","lead","bullets":["..."],"items":["..."],"rows":[["헤더..","..."]]}]}')


def _brief_block(brief: str) -> str:
    """디자인 브리프(목적·자유 디렉션·참고자료)를 프롬프트 상단 지시로 변환."""
    b = (brief or "").strip()
    if not b:
        return ""
    return ("\n[제작자 브리프 — 아래 목적·디렉션·참고자료를 슬라이드 구성·강조·문구에 최대한 반영하라. "
            "참고자료는 사실 근거로만 쓰고 그대로 복붙하지 마라.]\n" + b[:2500] + "\n")


def interpret_llm(raw_text: str, title_hint: str = "", strict: bool = True, brief: str = "") -> dict:
    """문서를 LLM(로컬 Ollama/GPT)이 읽고 슬라이드 구조로 나눈다. 색·디자인은 넣지 않음."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "ollama", base_url=os.getenv("OPENAI_BASE_URL"))
    doc = raw_text[:6000]  # 로컬 모델 컨텍스트 보호
    prompt = f"""다음 문서를 감바랩스 발표자료 PLAN(JSON)으로 구조화하라. 규칙을 반드시 지켜라.

[규칙]
- title: 문서 전체를 대표하는 제목. subtitle: 한 줄 부제(없으면 "").
- 내용을 논리적 단위로 나눠 본문 슬라이드 5~9개를 만들어라. 각 슬라이드 title은 짧고 명확하게.
- 슬라이드 유형을 골라라: 핵심 항목 2~4개면 "cards"(items에 항목), 설명/목록/근거면 "text"(bullets에 요약), 비교·수치 표면 "table"(rows, 첫 행=헤더).
- bullets/items는 원문 복붙 금지 — 한 항목을 한 줄로 간결히 요약. 마크다운 기호(#,*,`,|) 제거.
- 표지·목차·마무리는 만들지 마라(렌더러가 자동 생성한다).
- 색/폰트/테마는 절대 넣지 마라. 설명 없이 오직 JSON만 출력.
{PLAN_SCHEMA}
{_brief_block(brief)}
[문서]
{doc}"""
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"), temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": "You output only valid JSON. 한국어 내용은 그대로 보존한다."},
                  {"role": "user", "content": prompt}])
    return _normalize_llm(json.loads(resp.choices[0].message.content), title_hint, strict=strict)


def _normalize_llm(plan: dict, title_hint: str = "", strict: bool = True) -> dict:
    """LLM 출력 보정: 제목 폴백·유형 정리·빈 슬라이드 제거. 결과 비면 예외(→규칙 폴백).
    strict=False(freeform)면 모델이 고른 유형을 존중(카드 자동변환 안 함)."""
    if not isinstance(plan, dict):
        plan = {}
    if not (plan.get("title") or "").strip():
        plan["title"] = title_hint or "발표자료"
    plan.setdefault("subtitle", "")
    out = []
    for sl in (plan.get("slides") or []):
        if not isinstance(sl, dict):
            continue
        t = _clean_title(str(sl.get("title") or ""))
        lead = _strip_md(str(sl.get("lead") or "")).strip()
        typ = sl.get("type") if sl.get("type") in ("text", "cards", "table", "content") else "text"
        if typ == "table":
            rows = [[str(c).strip() for c in r] for r in (sl.get("rows") or []) if isinstance(r, (list, tuple)) and r]
            if rows:
                out.append({"type": "table", "title": t, "lead": lead, "rows": rows})
                continue
            typ = "text"  # 행 없으면 텍스트로
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
        res = subprocess.run(["node", RENDERER, plan_path, assets_dir, out_pptx],
                             capture_output=True, text=True, cwd=PROJECT_DIR)
        if res.returncode != 0:
            raise RuntimeError(f"render_deck.js 실패: {res.stderr[-500:]}")
    finally:
        os.unlink(plan_path)
    return out_pptx


if __name__ == "__main__":
    import sys
    doc = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(PROJECT_DIR), "gambalabs_tech_presentation.md")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(PROJECT_DIR, "output", "gambalabs_deck.pptx")
    print("생성:", generate(doc, out))
    print("슬라이드 플랜 미리보기:")
    print(json.dumps(build_plan(doc), ensure_ascii=False, indent=2)[:800])

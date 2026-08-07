# -*- coding: utf-8 -*-
"""Freeform PPT 엔진 — LLM이 pptxgenjs 코드를 직접 생성하여 진정한 자유 설계를 실현.

기존 방식: LLM → JSON Plan(6개 고정 type) → render_deck.js(고정 템플릿) → 항상 같은 PPT
새 방식:   LLM → pptxgenjs 코드(완전 자유) → node 실행 → 매번 다른 PPT

강한 모델(Groq/GPT-4o 등)에서만 사용. 실패 시 기존 렌더러로 자동 폴백.
"""
import os
import re
import json
import tempfile
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(HERE))
DEFAULT_ASSETS = os.path.join(PROJECT_DIR, "ppt-skill", "assets")
SKILL_DIR = os.path.join(PROJECT_DIR, "ppt-skill")

# ── 레퍼런스 코드 & 헬퍼 로드 ──
_SAMPLE_CODE = ""
_sample_path = os.path.join(SKILL_DIR, "examples", "build_samples.js")
if os.path.exists(_sample_path):
    with open(_sample_path, "r", encoding="utf-8") as f:
        _SAMPLE_CODE = f.read()

_HELPERS_CODE = ""
_helpers_path = os.path.join(HERE, "freeform_helpers.js")
if os.path.exists(_helpers_path):
    with open(_helpers_path, "r", encoding="utf-8") as f:
        _HELPERS_CODE = f.read()

# ── 테마 팔레트 (render_deck.js THEMES에서 추출) ──
THEMES = {
    "gamba": {
        "C": {"hero": "123979", "brand": "0038A3", "med": "1970AE", "deepbox": "153C7E",
              "body": "ECECEC", "white": "FFFFFF", "muted": "C9D4E8", "gray": "5A6472",
              "sky": "4E86C6", "teal": "2A9D99", "surface2": "E7ECF3",
              "cardBg": "FFFFFF", "cardInk": "123979"},
        "F": {"title": "맑은 고딕", "body": "맑은 고딕"},
        "useImages": True,
    },
    "light": {
        "C": {"hero": "123979", "brand": "0038A3", "med": "1970AE",
              "body": "F4F6FA", "white": "FFFFFF", "muted": "5A6472", "gray": "5A6472",
              "sky": "4E86C6", "teal": "2A9D99", "surface2": "E9EFF9",
              "cardBg": "FFFFFF", "cardInk": "123979"},
        "F": {"title": "맑은 고딕", "body": "맑은 고딕"},
        "useImages": False,
    },
    "none": {
        "C": {"hero": "222222", "brand": "2456C7", "med": "4A76D6",
              "body": "FFFFFF", "white": "FFFFFF", "muted": "777777", "gray": "666666",
              "sky": "4A76D6", "teal": "2A9D99", "surface2": "F0F0F0",
              "cardBg": "FAFAFA", "cardInk": "222222"},
        "F": {"title": "맑은 고딕", "body": "맑은 고딕"},
        "useImages": False,
    },
}


def _resolve_theme(theme: str = None, theme_config: dict = None) -> dict:
    """테마 설정을 resolve하여 C, F, useImages, assets 경로를 반환."""
    if theme_config and theme_config.get("C"):
        t = theme_config
    else:
        t = THEMES.get(theme or "gamba", THEMES["gamba"])
    C = t.get("C", THEMES["gamba"]["C"])
    info = {
        "C": C,
        "F": t.get("F", THEMES["gamba"]["F"]),
        "useImages": t.get("useImages", True),
    }
    # 표지 색은 따로 전달한다. C.hero는 '글자색'이라 그걸 표지 배경으로 쓰면
    # 글자색을 검정으로 고른 사용자의 표지가 새까맣게 나온다.
    for k in ("coverBg", "coverInk", "coverSub"):
        if t.get(k):
            info[k] = t[k]
    if not info.get("coverBg"):
        info["coverBg"] = C.get("brand") or C.get("hero") or "123979"
    return info


def _build_prompt(doc_text: str, assets_dir: str, theme_info: dict, brief: str = "") -> str:
    """LLM에게 보낼 프롬프트를 조립한다."""
    C = theme_info["C"]
    F = theme_info["F"]
    use_images = theme_info["useImages"]

    # 에셋 경로 정보
    assets_note = f"""[에셋 경로]
const A = (p) => path.join("{assets_dir.replace(chr(92), '/')}", p);
사용 가능한 에셋:
- A("backgrounds/bg_cover.png") — 표지 배경(딥네이비 + 사운드 링)
- A("backgrounds/band.png") — 본문 상단 헤더 밴드(슬레이트→스카이 그라데이션, 1920×170)
- A("logo/logo_white.png") — 흰 로고(네이비 배경용)
- A("logo/logo_color.png") — 컬러 로고(밝은 배경용)
- A("logo/icon_white.png") — 흰 아이콘(밴드 위용)
- A("logo/icon_color.png") — 컬러 아이콘
useImages={use_images} — {"true: 위 이미지 에셋을 적극 사용하라" if use_images else "false: 이미지 에셋 없이 도형만으로 디자인하라"}"""

    brief_block = ""
    if (brief or "").strip():
        brief_block = f"\n[제작자 브리프 — 목적·디렉션·참고자료를 설계에 반영하라]\n{brief[:15000]}\n"

    if use_images:
        design_rules = f"""1. 표지 슬라이드는 반드시 `s.background = {{ path: A("backgrounds/bg_cover.png") }};` 를 적용하고, 텍스트는 흰색(C.white)으로 크고 세련되게 배치하라.
2. 모든 본문 슬라이드(표지 제외)의 상단에는 반드시 헤더 밴드(`s.addImage({{ path: A("backgrounds/band.png"), x: 0, y: 0, w: 13.333, h: 1.05 }});`)를 깔고, 그 위에 슬라이드 대제목을 흰색 텍스트로 수직 중앙(valign:"middle") 정렬해 올려라.
3. 본문 내용은 빈 공간에 그냥 쓰지 말고, 배경색(`C.body`) 위에 하얀색 카드 도형(`s.addShape('roundRect', {{ fill: {{color: "FFFFFF"}}, shadow: ... }})`)을 여러 개 깔고 그 안에 텍스트를 배치하는 '카드 레이아웃'을 적극 활용하라."""
    else:
        design_rules = f"""1. 표지 슬라이드는 준비된 배경 이미지가 없으므로, 테마 색상(C.hero 또는 C.brand)을 이용해 배경(`s.background = {{ color: C.hero }}`)을 깔고 텍스트를 대비되는 색(C.white 등)으로 세련되게 배치하라.
2. 모든 본문 슬라이드 상단에는 이미지 밴드 대신 직접 도형(rect)으로 헤더 영역을 그려라 (예: 높이 1.05의 `C.brand` 또는 `C.med` 색상 사각형). 그 위에 대제목을 올려라.
3. 본문 내용은 빈 공간에 그냥 쓰지 말고, 배경색(`C.body`) 위에 다른 색상(예: C.cardBg 또는 C.white)의 카드 도형을 깔고 그림자를 주어 '카드 레이아웃'을 창조하라."""

    return f"""너는 세계 최고의 발표자료(PPT) 디자이너 겸 pptxgenjs 개발자다.
아래 [문서]를 읽고, **실행 가능한 Node.js pptxgenjs 스크립트**를 작성하여 멋진 발표자료(.pptx)를 생성하라.

[스마트 레이아웃 헬퍼 함수 — 맹탕 텍스트 금지! 반드시 헬퍼를 사용하라]
코드 상단에 최적 폰트 스케일링(fitText) 및 카드 레이아웃 헬퍼가 미리 주입되어 있습니다. 슬라이드를 구성할 때 이 헬퍼 함수들을 적극 활용하여 최고의 디자인 퀄리티를 완성하십시오:

1. **표지 슬라이드**:
   `addCover(prs, "대제목", "부제목", "발표자/회사명", THEME_INFO, ASSETS_DIR);`

2. **본문 슬라이드 기본 구성**:
   ```javascript
   const s = prs.addSlide();
   addHeader(s, "슬라이드 제목", THEME_INFO, ASSETS_DIR);
   ```

3. **본문 콘텐츠 배치 (택 1 이상 조합)**:
   - **카드 그리드 (1~6개 자동 배치)**:
     `addCards(s, [{{ title: "카드제목", body: "내용" }}, {{ title: "특징", items: ["항목1", "항목2"] }}], THEME_INFO);`
   - **수치/스탯 강조 (큰 숫자 + 라벨)**:
     `addStats(s, [{{ num: "90%+", label: "인식률" }}, {{ num: "수백KB", label: "경량화" }}], THEME_INFO);`
   - **2열 비교 카드**:
     `addCompare(s, {{ title: "기존 방식", items: ["단점1", "단점2"] }}, {{ title: "개선 방식", items: ["장점1", "장점2"] }}, THEME_INFO);`

[금지 및 유의사항]
- 본문에 수동 `addText`로 작게 텍스트만 덩그러니 쓰지 마라! 반드시 `addCards`, `addStats`, `addCompare`를 이용해 화면을 알차게 채워라.
- "이 위치에 이미지 삽입" 같은 설명글을 슬라이드에 쓰지 마라.
- 한국어 텍스트는 원문의 의미를 살려 발표용 키워드/문장으로 간결하게 작성하라.

[테마 상수 — 반드시 이 값을 사용하라]
const C = {json.dumps(C, ensure_ascii=False)};
const F = {json.dumps(F, ensure_ascii=False)};

{assets_note}

[pptxgenjs 필수 규칙]
- `prs.layout = "LAYOUT_WIDE"` (13.333 × 7.5 inch) 를 슬라이드 추가 전에 설정
- 도형 타입은 인스턴스(prs)에서 가져오거나 문자열을 사용하라: `prs.ShapeType.rect` 또는 `'roundRect'`. 절대 클래스(`pptxgen.ShapeType`)에서 가져오지 마라(undefined 에러 발생).
- 색은 '#' 없이 6자리: color: "123979". 투명도는 transparency: 0-100
- 그림자 offset ≥ 0. 위쪽 그림자는 angle: 270
- 불릿: bullet: true (리터럴 '•' 금지), 마지막 제외 breakLine: true, 문단 간격은 paraSpaceAfter
- rectRadius는 roundRect에서만 적용 가능
- 그라데이션 채움은 코드로 구현하지 마라! 배경은 테마 단색(color)이나 준비된 에셋을 사용하라.
- 텍스트박스 margin: 0 으로 도형과 정렬
- 금지: 제목 밑줄, 장식용 컬러 바, 텍스트 넘침, 본문 가운데정렬(제목만 가운데)
- 외곽 여백: 좌우 0.7~0.9, 상하 0.4 이상

[레퍼런스 코드 — 이 패턴을 철저히 분석하고 응용하여, 최고급 디자인의 코드를 작성하라]
{_SAMPLE_CODE}
{brief_block}
[문서]
{doc_text[:80000]}

[출력 형식]
오직 실행 가능한 JavaScript 코드만 출력하라. 설명이나 마크다운 코드블록(```) 없이 순수 JS 코드만.
코드의 마지막 줄은 반드시: prs.writeFile({{ fileName: OUTPUT_PATH }}).then((f) => console.log("WROTE", f));
OUTPUT_PATH 변수는 코드 상단에서 process.argv[2]로 받아라.
require("pptxgenjs")와 require("path")를 사용하라.
"""


def _extract_js(response: str) -> str:
    """LLM 응답에서 JavaScript 코드를 추출한다."""
    text = response.strip()
    # 마크다운 코드 블록이 있으면 추출
    m = re.search(r"```(?:javascript|js)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # 코드 블록 없이 순수 코드일 수도 있음
    # pptxgenjs require가 있는지 확인
    if "pptxgenjs" not in text:
        raise ValueError("LLM 응답에 pptxgenjs 코드가 없음")
    return text


def _plan_presentation(doc_text: str, brief: str = "", media_note: str = "") -> dict:
    """1단계: 문서와 브리프를 분석하여 Claude/Gamma급 프리미엄 슬라이드 기획안(JSON)을 작성한다."""
    from src.common.llm_client import get_llm_client_and_model
    client, model_name = get_llm_client_and_model()

    brief_text = f"\n[제작자 브리프]\n{brief}\n" if brief else ""
    brief_text += media_note or ""
    prompt = f"""너는 Claude, Gamma, Beautiful.ai 수준의 최고급 프레젠테이션 수석 디자이너 겸 기획자다.
아래 [문서]를 정독하고, 핵심 메시지와 세부 내용, 수치, 비교, 연도별 추이 데이터를 풍부하고 완성도 높게 슬라이드 기획안(JSON)으로 작성하라.

[기획 원칙 — 맹탕 슬라이드 금지!]
0. 모든 텍스트는 한국어로 쓰되 한자·일본어를 섞지 마라(예: "경량화"를 "軽量化"로 쓰지 말 것).
1. 슬라이드 개수: 내용에 따라 4~8장의 알찬 슬라이드로 구성하라.
2. 카드 내용 충실화: 한두 단어로 성의없이 끝내지 말고, 각 카드마다 명확한 타이틀과 2~3줄의 알찬 설명(또는 2~4개의 세부 불릿 포인트)을 채워라.
3. 적절한 layout_type 선택:
   - "cover": 표지 슬라이드 (title, subtitle, presenter)
   - "cards": 기능/특징/요약 (title, cards: [{{ title, body }}, {{ title, items: ["불릿1", "불릿2"] }}]) (카드 2~6개)
   - "stats": 핵심 수치/스탯 (title, stats: [{{ num: "90%+", label: "상세 설명" }}, {{ num: "수백KB", label: "상세 설명" }}]) (2~4개)
   - "compare": 비교 분석 (title, leftCol: {{ title, items: [...] }}, rightCol: {{ title, items: [...] }})
   - "chart": 수치 그래프 (title, chartData)

[chartData 규격 — 지시한 차트 종류를 반드시 지켜라]
{{"kind":"bar|line|pie|doughnut", "labels":["2023","2024"], "series":[{{"name":"수익","values":[100,200]}}], "trend":true}}
- "원형차트/파이차트로" 지시 → kind:"pie". "도넛" → kind:"doughnut".
  점유율 46%처럼 비율 하나만 주어지면 labels:["당사","기타"], values:[46,54]로 만들어라.
  **비율·점유율을 stats(큰 숫자 카드)로 처리하지 마라. 원형차트로 표시하라는 지시가 있으면 반드시 chart다.**
- "막대그래프/추세선" 지시 → kind:"bar", trend:true. 연도별 데이터를 labels/values로 채워라.
- "임의 수치로 만들라"는 지시가 있을 때만 그럴듯한 값을 생성하라(없으면 지어내지 마라).

[디자인 지시 반영 — 아래 두 필드는 어떤 layout_type에도 붙일 수 있다]
- 그라데이션: "이 영역에 그라데이션", "우->좌 그라데이션" 같은 지시가 있으면
  "gradient": {{"dir":"h","reverse":true,"x":6.7,"y":1.05,"w":6.6,"h":6.45}}
  (dir는 가로 "h"/세로 "v", 우→좌면 reverse:true. 영역을 특정하지 않았으면 x/y/w/h 생략 = 본문 전체)
- 이미지: "배경에 ~이미지 반투명하게", "여기에 ~사진" 지시가 있으면
  "image": {{"query":"영어 스톡 검색 키워드", "mode":"background", "transparency":70}}
  (특정 영역이면 mode 생략하고 x/y/w/h 지정. **query는 반드시 영어 2~4단어.** 한글 금지)
- 지시 문구에 "(지시 영역: x=.. y=.. w=.. h=.. — 원본 슬라이드 AxB in 기준)"이 붙어 있으면
  그 위치가 곧 지시다. 출력은 항상 13.333 x 7.5 in이므로 **가로는 13.333/A, 세로는 7.5/B 를 곱해
  환산한 x/y/w/h를 그 필드에 넣어라.** 본문은 y=1.05부터 시작하니 y가 그보다 작으면 1.05로 올려라.
- 디자인 지시 문구 자체는 카드·불릿 텍스트에 절대 넣지 마라. 위 필드로만 표현하라.
  ("이 영역에 그라데이션 효과", "(아래 사진 추가)", "-> 이거 원형차트로 표시" 등은 텍스트에서 제거)

{brief_text}
[문서]
{doc_text[:80000]}

[출력 형식]
오직 순수한 JSON만 출력하라. 마크다운 코드블록 없이 JSON만.
{{
  "slides": [
    {{ "layout_type": "cover", "title": "대제목", "subtitle": "부제목", "presenter": "발표자" }},
    {{ "layout_type": "cards", "title": "슬라이드 제목", "cards": [ {{ "title": "특징1", "body": "상세 설명 문장" }}, {{ "title": "특징2", "items": ["세부 기능 1", "세부 기능 2"] }} ] }},
    {{ "layout_type": "stats", "title": "핵심 성능 지표", "stats": [ {{ "num": "90%+", "label": "SNR -20dB 소음 환경 인식률" }} ] }},
    {{ "layout_type": "compare", "title": "방식 비교", "leftCol": {{ "title": "기존 방식", "items": ["클라우드 의존", "지연 발생"] }}, "rightCol": {{ "title": "WordSense", "items": ["온디바이스 독립 구동", "Zero Latency"] }} }},
    {{ "layout_type": "chart", "title": "연도별 수익 추이", "chartData": {{ "kind": "bar", "trend": true, "labels": ["2023년", "2024년", "2025년", "2026년"], "series": [ {{ "name": "매출액", "values": [100, 180, 260, 320] }} ] }} }},
    {{ "layout_type": "chart", "title": "국내 시장 점유율", "chartData": {{ "kind": "pie", "labels": ["당사", "기타"], "series": [ {{ "name": "점유율", "values": [46, 54] }} ] }} }}
  ]
}}
"""

    resp = client.chat.completions.create(
        model=model_name,
        temperature=0.3,
        messages=[
            {"role": "system", "content": "You are a professional PPT content planner. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ]
    )

    text = resp.choices[0].message.content.strip()
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    try:
        plan = json.loads(text)
        if isinstance(plan, dict) and "slides" in plan and len(plan["slides"]) > 0:
            return plan
    except Exception as e:
        print(f"[freeform_engine] 기획안 JSON 파싱 경고, 기본 구조 생성: {e}")

    return {
        "slides": [
            {"layout_type": "cover", "title": "발표 자료", "subtitle": brief or "문서 요약", "presenter": "감바랩스"},
            {"layout_type": "cards", "title": "주요 내용", "cards": [{"title": "요약", "body": doc_text[:300]}]}
        ]
    }


def _resolve_media(plan: dict, theme_info: dict, user_images: dict = None) -> dict:
    """기획안의 image/gradient 지시를 실제 파일 경로로 바꾼다.

    - image.src(사용자가 러프 PPT에 넣어둔 실제 사진)가 있으면 그걸 그대로 쓴다.
      스톡 검색으로 대체하지 않는다 — 사용자가 고른 사진이 사라지는 게 가장 큰 불만이었다.
    - image.query만 있으면 스톡에서 받아온다.
    - gradient는 gradient.py로 PNG를 만들어 그 경로를 넘긴다(pptxgenjs 그라데이션 채움은 불안정).
    """
    from app.ppt import image_search
    from app.ppt import gradient as _grad

    C = theme_info.get("C", {}) or {}
    user_images = user_images or {}

    slides = plan.get("slides", [])
    # 모델이 슬라이드를 합치거나 쪼갤 수 있으므로, 사진은 모델이 지목한 입력 슬라이드 번호
    # (userImage)로 붙인다. 아무도 지목하지 않은 사진은 남은 슬라이드에 순서대로 배정한다.
    unclaimed = {int(k): list(v) for k, v in user_images.items() if v}
    for sl in slides:
        try:
            n = int(sl.get("userImage"))
        except (TypeError, ValueError):
            continue
        if unclaimed.get(n):
            img = sl.get("image") if isinstance(sl.get("image"), dict) else {}
            img["src"] = unclaimed[n].pop(0)
            sl["image"] = img
    leftovers = [p for n in sorted(unclaimed) for p in unclaimed[n]]
    if leftovers:
        for sl in slides[1:]:                       # 표지는 건너뛴다
            if not leftovers:
                break
            if not (isinstance(sl.get("image"), dict) and sl["image"].get("src")):
                img = sl.get("image") if isinstance(sl.get("image"), dict) else {}
                img["src"] = leftovers.pop(0)
                sl["image"] = img

    for sl in slides:

        img = sl.get("image")
        if isinstance(img, dict):
            src = img.get("src")
            if src and os.path.exists(src):
                img["path"] = src
            elif img.get("query"):
                try:
                    p = image_search.fetch_image(img["query"])
                    if p:
                        img["path"] = p
                except Exception as e:
                    print(f"[freeform_engine] 이미지 검색 실패({img.get('query')}): {e}")
            if not img.get("path"):
                sl.pop("image", None)   # 자리표시자를 남기지 않는다

        g = sl.get("gradient")
        if isinstance(g, dict):
            c1 = g.get("from") or C.get("brand") or "0038A3"
            c2 = g.get("to") or C.get("body") or "ECECEC"
            try:
                g["path"] = _grad.gradient_png("#" + str(c1).lstrip("#"), "#" + str(c2).lstrip("#"),
                                               direction=g.get("dir", "h"),
                                               reverse=bool(g.get("reverse")))
            except Exception as e:
                print(f"[freeform_engine] 그라데이션 생성 실패: {e}")
                sl.pop("gradient", None)
    return plan


def _decor_js(sl: dict) -> str:
    """슬라이드의 그라데이션·이미지 코드. 카드보다 먼저 깔려야 뒤에 남는다.

    쌓는 순서: 배경 이미지 → 그라데이션 패널 → 영역 이미지.
    (그라데이션을 배경 이미지보다 먼저 깔면 이미지에 완전히 가려 보이지 않는다)
    """
    g = sl.get("gradient")
    img = sl.get("image")
    has_g = isinstance(g, dict) and g.get("path")
    has_i = isinstance(img, dict) and img.get("path")

    def gradient_line():
        rect = {k: g[k] for k in ("x", "y", "w", "h") if k in g}
        # 배경 이미지 위에 전면 그라데이션을 덮으면 이미지가 사라진다 → 영역 지정이 없으면 우측 패널로
        if not rect and has_i and img.get("mode") == "background":
            rect = {"x": 6.9, "y": 1.05, "w": 6.43, "h": 6.45}
        return f"addGradientPanel(s, {json.dumps(g['path'], ensure_ascii=False)}, {json.dumps(rect)});"

    def image_line():
        opts = {k: img[k] for k in ("mode", "transparency", "x", "y", "w", "h") if k in img}
        return f"addSlideImage(s, {json.dumps(img['path'], ensure_ascii=False)}, {json.dumps(opts, ensure_ascii=False)});"

    out = []
    if has_i and img.get("mode") == "background":
        out.append(image_line())
        if has_g:
            out.append(gradient_line())
    else:
        if has_g:
            out.append(gradient_line())
        if has_i:
            out.append(image_line())
    return " ".join(out)


def _convert_plan_to_js(plan: dict) -> str:
    """2단계: 기획안(JSON)을 레이아웃 헬퍼 기반 실행 가능 Node.js 스크립트로 변환한다."""
    lines = []
    for slide in plan.get("slides", []):
        stype = slide.get("layout_type") or slide.get("type") or "cards"
        title = json.dumps(slide.get("title", ""), ensure_ascii=False)
        if stype == "cover":
            sub = json.dumps(slide.get("subtitle", ""), ensure_ascii=False)
            pres = json.dumps(slide.get("presenter", ""), ensure_ascii=False)
            lines.append(f"addCover(prs, {title}, {sub}, {pres}, THEME_INFO, ASSETS_DIR);")
            continue

        head = f"var s = prs.addSlide(); addHeader(s, {title}, THEME_INFO, ASSETS_DIR);"
        decor = _decor_js(slide)          # 그라데이션·이미지는 콘텐츠보다 먼저
        img = slide.get("image") or {}
        side = isinstance(img, dict) and img.get("path") and img.get("mode") != "background"

        if stype == "stats":
            body = f"addStats(s, {json.dumps(slide.get('stats', []), ensure_ascii=False)}, THEME_INFO);"
        elif stype == "compare":
            body = (f"addCompare(s, {json.dumps(slide.get('leftCol', {}), ensure_ascii=False)}, "
                    f"{json.dumps(slide.get('rightCol', {}), ensure_ascii=False)}, THEME_INFO);")
        elif stype == "chart":
            # 곁에 이미지가 있으면 차트를 왼쪽 절반으로 좁힌다
            rect = {"x": 0.8, "y": 1.6, "w": 5.9, "h": 4.8} if side else {}
            body = (f"addChart(s, {title}, {json.dumps(slide.get('chartData', {}), ensure_ascii=False)}, "
                    f"THEME_INFO, prs, {json.dumps(rect)});")
        else:
            body = f"addCards(s, {json.dumps(slide.get('cards', []), ensure_ascii=False)}, THEME_INFO);"

        lines.append(" ".join(x for x in (head, decor, body) if x))
    lines.append("prs.writeFile({ fileName: process.argv[2] });")
    return "\n".join(lines)


def generate_freeform(doc_text: str, out_pptx: str, assets_dir: str = DEFAULT_ASSETS,
                      theme: str = None, theme_config: dict = None, brief: str = "",
                      user_images: dict = None) -> str:
    """LLM 2단계 생성 (1단계: 문서 분석 & 슬라이드 기획 -> 2단계: 헬퍼 기반 JS 실행).

    user_images: {입력 슬라이드 번호: [이미지 경로, ...]} — 러프 PPT에 사용자가 직접 넣은 사진.
    """
    theme_info = _resolve_theme(theme, theme_config)

    media_note = ""
    if user_images:
        listing = "\n".join(f"- 입력 슬라이드 {k}: 사진 {len(v)}장" for k, v in sorted(user_images.items()))
        media_note = ("\n[사용자가 직접 넣은 사진 — 스톡 이미지로 대체하지 말고 반드시 그대로 쓴다]\n"
                      f"{listing}\n"
                      "그 내용에 해당하는 출력 슬라이드에 \"userImage\": <입력 슬라이드 번호> 를 넣어라.\n"
                      "그 슬라이드는 사진 자리를 남기도록 카드를 1~2개로 줄이고, "
                      "\"(아래 사진 추가)\" 같은 설명 문구는 텍스트에서 빼라. 배치는 시스템이 한다.\n")

    print(f"[freeform_engine] 1단계: 문서 분석 및 슬라이드 기획 중…")
    plan = _plan_presentation(doc_text, brief, media_note)
    print(f"[freeform_engine] 기획 완료: 총 {len(plan.get('slides', []))}개 슬라이드")

    # 이미지·그라데이션 지시를 실제 파일로 해결
    plan = _resolve_media(plan, theme_info, user_images)

    print(f"[freeform_engine] 2단계: pptxgenjs 코드 생성 및 렌더링 중…")
    js_content = _convert_plan_to_js(plan)

    os.makedirs(os.path.dirname(os.path.abspath(out_pptx)), exist_ok=True)

    assets_clean = assets_dir.replace('\\', '/')
    theme_json = json.dumps(theme_info, ensure_ascii=False)
    
    header_inject = f"""
var path = require("path");
var pptxgen = require("pptxgenjs");
var THEME_INFO = {theme_json};
var ASSETS_DIR = "{assets_clean}";
var A = function(p) {{ return path.resolve(ASSETS_DIR, p); }};
{_HELPERS_CODE}
var prs = new pptxgen();
prs.layout = "LAYOUT_WIDE";
"""
    full_js = header_inject + "\n" + js_content

    tmp_dir = os.path.join(PROJECT_DIR, "output", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".js", dir=tmp_dir, delete=False, encoding="utf-8") as tf:
        tf.write(full_js)
        js_path = tf.name

    try:
        res = subprocess.run(
            ["node", js_path, out_pptx],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=60
        )
        if res.returncode != 0:
            err_msg = (res.stderr or "")[-800:]
            raise RuntimeError(f"pptxgenjs 코드 실행 실패:\n{err_msg}")
        if not os.path.exists(out_pptx):
            raise RuntimeError("pptxgenjs 코드가 .pptx 파일을 생성하지 않음")
        print(f"[freeform_engine] 생성 완료: {out_pptx}")
        return out_pptx
    finally:
        try:
            os.unlink(js_path)
        except OSError:
            pass


def generate_freeform_from_file(doc_path: str, out_pptx: str, assets_dir: str = DEFAULT_ASSETS,
                                theme: str = None, theme_config: dict = None, brief: str = "") -> str:
    """파일 경로에서 문서를 읽어 freeform 생성."""
    with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
        doc_text = f.read()
    return generate_freeform(doc_text, out_pptx, assets_dir, theme, theme_config, brief)


def generate_freeform_from_slides(slides_text: str, out_pptx: str, assets_dir: str = DEFAULT_ASSETS,
                                  theme: str = None, theme_config: dict = None, brief: str = "",
                                  user_images: dict = None) -> str:
    """PPT 가져오기: 추출된 슬라이드 텍스트(+사용자 사진)로 freeform 생성."""
    return generate_freeform(slides_text, out_pptx, assets_dir, theme, theme_config, brief, user_images)

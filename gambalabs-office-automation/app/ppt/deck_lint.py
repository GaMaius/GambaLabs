# -*- coding: utf-8 -*-
"""생성된 덱의 기하학적 결함을 코드로 잡아낸다.

모델이 쓴 pptxgenjs 코드는 '실행은 되는데 보기엔 엉망'인 경우가 많다.
사람이 스크린샷을 보내주기 전에 스스로 걸러내기 위한 검사기.
지적 사항은 문자열 목록으로 돌려주고, 그대로 모델에게 재수정 지시로 넘긴다.
"""
from typing import List

W_IN, H_IN = 13.333, 7.5
EMU = 914400.0


def _rects(slide):
    out = []
    for sh in slide.shapes:
        if sh.left is None or sh.top is None or sh.width is None or sh.height is None:
            continue
        kind = "pic" if (sh.shape_type == 13 or sh.__class__.__name__ == "Picture") else "shape"
        txt = ""
        try:
            if sh.has_text_frame:
                txt = sh.text_frame.text.strip()
                if txt:
                    kind = "text"
        except Exception:
            pass
        out.append({
            "kind": kind, "text": txt,
            "x": sh.left / EMU, "y": sh.top / EMU,
            "w": sh.width / EMU, "h": sh.height / EMU,
        })
    return out


def _overlap(a, b):
    ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    if ox <= 0 or oy <= 0:
        return 0.0
    return ox * oy


def _has_chart(slide) -> bool:
    for sh in slide.shapes:
        if getattr(sh, "has_chart", False):
            return True
    return False


def _has_picture(slide) -> bool:
    for sh in slide.shapes:
        if sh.shape_type == 13 or sh.__class__.__name__ == "Picture":
            return True
    return False


def lint(pptx_path: str, expect: dict = None) -> List[str]:
    """expect = {"n_slides":6, "charts":[4,5], "images":[3], "cover":True}

    기하 결함뿐 아니라 '기획안대로 만들어졌는지'까지 본다. 이게 없으면 모델이
    차트를 회색 네모+숫자로 그려 놓고도 검사를 통과한다(실제로 그랬다).
    """
    from pptx import Presentation
    prs = Presentation(pptx_path)
    problems = []
    expect = expect or {}

    if len(prs.slides) == 0:
        return ["슬라이드가 하나도 없다."]

    n_exp = expect.get("n_slides")
    if n_exp and len(prs.slides) != n_exp:
        problems.append(f"슬라이드 수가 기획안과 다르다(기획 {n_exp}장, 생성 {len(prs.slides)}장).")

    for idx in expect.get("charts", []):
        if idx <= len(prs.slides) and not _has_chart(prs.slides[idx - 1]):
            problems.append(
                f"슬라이드 {idx}: 차트 슬라이드인데 실제 차트가 없다. "
                f"도형과 숫자로 흉내 내지 말고 addChart(s, 제목, chartData, THEME_INFO, prs, rect)를 호출하라.")

    for idx in expect.get("images", []):
        if idx <= len(prs.slides) and not _has_picture(prs.slides[idx - 1]):
            problems.append(f"슬라이드 {idx}: 배치해야 할 사진(IMG[{idx}])이 없다. addSlideImage로 넣어라.")

    for i, s in enumerate(prs.slides, 1):
        rs = _rects(s)
        if not rs:
            problems.append(f"슬라이드 {i}: 아무 요소도 없다.")
            continue

        # 1) 슬라이드 밖으로 나간 요소
        for r in rs:
            if r["x"] < -0.05 or r["y"] < -0.05 or \
               r["x"] + r["w"] > W_IN + 0.05 or r["y"] + r["h"] > H_IN + 0.05:
                label = (r["text"][:18] + "…") if r["text"] else r["kind"]
                problems.append(
                    f"슬라이드 {i}: '{label}'이(가) 슬라이드 밖으로 나감 "
                    f"(x={r['x']:.2f} y={r['y']:.2f} w={r['w']:.2f} h={r['h']:.2f}, 화면은 {W_IN}x{H_IN})")

        # 2) 사진이 다른 요소에 가려짐 (배경으로 깔린 전면 이미지는 제외)
        pics = [r for r in rs if r["kind"] == "pic" and r["w"] * r["h"] > 0.5
                and not (r["w"] > W_IN * 0.9 and r["h"] > (H_IN - 1.05) * 0.9)]
        for p_i, p in enumerate(pics):
            area = p["w"] * p["h"]
            covered = 0.0
            for r in rs[rs.index(p) + 1:]:      # 뒤에 그려진 것 = 위에 덮이는 것
                if r["kind"] == "pic":
                    continue
                covered += _overlap(p, r)
            if area and covered / area > 0.35:
                problems.append(
                    f"슬라이드 {i}: 사진이 카드/도형에 {covered / area * 100:.0f}% 가려졌다. "
                    f"사진 자리(x={p['x']:.2f} y={p['y']:.2f} w={p['w']:.2f} h={p['h']:.2f})를 비워라.")

        # 3) 본문 요소끼리 심하게 겹침
        body = [r for r in rs if r["y"] > 1.1 and r["kind"] != "pic"]
        for a_i in range(len(body)):
            for b_i in range(a_i + 1, len(body)):
                a, b = body[a_i], body[b_i]
                ov = _overlap(a, b)
                small = min(a["w"] * a["h"], b["w"] * b["h"])
                # 카드 위의 텍스트는 정상적인 포함 관계 → 완전히 감싸는 경우는 제외
                inside = (a["x"] <= b["x"] and a["y"] <= b["y"] and
                          a["x"] + a["w"] >= b["x"] + b["w"] and a["y"] + a["h"] >= b["y"] + b["h"]) or \
                         (b["x"] <= a["x"] and b["y"] <= a["y"] and
                          b["x"] + b["w"] >= a["x"] + a["w"] and b["y"] + b["h"] >= a["y"] + a["h"])
                if not inside and small and ov / small > 0.4:
                    la = (a["text"][:14] or a["kind"]); lb = (b["text"][:14] or b["kind"])
                    problems.append(f"슬라이드 {i}: '{la}'와 '{lb}'가 서로 겹친다.")

        # 4) 본문이 거의 비어 있음
        used = sum(r["w"] * r["h"] for r in rs if r["y"] > 1.1)
        if used < (W_IN * (H_IN - 1.05)) * 0.15:
            problems.append(f"슬라이드 {i}: 본문이 거의 비어 있다. 내용을 채우거나 배치를 키워라.")

        # 5) 상단 헤더 영역이 비었다(표지 제외) — 제목 없는 맨 슬라이드 방지
        if i > 1 or not expect.get("cover", True):
            if not any(r["y"] < 1.1 and r["w"] > 3 for r in rs):
                problems.append(
                    f"슬라이드 {i}: 상단 헤더(제목 밴드)가 없다. "
                    f"addHeader(s, 제목, THEME_INFO, ASSETS_DIR)를 먼저 호출하라.")

        # 6) 표지가 비었다
        if i == 1 and expect.get("cover", True):
            if len([r for r in rs if r["kind"] == "text"]) == 0:
                problems.append("슬라이드 1(표지)에 제목이 없다. addCover(prs, 제목, 부제, 발표자, THEME_INFO, ASSETS_DIR)를 쓰라.")

    # 중복 제거(같은 지적이 반복되면 프롬프트만 길어진다)
    seen, out = set(), []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:20]

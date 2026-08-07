# -*- coding: utf-8 -*-
"""저작권 안전한 스톡 이미지 검색·다운로드 (생성 아님).

지시 '[이미지: 설명]'의 설명을 질의로 스톡 서비스에서 검색해 1장 내려받는다.
우선순위: Unsplash → Pexels(키 있을 때) → Openverse(키 불필요·CC 상업적 사용 가능).
Openverse 덕분에 키가 없어도 실제 이미지가 들어간다. 모두 실패하면 None → 플레이스홀더.

주의: 검색어(예: 'AI 음성인식')만 외부로 나가며, 기밀 문서 내용은 전송하지 않는다.

환경변수(선택): UNSPLASH_ACCESS_KEY  또는  PEXELS_API_KEY (있으면 화질↑·한도↑)
"""
import os
import re
import hashlib

from src.common import paths

CACHE = os.path.join(paths.CACHE_DIR, "stock")


def _download(url, query):
    import requests
    os.makedirs(CACHE, exist_ok=True)
    name = re.sub(r"[^\w]+", "_", query)[:30] + "_" + hashlib.md5(url.encode()).hexdigest()[:8] + ".jpg"
    path = os.path.join(CACHE, name)
    if os.path.exists(path):
        return path
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    return path


_QCACHE = {}


def _english_query(q: str) -> str:
    """스톡 API는 영어 기반 → 한글 질의를 영어 키워드로 번역(LLM, 캐시). 실패 시 원문."""
    q = (q or "").strip()
    if not q or not re.search(r"[가-힣]", q):
        return q
    if q in _QCACHE:
        return _QCACHE[q]
    eng = q
    try:
        # 통합 팩토리를 쓴다. 예전엔 OPENAI_* 를 직접 읽어 로컬 Ollama로 붙었고,
        # Ollama가 안 떠 있으면 조용히 실패해 한글 질의가 그대로 스톡 검색에 나갔다.
        from src.common.llm_client import get_llm_client_and_model
        c, model = get_llm_client_and_model()
        r = c.chat.completions.create(
            model=model, temperature=0,
            messages=[{"role": "user", "content":
                       "Convert to 2-4 concise English stock-photo search keywords. "
                       f"Output ONLY the keywords, nothing else.\n\n{q}"}])
        cand = re.sub(r"\s+", " ", (r.choices[0].message.content or "").strip().strip('".')).strip()
        if cand:
            eng = cand[:60]
    except Exception as e:
        print(f"[image_search] 검색어 번역 실패({e}) → 원문 사용")
    _QCACHE[q] = eng
    return eng


def _search_urls(query: str, n: int = 6):
    """후보 사진 URL을 여러 개. 우선순위 Unsplash→Pexels→Openverse."""
    import requests
    uk, pk = os.getenv("UNSPLASH_ACCESS_KEY"), os.getenv("PEXELS_API_KEY")
    try:
        if uk:
            r = requests.get("https://api.unsplash.com/search/photos",
                             params={"query": query, "per_page": max(n, 12), "orientation": "landscape",
                                     "order_by": "relevant", "content_filter": "high"},
                             headers={"Authorization": f"Client-ID {uk}"}, timeout=20)
            r.raise_for_status()
            res = r.json().get("results", [])
            if res:
                return [x["urls"]["regular"] for x in res[:n]]
        elif pk:
            r = requests.get("https://api.pexels.com/v1/search",
                             params={"query": query, "per_page": max(n, 15), "orientation": "landscape",
                                     "size": "large"},
                             headers={"Authorization": pk}, timeout=20)
            r.raise_for_status()
            ph = r.json().get("photos", [])
            ph = [p for p in ph if p.get("width", 0) >= p.get("height", 1)] or ph
            if ph:
                return [(p["src"].get("large2x") or p["src"]["large"]) for p in ph[:n]]
    except Exception as e:
        print(f"[image_search] 키 기반 검색 실패({e}) → Openverse")
    try:  # 폴백: Openverse (키 불필요, CC 상업적 사용)
        r = requests.get("https://api.openverse.org/v1/images/",
                         params={"q": query, "page_size": max(n, 8), "license_type": "commercial",
                                 "aspect_ratio": "wide", "size": "large"},
                         headers={"User-Agent": "GambaLabsOfficeAI/1.0"}, timeout=20)
        r.raise_for_status()
        res = r.json().get("results", [])
        return [(x.get("url") or x.get("thumbnail")) for x in res[:n] if (x.get("url") or x.get("thumbnail"))]
    except Exception as e:
        print(f"[image_search] Openverse 실패({e})")
    return []


def _search_url(query: str):
    """구버전 호환 — 후보 중 첫 번째."""
    u = _search_urls(query, 1)
    return u[0] if u else None


def _busyness(path: str):
    """배경용 적합도: 낮을수록 차분하다.

    글자·UI 스크린샷처럼 잔 디테일이 많은 사진을 배경에 깔면 그 위 카드 글자가 안 읽힌다.
    엣지 밀도(잔 디테일)와 밝기 분산을 섞어 점수를 낸다. 계산 불가면 None.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((480, 480))
        g = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(g, 80, 160)
        edge_density = float(np.count_nonzero(edges)) / max(g.size, 1)
        contrast = float(np.std(g)) / 128.0
        return edge_density * 3.0 + contrast * 0.5
    except Exception:
        return None


# 배경으로 깔 이미지에 덧붙이는 힌트. 인물·UI 스크린샷 대신 차분한 질감이 잡히게 한다.
_BG_HINT = "abstract soft blurred texture background"


def fetch_image(query: str, mode: str = "region"):
    """질의 → 영어 번역 → 스톡 검색·다운로드 → 사진 경로. 실패 시 None.

    mode="background"면 배경용으로 고른다: 질의에 추상·질감 힌트를 붙이고,
    후보를 여러 장 받아 **가장 차분한(잔 디테일이 적은)** 한 장을 고른다.
    글자 많은 UI 스크린샷이 배경에 깔려 카드 글자를 못 읽게 되던 문제를 막는다.
    (PPT 삽입용 사진은 원본 그대로 — 자동 SVG 변환은 하지 않는다.)
    """
    if not query:
        return None
    eng = _english_query(query)
    if mode == "background":
        eng_q = f"{eng} {_BG_HINT}"
        urls = _search_urls(eng_q, 5) or _search_urls(eng, 5)
        best, best_score = None, None
        for u in urls[:5]:
            try:
                p = _download(u, eng_q)
            except Exception:
                continue
            sc = _busyness(p)
            if sc is None:
                return p                     # 점수를 못 내면 첫 장으로
            if best_score is None or sc < best_score:
                best, best_score = p, sc
        if best:
            print(f"[image_search] 배경 이미지 선택(차분함 점수 {best_score:.3f}): {os.path.basename(best)}")
        return best
    url = _search_url(eng)
    if not url:
        return None
    return _download(url, eng)


def available():
    # Openverse 폴백이 있어 키 없어도 검색 가능
    return True


def source_label():
    if os.getenv("UNSPLASH_ACCESS_KEY"):
        return "스톡 ON · Unsplash"
    if os.getenv("PEXELS_API_KEY"):
        return "스톡 ON · Pexels"
    return "스톡 ON · Openverse(키없음)"

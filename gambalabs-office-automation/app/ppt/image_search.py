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

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output", "_images")


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
    if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL"):
        try:
            from openai import OpenAI
            c = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "ollama",
                       base_url=os.getenv("OPENAI_BASE_URL"), timeout=25)
            r = c.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"), temperature=0,
                messages=[{"role": "user", "content":
                           "Convert to 2-4 concise English stock-photo search keywords. "
                           f"Output ONLY the keywords, nothing else.\n\n{q}"}])
            cand = re.sub(r"\s+", " ", r.choices[0].message.content.strip().strip('".')).strip()
            if cand:
                eng = cand[:60]
        except Exception:
            pass
    _QCACHE[q] = eng
    return eng


def _search_url(query: str):
    """스톡 서비스에서 가로·고화질 사진 URL 1개. 우선순위 Unsplash→Pexels→Openverse."""
    import requests
    uk, pk = os.getenv("UNSPLASH_ACCESS_KEY"), os.getenv("PEXELS_API_KEY")
    try:
        if uk:
            r = requests.get("https://api.unsplash.com/search/photos",
                             params={"query": query, "per_page": 12, "orientation": "landscape",
                                     "order_by": "relevant", "content_filter": "high"},
                             headers={"Authorization": f"Client-ID {uk}"}, timeout=20)
            r.raise_for_status()
            res = r.json().get("results", [])
            if res:
                return res[0]["urls"]["regular"]
        elif pk:
            r = requests.get("https://api.pexels.com/v1/search",
                             params={"query": query, "per_page": 15, "orientation": "landscape",
                                     "size": "large"},
                             headers={"Authorization": pk}, timeout=20)
            r.raise_for_status()
            ph = r.json().get("photos", [])
            if ph:  # 가로 비율 우선(관련도 상위 중)
                ph.sort(key=lambda p: 0 if p.get("width", 0) >= p.get("height", 1) else 1)
                return ph[0]["src"].get("large2x") or ph[0]["src"]["large"]
    except Exception as e:
        print(f"[image_search] 키 기반 검색 실패({e}) → Openverse")
    try:  # 폴백: Openverse (키 불필요, CC 상업적 사용)
        r = requests.get("https://api.openverse.org/v1/images/",
                         params={"q": query, "page_size": 8, "license_type": "commercial",
                                 "aspect_ratio": "wide", "size": "large"},
                         headers={"User-Agent": "GambaLabsOfficeAI/1.0"}, timeout=20)
        r.raise_for_status()
        res = r.json().get("results", [])
        if res:
            return res[0].get("url") or res[0].get("thumbnail")
    except Exception as e:
        print(f"[image_search] Openverse 실패({e})")
    return None


def fetch_image(query: str):
    """질의 → 영어 번역 → 스톡 검색·다운로드 → 원본 사진 경로. 실패 시 None.
    (PPT 삽입용 사진은 원본 그대로 — 자동 SVG 변환은 하지 않음. 벡터화는 '벡터 변환' 탭에서 수동으로.)"""
    if not query:
        return None
    eng = _english_query(query)
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

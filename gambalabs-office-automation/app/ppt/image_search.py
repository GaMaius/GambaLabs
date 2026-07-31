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


def fetch_image(query: str):
    """질의로 스톡 이미지 1장 검색·다운로드 → 로컬 경로. 실패/미설정 시 None."""
    if not query:
        return None
    import requests
    uk = os.getenv("UNSPLASH_ACCESS_KEY")
    pk = os.getenv("PEXELS_API_KEY")
    try:
        if uk:
            r = requests.get("https://api.unsplash.com/search/photos",
                             params={"query": query, "per_page": 1, "orientation": "landscape"},
                             headers={"Authorization": f"Client-ID {uk}"}, timeout=20)
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                return _download(results[0]["urls"]["regular"], query)
        elif pk:
            r = requests.get("https://api.pexels.com/v1/search",
                             params={"query": query, "per_page": 1, "orientation": "landscape"},
                             headers={"Authorization": pk}, timeout=20)
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if photos:
                return _download(photos[0]["src"]["large"], query)
    except Exception as e:
        print(f"[image_search] 키 기반 검색 실패({e}) → Openverse 시도")
    # 폴백: Openverse (키 불필요, CC·상업적 사용 가능)
    try:
        r = requests.get("https://api.openverse.org/v1/images/",
                         params={"q": query, "page_size": 1, "license_type": "commercial"},
                         headers={"User-Agent": "GambaLabsOfficeAI/1.0"}, timeout=20)
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return _download(results[0].get("url") or results[0].get("thumbnail"), query)
    except Exception as e:
        print(f"[image_search] Openverse 실패({e}) → 플레이스홀더")
    return None


def available():
    # Openverse 폴백이 있어 키 없어도 검색 가능
    return True


def source_label():
    if os.getenv("UNSPLASH_ACCESS_KEY"):
        return "스톡 ON · Unsplash"
    if os.getenv("PEXELS_API_KEY"):
        return "스톡 ON · Pexels"
    return "스톡 ON · Openverse(키없음)"

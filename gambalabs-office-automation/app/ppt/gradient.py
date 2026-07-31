# -*- coding: utf-8 -*-
"""그라데이션 배경 PNG 생성 (pptxgenjs가 그라데이션 채움을 지원 안 해 이미지로 대체).

render_plan이 slide.gradient={"colors":["A","B"],"dir":"h|v","reverse":bool}를 만나면
여기서 PNG를 생성(파라미터별 캐시)하고 그 경로를 slide.gradientPath에 넣어 렌더러에 넘긴다.
"""
import os
import hashlib

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_gradcache")


def _rgb(h):
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        h = "123979"
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient_png(c1: str, c2: str, direction: str = "h", reverse: bool = False,
                 w: int = 1280, h: int = 720) -> str:
    """c1→c2 선형 그라데이션 PNG 경로 반환. 한 축만 채워 리사이즈(빠름)."""
    from PIL import Image
    key = hashlib.md5(f"{c1}{c2}{direction}{reverse}{w}{h}".encode()).hexdigest()[:12]
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"grad_{key}.png")
    if os.path.exists(path):
        return path
    a, b = _rgb(c1), _rgb(c2)
    if reverse:
        a, b = b, a
    horizontal = direction not in ("v", "vertical", "tb", "bt")
    n = w if horizontal else h
    strip = Image.new("RGB", (w, 1) if horizontal else (1, h))
    px = strip.load()
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0
        col = (int(a[0] + (b[0] - a[0]) * t),
               int(a[1] + (b[1] - a[1]) * t),
               int(a[2] + (b[2] - a[2]) * t))
        if horizontal:
            px[i, 0] = col
        else:
            px[0, i] = col
    strip.resize((w, h)).save(path)
    return path

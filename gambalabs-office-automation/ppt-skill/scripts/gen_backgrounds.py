# -*- coding: utf-8 -*-
"""테마 규격대로 그라데이션 배경 PNG 생성.
사용: python assets/gen_backgrounds.py
- bg_cover.png : 딥네이비 방사형(중심 62%,42%) + 은은한 사운드 링(중심 60%,55%)
- band.png     : 헤더 밴드 가로 그라데이션(좌 3D6EA2 → 우 60A4C8)
"""
import os
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "backgrounds")
os.makedirs(OUT, exist_ok=True)


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_cover(w=1920, h=1080):
    base = hex2rgb("123979")   # 히어로 네이비
    edge = hex2rgb("0B2656")   # 모서리 어두운 네이비
    cx, cy = 0.62 * w, 0.42 * h
    maxd = max((cx ** 2 + cy ** 2) ** 0.5,
               ((w - cx) ** 2 + cy ** 2) ** 0.5,
               (cx ** 2 + (h - cy) ** 2) ** 0.5,
               ((w - cx) ** 2 + (h - cy) ** 2) ** 0.5)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / maxd
            px[x, y] = lerp(base, edge, d ** 1.15)
    # 사운드 링(동심원) — 옅게, 블러
    ring = Image.new("L", (w, h), 0)
    rd = ImageDraw.Draw(ring)
    rcx, rcy = 0.60 * w, 0.55 * h
    r = 120
    while r <= 900:
        rd.ellipse([rcx - r, rcy - r, rcx + r, rcy + r], outline=22, width=3)
        r += 70
    ring = ring.filter(ImageFilter.GaussianBlur(2))
    tint = Image.new("RGB", (w, h), hex2rgb("78A0DC"))
    img = Image.composite(tint, img, ring)
    img.save(os.path.join(OUT, "bg_cover.png"))
    print("wrote bg_cover.png")


def make_band(w=1920, h=170):
    left = hex2rgb("3D6EA2")
    right = hex2rgb("60A4C8")
    img = Image.new("RGB", (w, h))
    px = img.load()
    for x in range(w):
        c = lerp(left, right, x / (w - 1))
        for y in range(h):
            px[x, y] = c
    img.save(os.path.join(OUT, "band.png"))
    print("wrote band.png")


if __name__ == "__main__":
    make_cover()
    make_band()
    print("done")

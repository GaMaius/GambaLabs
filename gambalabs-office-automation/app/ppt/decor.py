# -*- coding: utf-8 -*-
"""슬라이드 배경 장식(그라데이션 + 사진)을 **한 장의 PNG로 미리 합성**한다.

왜 합성하나: 예전에는 그라데이션 패널과 배경 사진을 각각 따로 슬라이드에 얹었다.
pptxgenjs는 z-order가 곧 호출 순서라, 모델이 그라데이션을 먼저 깔고 전면 배경 사진을
나중에 얹으면 그라데이션이 통째로 사라졌다(실제 산출물에서 확인). 순서를 지키라고
프롬프트로 부탁하는 대신, 애초에 한 장으로 합쳐 순서를 틀릴 수 없게 만든다.

합성 결과는 본문 영역(헤더 아래 전체)을 덮는 이미지 한 장이고, 반투명 처리는
테마 배경색 위에 미리 섞어 굽는다. 렌더러는 그냥 얹기만 하면 된다.
"""
import os
import hashlib

from src.common import paths

CACHE = os.path.join(paths.CACHE_DIR, "decor")

HEADER_H = 1.05          # freeform_helpers.js 의 HEADER_H 와 같아야 한다
PX_PER_IN = 120


def _rgb(h, fallback=(255, 255, 255)):
    h = str(h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return fallback
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _cover(img, w, h):
    """비율 유지하며 (w,h)를 덮도록 확대·중앙 크롭."""
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return img.resize((w, h))
    scale = max(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale + 0.5)), max(1, int(ih * scale + 0.5))
    img = img.resize((nw, nh))
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _ramp(n, fn):
    """길이 n의 1차원 그레이 램프(0~255)를 만든다."""
    from PIL import Image
    strip = Image.new("L", (n, 1))
    strip.putdata([max(0, min(255, int(fn(i)))) for i in range(n)])
    return strip


def _feather_mask(w, h, inset_px):
    """가장자리를 부드럽게 죽이는 마스크. 붙여넣은 사각형 티가 안 나게 한다.

    가로·세로 램프를 각각 만들어 곱한다(픽셀 루프를 돌면 100만 번이라 느리다).
    """
    from PIL import Image, ImageChops
    if inset_px <= 0:
        return Image.new("L", (w, h), 255)
    mx = _ramp(w, lambda i: 255 * min(1.0, min(i, w - 1 - i) / inset_px)).resize((w, h))
    my = _ramp(h, lambda i: 255 * min(1.0, min(i, h - 1 - i) / inset_px)) \
        .transpose(Image.ROTATE_270).resize((w, h))
    return ImageChops.multiply(mx, my)


def _brandify(img, body_color, brand_color):
    """스톡 사진을 흑백으로 바꾼 뒤 테마 색으로 톤을 입힌다.

    검색으로 받은 사진은 파스텔 분홍이든 형광 초록이든 나올 수 있고, 그대로 깔면
    덱 전체가 브랜드와 따로 논다. 명암만 남기고 브랜드 색조로 다시 칠하면
    어떤 사진이 걸려도 '우리 덱의 질감'으로 보인다.
    """
    from PIL import ImageOps
    dark = _mix(_rgb(brand_color, (0, 56, 163)), (0, 0, 0), 0.25)
    light = _mix(_rgb(body_color, (244, 246, 250)), (255, 255, 255), 0.35)
    return ImageOps.colorize(ImageOps.grayscale(img), black=dark, white=light)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def compose(body_color: str, slide_w: float, slide_h: float,
            photo: str = None, photo_transparency: int = 70,
            gradient: dict = None, brand_color: str = "0038A3") -> str:
    """본문 영역(0, HEADER_H)~(slide_w, slide_h)를 덮는 장식 PNG 한 장을 만든다.

    photo_transparency: 0~100. 클수록 사진이 옅다(pptxgenjs transparency와 같은 의미).
    gradient: {"from","to","dir":"h|v","reverse":bool, "x","y","w","h"(선택, 인치)}
    반환: PNG 경로. 만들 게 아무것도 없으면 None.
    """
    if not photo and not gradient:
        return None
    from PIL import Image

    key = hashlib.md5(repr((body_color, brand_color, round(slide_w, 3), round(slide_h, 3),
                            photo, photo_transparency, sorted((gradient or {}).items()))
                           ).encode()).hexdigest()[:14]
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"decor_{key}.png")
    if os.path.exists(path):
        return path

    bw = max(1, int((slide_w) * PX_PER_IN))
    bh = max(1, int((slide_h - HEADER_H) * PX_PER_IN))
    base = Image.new("RGB", (bw, bh), _rgb(body_color, (244, 246, 250)))

    if photo and os.path.exists(photo):
        try:
            ph = _cover(Image.open(photo).convert("RGB"), bw, bh)
            ph = _brandify(ph, body_color, brand_color)
            alpha = max(0, min(100, 100 - int(photo_transparency or 0))) / 100.0
            base = Image.blend(base, ph, alpha)
        except Exception as e:
            print(f"[decor] 배경 사진 합성 실패: {e}")

    if gradient:
        try:
            gradient = dict(gradient)
            gradient["_over_photo"] = bool(photo and os.path.exists(photo))
            base = _paste_gradient(base, gradient, body_color, slide_w, slide_h)
        except Exception as e:
            print(f"[decor] 그라데이션 합성 실패: {e}")

    base.save(path)
    return path


def _paste_gradient(base, g, body_color, slide_w, slide_h):
    from PIL import Image
    bw, bh = base.size

    # 지시 영역(인치) → 장식 캔버스 픽셀. 영역이 없으면 본문 전체.
    gx = float(g.get("x", 0.0))
    gy = float(g.get("y", HEADER_H))
    gw = float(g.get("w", slide_w))
    gh = float(g.get("h", slide_h - HEADER_H))
    x0 = max(0, int(gx * PX_PER_IN))
    y0 = max(0, int((gy - HEADER_H) * PX_PER_IN))
    w = max(1, min(bw - x0, int(gw * PX_PER_IN)))
    h = max(1, min(bh - y0, int(gh * PX_PER_IN)))

    c1 = _rgb(g.get("from") or "0038A3")
    c2 = _rgb(g.get("to") or body_color, _rgb(body_color, (244, 246, 250)))
    if g.get("reverse"):
        c1, c2 = c2, c1
    horizontal = str(g.get("dir", "h")).lower() not in ("v", "vertical", "tb", "bt")

    # 사진 위에 얹을 때는 더 옅게. 장식 위에 장식을 덮으면 얼룩처럼 보인다.
    peak = 0.62 if g.get("_over_photo") else 1.0
    n = w if horizontal else h

    def t_of(i):
        return i / (n - 1) if n > 1 else 0.0

    strip = Image.new("RGB", (n, 1))
    strip.putdata([tuple(int(c1[k] + (c2[k] - c1[k]) * t_of(i)) for k in range(3))
                   for i in range(n)])
    # 진한 쪽은 불투명, 옅은 쪽은 배경이 비치게 — 딱딱한 색면 대신 '효과'로 보인다.
    aramp = _ramp(n, lambda i: 255 * peak * (1.0 - 0.6 * t_of(i)))
    if horizontal:
        panel = strip.resize((w, h))
        alpha = aramp.resize((w, h))
    else:
        panel = strip.transpose(Image.ROTATE_270).resize((w, h))
        alpha = aramp.transpose(Image.ROTATE_270).resize((w, h))

    # 슬라이드 안쪽으로 잘리는 변만 부드럽게 흐린다(화면 끝에 닿는 변은 그대로).
    # 좁게 잡으면 '붙여넣은 사각형' 티가 나 얼룩처럼 보인다 — 넉넉히 흐린다.
    inset = int(min(1.1, min(w, h) / PX_PER_IN * 0.35) * PX_PER_IN)
    if inset > 0 and (x0 > 2 or y0 > 2 or x0 + w < bw - 2 or y0 + h < bh - 2):
        from PIL import ImageChops
        alpha = ImageChops.multiply(alpha, _feather_mask(w, h, inset))

    base.paste(panel, (x0, y0), alpha)
    return base

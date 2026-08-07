# -*- coding: utf-8 -*-
"""SVG 품질 채점 — SVG를 다시 래스터화(resvg)해서 원본과 비교한다.

지표 두 가지
  ssim   : 전체 구조 유사도. 흰 배경이 넓은 도식에서는 변별력이 약하다.
  ink_f1 : 획(어두운 픽셀) 보존 F1. 사라진 '=' 기호, i의 점 같은 결손을 직접 잡는다.
           1px 굵기 차이는 용인하고 '사라짐/없던 얼룩'만 벌점.
  color_mae: 픽셀 색 평균 절대 오차(사진·로고용).

resvg(node)가 없으면 None을 반환 — 이 경우 UI에 점수를 표시하지 않는다(가짜 숫자 금지).
"""
import os
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image

try:
    from skimage.metrics import structural_similarity as _ssim
except Exception:
    _ssim = None

from src.common import paths

HERE = os.path.dirname(os.path.abspath(__file__))
RASTER_JS = os.path.join(HERE, "_svg_raster.js")

_NODE_OK = None


def node_available() -> bool:
    """node + resvg-js 사용 가능 여부 (1회만 검사)."""
    global _NODE_OK
    if _NODE_OK is not None:
        return _NODE_OK
    _NODE_OK = False
    if not os.path.exists(RASTER_JS):
        return False
    try:
        r = subprocess.run([paths.node_exe(), "-e", "require('@resvg/resvg-js');console.log('ok')"],
                           cwd=paths.node_cwd(), capture_output=True, text=True, timeout=30)
        _NODE_OK = (r.returncode == 0 and "ok" in (r.stdout or ""))
    except Exception:
        _NODE_OK = False
    return _NODE_OK


def rasterize(svg_path: str, out_png: str, width: int, timeout: int = 120) -> bool:
    # cwd를 프로젝트 루트로 두고 실행하므로(node_modules 해석) 경로는 반드시 절대경로로.
    svg_path, out_png = os.path.abspath(svg_path), os.path.abspath(out_png)
    try:
        r = subprocess.run([paths.node_exe(), RASTER_JS, svg_path, out_png, str(int(width))],
                           cwd=paths.node_cwd(), capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0 and os.path.exists(out_png)
    except Exception:
        return False


def _flatten(path):
    im = Image.open(path)
    im.load()
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return np.array(Image.alpha_composite(bg, im).convert("RGB"))


def _ink_threshold(gray) -> float:
    t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return t


def _ink_mask(gray, thr=None):
    """획(어두운 픽셀) 마스크. thr을 주면 그 값을 그대로 쓴다.

    원본과 결과에 각각 Otsu를 돌리면 안 된다 — 트레이스 결과는 경계가 더 또렷해서
    더 낮은 임계값이 잡히고, 획이 1px 굵어진 것만으로 '다른 그림'으로 채점된다.
    """
    if thr is None:
        thr = _ink_threshold(gray)
    return gray < thr


_K3 = np.ones((3, 3), np.uint8)


def _cc_coverage(a, b, min_area=4, cover=0.5):
    """a의 획 덩어리 중 b가 (절반 이상) 덮은 비율.

    픽셀 수로 재면 안 된다 — '=' 기호 하나가 사라져도 전체 잉크 면적의 0.1%라
    픽셀 IoU/F1은 거의 움직이지 않는다. 반면 덩어리 단위로 세면 '마크 하나가
    통째로 사라졌다'가 그대로 점수에 찍힌다.
    """
    n, lab, stats, _ = cv2.connectedComponentsWithStats(a, 8)
    if n <= 1:
        return 1.0
    b_d = cv2.dilate(b, _K3)   # 1px 굵기 차이는 눈감아 준다
    covered = np.bincount(lab.ravel(), weights=b_d.ravel().astype(np.float64), minlength=n)
    areas = stats[:, cv2.CC_STAT_AREA].astype(np.float64)
    sel = np.zeros(n, bool)
    sel[1:] = areas[1:] >= min_area     # 1px 점 노이즈는 세지 않음
    if not sel.any():
        return 1.0
    return float(((covered[sel] / areas[sel]) >= cover).mean())


def _ink_f1(ref_gray, cand_gray):
    """획 보존 F1 — 원본의 마크가 살아남았나(recall) + 없던 얼룩이 생겼나(precision)."""
    thr = _ink_threshold(ref_gray)   # 임계값은 원본 기준 하나로 통일
    a = _ink_mask(ref_gray, thr).astype(np.uint8)
    b = _ink_mask(cand_gray, thr).astype(np.uint8)
    if not a.any() and not b.any():
        return 1.0
    rec = _cc_coverage(a, b)
    prec = _cc_coverage(b, a)
    return 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)


def score_svg(svg_path: str, ref_image_path: str, metric: str = "ink",
              max_side: int = 1200, workdir: str = None):
    """{'score','ssim','ink_f1','color_mae'} 또는 채점 불가 시 None."""
    if not node_available() or not os.path.exists(svg_path):
        return None

    ref_rgb = _flatten(ref_image_path)
    h, w = ref_rgb.shape[:2]
    # 채점은 축소본으로 — 큰 SVG를 원본 크기로 렌더하면 느리기만 하고 결론은 같다.
    if max(w, h) > max_side:
        sc = max_side / max(w, h)
        ref_rgb = cv2.resize(ref_rgb, (max(1, int(w * sc)), max(1, int(h * sc))), interpolation=cv2.INTER_AREA)
        h, w = ref_rgb.shape[:2]
    ref_gray = cv2.cvtColor(ref_rgb, cv2.COLOR_RGB2GRAY)

    wd = workdir or tempfile.gettempdir()
    png = os.path.join(wd, os.path.basename(svg_path)[:-4] + "_score.png")
    if not rasterize(svg_path, png, w):
        return None
    try:
        cand = np.array(Image.open(png).convert("RGB"))
    except Exception:
        return None
    finally:
        try:
            os.remove(png)
        except Exception:
            pass

    if cand.shape[:2] != (h, w):
        cand = cv2.resize(cand, (w, h), interpolation=cv2.INTER_AREA)
    cand_gray = cv2.cvtColor(cand, cv2.COLOR_RGB2GRAY)

    s = float(_ssim(ref_gray, cand_gray)) if _ssim is not None else 0.0
    iou = _ink_f1(ref_gray, cand_gray)
    mae = float(np.abs(cand.astype(np.int16) - ref_rgb.astype(np.int16)).mean())

    if metric == "ink":
        # 글자·선이 핵심인 유형: 획 보존에 무게를 싣는다.
        score = 0.4 * s + 0.6 * iou
    else:
        # 색이 핵심인 유형: SSIM + 색 오차(0~24 구간을 1~0으로 환산)
        score = 0.7 * s + 0.3 * max(0.0, 1.0 - mae / 24.0)

    return {"score": round(score, 5), "ssim": round(s, 5),
            "ink_f1": round(iou, 5), "color_mae": round(mae, 3)}

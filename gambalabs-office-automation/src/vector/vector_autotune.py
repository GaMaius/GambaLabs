# -*- coding: utf-8 -*-
"""감바랩스 벡터 자동 튜닝 엔진 (vtracer + OpenCV + SSIM/InkIoU)

역할 3가지
  1) 이미지 분류      : lineart / diagram / logo / photo
  2) 유형별 전처리     : 업스케일·이진화·색 단순화 (vtracer가 삼키기 좋은 형태로)
  3) 후보 파라미터 생성 : 실제 트레이스 → 래스터화 → 점수 비교로 최적안 선택(autotune)

실제 트레이스/채점 루프는 별도 프로세스(app/ppt/_vtrace_run.py)에서 돈다.
여기서는 "무엇을 시도할지"와 "어떻게 점수 매길지"만 정의한다.

■ vtracer 파라미터 유효 범위 (공식 문서 기준 — 벗어나면 형상이 깨진다)
    filter_speckle    1~16  (이 값보다 작은 점/획은 통째로 버려짐 → 글자 획 실종의 주범)
    color_precision   1~8
    layer_difference  0~255
    corner_threshold  0~180 (낮을수록 코너를 많이 잡음 → 곡선이 각짐)
    length_threshold  3.5~10 (범위 밖 값은 과분할 → 경로 붕괴)
    splice_threshold  0~180
    path_precision    0~8
"""
import cv2
import numpy as np
from PIL import Image

CATEGORIES = ("lineart", "diagram", "logo", "photo")

# 옛 프리셋 이름이 들어와도 죽지 않도록
_ALIAS = {"text": "lineart", "general": "diagram", "auto": "diagram"}


# ──────────────────────────────────────────────────────────────────────────
# 유형별 기본 파라미터 (실측으로 검증한 값)
#   upscale  : 트레이스 전 확대 배율. 안티에일리어싱된 글자 획을 살리는 핵심.
#   quantize : 색 수 제한(0=제한 없음). 도식/글자에는 오히려 해로워서 0.
# ──────────────────────────────────────────────────────────────────────────
PRESETS = {
    # 흑백 선화: 순서도·도면·스캔 문서·수식. 이진화 후 binary 모드로 뽑는 게 압도적으로 깨끗하다.
    "lineart": {
        "upscale": 2.0, "binarize": True, "quantize": 0, "cap": 3200,
        "params": {
            "colormode": "binary", "hierarchical": "stacked", "mode": "spline",
            "filter_speckle": 2, "color_precision": 8, "layer_difference": 16,
            "corner_threshold": 60, "length_threshold": 4.0,
            "splice_threshold": 45, "max_iterations": 10, "path_precision": 3,
        },
    },
    # 컬러 도식: 다이어그램·차트·UI 스크린샷. 작은 글자가 많아 filter_speckle을 낮게 유지해야 한다.
    "diagram": {
        "upscale": 2.0, "binarize": False, "quantize": 0, "cap": 3000,
        "params": {
            "colormode": "color", "hierarchical": "stacked", "mode": "spline",
            "filter_speckle": 2, "color_precision": 8, "layer_difference": 16,
            "corner_threshold": 60, "length_threshold": 5.0,
            "splice_threshold": 45, "max_iterations": 10, "path_precision": 3,
        },
    },
    # 로고·아이콘·플랫 일러스트: 색 수가 적고 면이 넓다.
    "logo": {
        "upscale": 2.0, "binarize": False, "quantize": 0, "cap": 2400,
        "params": {
            "colormode": "color", "hierarchical": "stacked", "mode": "spline",
            "filter_speckle": 4, "color_precision": 8, "layer_difference": 16,
            "corner_threshold": 60, "length_threshold": 4.0,
            "splice_threshold": 45, "max_iterations": 10, "path_precision": 3,
        },
    },
    # 사진·연속 톤: 확대하면 용량만 폭발하므로 등배~축소.
    # 격자 탐색 결과 filter_speckle 4 · 색 제한 없음 · bilateral 없음이 확실히 우세했다
    # (파인애플.webp 기준 score 0.816 → 0.877). 용량을 줄이려면 autotune 변형을 쓴다.
    "photo": {
        "upscale": 1.0, "binarize": False, "quantize": 0, "cap": 1400,
        "params": {
            "colormode": "color", "hierarchical": "stacked", "mode": "spline",
            "filter_speckle": 4, "color_precision": 8, "layer_difference": 16,
            "corner_threshold": 60, "length_threshold": 4.0,
            "splice_threshold": 45, "max_iterations": 10, "path_precision": 3,
        },
        "denoise": 0,   # bilateral 커널 지름(0=사용 안 함)
    },
}

# autotune 시 추가로 시도할 변형 (첫 항목 = 프리셋 기본값이므로 생략)
_VARIANTS = {
    "lineart": [
        {"label": "고해상", "upscale": 3.0},
        {"label": "잡티강", "params": {"filter_speckle": 6}},
        {"label": "직선", "params": {"mode": "polygon"}},
    ],
    "diagram": [
        {"label": "경량", "params": {"color_precision": 6}},
        {"label": "잡티강", "params": {"filter_speckle": 6}},
        {"label": "고해상", "upscale": 2.5},
    ],
    "logo": [
        {"label": "잡티최소", "params": {"filter_speckle": 2}},
        {"label": "24색", "quantize": 24},
    ],
    # 사진은 기본이 가장 정확하지만 용량이 크다 — 아래는 용량을 줄이는 쪽 후보들.
    "photo": [
        {"label": "64색", "quantize": 64},
        {"label": "32색", "quantize": 32},
        {"label": "잡티강", "params": {"filter_speckle": 10}},
    ],
}

# 유형별 채점 방식: 글자가 중요한 유형은 잉크 IoU 가중을 높인다.
#   SSIM 단독은 흰 배경이 대부분인 도식에서 변별력이 없다(0.976 vs 0.989).
#   잉크 IoU(검은 획 픽셀의 교집합/합집합)는 사라진 '=' 기호·i의 점을 그대로 잡아낸다.
METRIC = {"lineart": "ink", "diagram": "ink", "logo": "color", "photo": "color"}


def imread_unicode(path):
    """한글 경로 대응 cv2.imread (알파 포함)."""
    try:
        buf = np.fromfile(path, np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    except Exception:
        return None


def flatten_on_white(im):
    """RGBA → 흰 배경 합성 RGB (채점 기준 이미지용)."""
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert("RGB")


def defringe_cutout(im: Image.Image, erode_px: int = 1) -> Image.Image:
    """배경 제거 결과의 반투명 테두리를 잘라낸다.

    rembg가 남기는 경계 픽셀은 피사체 색과 원래 배경색이 섞여 있다. 그대로 트레이스하면
    윤곽을 따라 검은 실선/점선이 생긴다. 알파를 이진화하고 1px 깎아 오염된 띠를 버린다.
    """
    a = np.array(im.convert("RGBA"))
    alpha = a[:, :, 3]
    if not np.any((alpha > 0) & (alpha < 250)):
        return im   # 이미 하드 엣지면 손대지 않는다
    m = (alpha >= 128).astype(np.uint8)
    if erode_px > 0:
        m = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=int(erode_px))
    a[:, :, 3] = m * 255
    return Image.fromarray(a, "RGBA")


class VectorAutotuner:
    """이미지 분석 · 전처리 · 후보 파라미터 생성기"""

    def __init__(self, image_path: str):
        self.image_path = image_path
        self.im_pil = Image.open(image_path)
        self.im_pil.load()
        self.im_pil = self.im_pil.convert("RGBA")
        self.w, self.h = self.im_pil.size
        self._profile = None

    # ── 1) 분석 ──────────────────────────────────────────────────────────
    def profile(self) -> dict:
        """엣지 밀도·채도·색 수·이진성으로 이미지 성격을 수치화."""
        if self._profile is not None:
            return self._profile

        rgb = np.array(flatten_on_white(self.im_pil))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(np.count_nonzero(edges)) / max(self.w * self.h, 1)

        # 색 수 (2만 색에서 포화)
        colors = self.im_pil.getcolors(maxcolors=20000)
        n_colors = len(colors) if colors else 20001

        # 채도: 유채색 픽셀이 거의 없으면 흑백 선화 후보
        sat_mean = float(hsv[:, :, 1].mean())
        colorful_ratio = float(np.count_nonzero(hsv[:, :, 1] > 40)) / max(self.w * self.h, 1)

        # 이진성: 아주 밝거나 아주 어두운 픽셀의 비율
        bilevel_ratio = float(np.count_nonzero((gray < 60) | (gray > 200))) / max(self.w * self.h, 1)

        alpha = np.array(self.im_pil.getchannel("A"))
        has_alpha = bool(np.count_nonzero(alpha < 250))

        self._profile = {
            "w": self.w, "h": self.h,
            "edge_density": edge_density,
            "n_colors": n_colors,
            "sat_mean": sat_mean,
            "colorful_ratio": colorful_ratio,
            "bilevel_ratio": bilevel_ratio,
            "has_alpha": has_alpha,
            "small_mark_ratio": self._small_mark_ratio(gray),
        }
        return self._profile

    @staticmethod
    def _small_mark_ratio(gray) -> float:
        """전체 획 덩어리 중 '작은 마크'(글자·기호 크기)의 비율.

        확대 트레이스가 이득인지 판단하는 신호다. 글자가 많으면(비율↑) 원본 해상도로는
        획이 뭉개지므로 2배 확대가 이득이고, 큰 면으로 이뤄진 아이콘·로고(비율↓)는
        확대해봐야 경계 램프만 넓어져 레이어가 겹치며 후광이 생긴다.
        """
        t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        m = (gray < t).astype(np.uint8)
        n, _lab, st, _c = cv2.connectedComponentsWithStats(m, 8)
        if n <= 1:
            return 0.0
        areas = st[1:, cv2.CC_STAT_AREA]
        areas = areas[areas >= 4]
        if len(areas) == 0:
            return 0.0
        rel = areas / float(gray.shape[0] * gray.shape[1])
        return float((rel < 0.0008).mean())

    def classify(self) -> str:
        """lineart / diagram / logo / photo 중 하나."""
        p = self.profile()

        # 흑백에 가깝고 대비가 뚜렷하면 선화(순서도·도면·문서 스캔)
        if p["colorful_ratio"] < 0.02 and p["bilevel_ratio"] > 0.85:
            return "lineart"

        # 색이 있어도 평면 색 + 엣지가 많으면 도식(다이어그램·차트·스크린샷)
        if p["n_colors"] <= 6000 and p["edge_density"] > 0.015:
            return "diagram"

        # 색 수가 적고 엣지도 적으면 로고·아이콘·플랫 일러스트
        if p["n_colors"] <= 3000:
            return "logo"

        # 색이 아주 많은데 엣지도 많으면 글자 있는 컬러 스크린샷일 확률이 높다
        if p["edge_density"] > 0.05 and p["colorful_ratio"] < 0.35:
            return "diagram"

        return "photo"

    # ── 2) 전처리 ────────────────────────────────────────────────────────
    def default_upscale(self, category: str) -> float:
        """이 이미지에 확대 트레이스가 이득인지 판단해 배율을 정한다.

        글자·작은 기호가 많으면(small_mark_ratio↑) 원본 해상도에서 획이 뭉개지므로 확대가 이득.
        큰 면으로 이뤄진 아이콘·로고는 확대해도 새로 얻을 정보가 없고, 경계 램프만 넓어져
        vtracer가 그 램프를 여러 색 레이어로 쪼개며 후광이 생긴다.
        """
        pr = PRESETS.get(category, PRESETS["diagram"])
        if category in ("diagram", "logo") and self.profile()["small_mark_ratio"] < 0.5:
            return 1.0
        return pr["upscale"]

    def target_size(self, category: str, upscale=None, cap=None):
        """트레이스 해상도 결정. 선화·도식은 확대, 사진은 축소."""
        pr = PRESETS[category]
        up = pr["upscale"] if upscale is None else float(upscale)
        limit = pr["cap"] if not cap or int(cap) <= 0 else int(cap)
        long_side = max(self.w, self.h)
        target = long_side * up
        target = min(target, limit)
        # 사진은 원본보다 키우지 않는다
        if up <= 1.0:
            target = min(target, long_side)
        scale = target / max(long_side, 1)
        return max(1, int(round(self.w * scale))), max(1, int(round(self.h * scale)))

    def preprocess(self, category: str, upscale=None, cap=None, quantize=None) -> Image.Image:
        """유형별 전처리된 PIL 이미지를 반환.

        옛 구현이 하던 '언샤프 마스킹'은 제거했다. 글자 테두리에 밝은/어두운 헤일로가
        생기고, 그 헤일로가 vtracer에서 별도 색 레이어로 잡혀 획이 이중으로 찍혔다.
        """
        cat = _ALIAS.get(category, category)
        pr = PRESETS.get(cat, PRESETS["diagram"])
        tw, th = self.target_size(cat, upscale, cap)
        q = pr["quantize"] if quantize is None else int(quantize)

        if pr["binarize"]:
            # 선화: 흰 배경 합성 → 그레이스케일 → 확대 → Otsu 이진화
            rgb = np.array(flatten_on_white(self.im_pil))
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            interp = cv2.INTER_CUBIC if tw >= self.w else cv2.INTER_AREA
            gray = cv2.resize(gray, (tw, th), interpolation=interp)
            _, binimg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return Image.fromarray(binimg).convert("RGB")

        im = self.im_pil  # RGBA (투명 보존 — RGB로 바꾸면 투명이 검정이 된다)

        d = int(pr.get("denoise", 0))
        if d:
            # 엣지 보존 평활화. 용량은 줄지만 실측상 재현도는 조금 떨어져 기본은 꺼 둔다.
            arr = np.array(im)
            arr = np.dstack([cv2.bilateralFilter(arr[:, :, :3], d, 45, 45), arr[:, :, 3]])
            im = Image.fromarray(arr, "RGBA")

        if (tw, th) != im.size:
            # BICUBIC — LANCZOS는 경계에서 오버슈트(링잉)해 밝은/어두운 테두리를 만들고,
            # vtracer가 그 테두리를 별도 색 레이어로 잡아 획 둘레에 후광이 생긴다.
            im = im.resize((tw, th), Image.BICUBIC if tw >= im.size[0] else Image.LANCZOS)

        if q >= 2:
            alpha = im.getchannel("A")
            rgb = im.convert("RGB").quantize(colors=q, method=Image.MEDIANCUT, dither=Image.NONE)
            im = rgb.convert("RGB").convert("RGBA")
            im.putalpha(alpha)

        return im

    # ── 3) 후보 생성 ─────────────────────────────────────────────────────
    def build_candidates(self, category: str, autotune: bool = False,
                         overrides: dict = None, cap=None, quantize=None, max_tries: int = 4):
        """[{label, upscale, quantize, cap, params}] — 첫 항목이 프리셋 기본값."""
        cat = _ALIAS.get(category, category)
        pr = PRESETS.get(cat, PRESETS["diagram"])
        overrides = overrides or {}

        base_up = self.default_upscale(cat)

        def mk(label, up=None, q=None, extra=None):
            params = dict(pr["params"])
            params.update(overrides)
            if extra:
                params.update(extra)
            return {
                "label": label,
                "upscale": base_up if up is None else up,
                "quantize": (pr["quantize"] if quantize is None else int(quantize)) if q is None else q,
                "cap": cap,
                "params": clamp_params(params),
            }

        out = [mk("기본")]
        if autotune:
            seen = {base_up}
            for v in _VARIANTS.get(cat, []):
                up = v.get("upscale")
                if up is not None and up in seen:
                    continue
                if up is not None:
                    seen.add(up)
                out.append(mk(v["label"], up, v.get("quantize"), v.get("params")))
            # 기본이 확대라면 등배도, 등배라면 확대도 한 번은 시도해 본다.
            alt = 1.0 if base_up > 1.0 else pr["upscale"]
            if alt not in seen and alt != base_up:
                out.append(mk("등배" if alt == 1.0 else "확대", alt))
        return out[:max(1, int(max_tries))]


def clamp_params(p: dict) -> dict:
    """vtracer 유효 범위로 강제. 범위를 벗어난 값이 경로 붕괴의 원인이었다."""
    q = dict(p)
    q["colormode"] = q.get("colormode") if q.get("colormode") in ("color", "binary") else "color"
    q["hierarchical"] = q.get("hierarchical") if q.get("hierarchical") in ("stacked", "cutout") else "stacked"
    q["mode"] = q.get("mode") if q.get("mode") in ("spline", "polygon", "pixel") else "spline"
    q["filter_speckle"] = int(min(max(int(q.get("filter_speckle", 4)), 0), 128))
    q["color_precision"] = int(min(max(int(q.get("color_precision", 6)), 1), 8))
    q["layer_difference"] = int(min(max(int(q.get("layer_difference", 16)), 0), 255))
    q["corner_threshold"] = int(min(max(int(q.get("corner_threshold", 60)), 0), 180))
    # 공식 유효 범위 [3.5, 10]. 옛 코드의 1.5는 과분할을 일으켜 글자를 뭉갰다.
    q["length_threshold"] = float(min(max(float(q.get("length_threshold", 4.0)), 3.5), 10.0))
    q["splice_threshold"] = int(min(max(int(q.get("splice_threshold", 45)), 0), 180))
    q["max_iterations"] = int(min(max(int(q.get("max_iterations", 10)), 1), 64))
    q["path_precision"] = int(min(max(int(q.get("path_precision", 3)), 0), 8))
    return q

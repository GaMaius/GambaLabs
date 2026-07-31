# -*- coding: utf-8 -*-
"""vtracer 변환을 별도 프로세스에서 실행 (타임아웃으로 무한 지연 방지).
사용: python _vtrace_run.py <src> <out> <colormode> <mode> <filter_speckle> <color_precision>
"""
import sys
import vtracer

_, src, out, colormode, mode, speckle, cprec = sys.argv
vtracer.convert_image_to_svg_py(
    src, out,
    colormode=colormode if colormode in ("color", "binary") else "color",
    mode=mode if mode in ("spline", "polygon", "pixel") else "spline",
    filter_speckle=int(speckle),
    color_precision=int(cprec),
)
print("OK")

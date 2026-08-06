# -*- coding: utf-8 -*-
"""vtracer 결과 SVG 무손실 축소.

파일의 85%가 <path d="..."> 좌표 문자열이다. 좌표 값 자체는 건드리지 않고
표기만 줄인다(1.0→1, 0.6→.6, "1 -2"→"1-2"). 렌더 결과는 바이트 단위로 동일하다.
"""
import re

# 숫자 하나: 부호 + 정수부 + 소수부
_NUM = re.compile(r"-?(?:\d+\.\d+|\.\d+|\d+)")
_D_ATTR = re.compile(r'(\sd=")([^"]*)(")')
_WS = re.compile(r"[ \t\r\n]+")


def _shorten_number(m) -> str:
    s = m.group(0)
    if "." not in s:
        return s
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    intp, frac = s.split(".", 1)
    frac = frac.rstrip("0")
    if not frac:
        s = intp or "0"
    else:
        # 0.6 → .6 (정수부가 0일 때만)
        s = ("" if intp == "0" else intp) + "." + frac
        if s == ".":
            s = "0"
    if s == "":
        s = "0"
    return ("-" + s) if neg else s


def minify_path_data(d: str) -> str:
    d = _WS.sub(" ", d).strip()
    d = _NUM.sub(_shorten_number, d)
    # 구분자를 지워도 되는 건 '-' 앞뿐이다. '.' 앞의 공백을 지우면 "1 .5"가 "1.5" 한 숫자로
    # 합쳐져 좌표가 하나 사라진다(실제로 렌더가 달라졌던 버그).
    d = re.sub(r"\s+(-)", r"\1", d)
    d = re.sub(r"\s*([A-Za-z])\s*", r"\1", d)   # 명령 문자 앞뒤 공백
    return d


def minify(svg_text: str) -> str:
    return _D_ATTR.sub(lambda m: m.group(1) + minify_path_data(m.group(2)) + m.group(3), svg_text)


def minify_file(path: str) -> tuple:
    """(before_bytes, after_bytes). 문제가 생기면 원본을 그대로 둔다."""
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    before = len(src.encode("utf-8"))
    try:
        out = minify(src)
    except Exception:
        return before, before
    data = out.encode("utf-8")
    if len(data) >= before:
        return before, before
    with open(path, "wb") as f:
        f.write(data)
    return before, len(data)

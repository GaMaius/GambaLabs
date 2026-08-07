# -*- coding: utf-8 -*-
"""발표자료 테마 관리 — 내장 테마 + 사용자 커스텀 테마(업로드/제작).

테마 = render_deck.js가 이해하는 설정(JSON). 커스텀 테마는 app/ppt/themes/*.json에 저장하고,
렌더 시 api가 resolve()로 전체 설정을 읽어 plan['themeConfig']로 넘긴다(내장은 JS에 하드코딩).

skill로 테마 파일을 만들 때의 스키마는 ppt-skill/THEME_AUTHORING.md 참고.
"""
import os
import re
import json
from typing import Dict, Any, List, Optional

from src.common import paths

# 사용자 테마는 **쓰기 가능한 작업 폴더**에 둔다. 패키지 안(app/ppt/themes)에 두면
# exe로 묶었을 때 읽기 전용 임시 폴더가 되어 저장이 조용히 실패한다.
THEMES_DIR = paths.USER_THEMES_DIR
_LEGACY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")


def _migrate_legacy():
    """예전 위치(app/ppt/themes)에 있던 테마를 새 위치로 한 번만 옮긴다."""
    if not os.path.isdir(_LEGACY_DIR):
        return
    os.makedirs(THEMES_DIR, exist_ok=True)
    for f in os.listdir(_LEGACY_DIR):
        if not f.endswith(".json"):
            continue
        dst = os.path.join(THEMES_DIR, f)
        if not os.path.exists(dst):
            try:
                os.replace(os.path.join(_LEGACY_DIR, f), dst)
            except OSError:
                pass


_migrate_legacy()

# 내장 테마(설정 본체는 render_deck.js). 여기선 선택기용 메타데이터만.
BUILTIN = [
    {"id": "gamba", "label": "감바랩스 네이비", "desc": "브랜드 풀 (네이비 배경·밴드·로고)"},
    {"id": "light", "label": "감바랩스 라이트", "desc": "밝은 배경 (인쇄·문서용)"},
    {"id": "none", "label": "테마 없음", "desc": "플레인 (브랜드 없이 깔끔한 기본)"},
]
_BUILTIN_IDS = {t["id"] for t in BUILTIN}


# ── 색 유틸 ────────────────────────────────────────
def _norm_hex(h: str, fallback: str = "000000") -> str:
    h = (h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", h) else fallback


def _rgb(h):
    h = _norm_hex(h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(r, g, b):
    f = lambda v: max(0, min(255, int(round(v))))
    return f"{f(r):02X}{f(g):02X}{f(b):02X}"


def _mix(h, target, t):
    r, g, b = _rgb(h)
    tr, tg, tb = target
    return _hex(r + (tr - r) * t, g + (tg - g) * t, b + (tb - b) * t)


def _lighten(h, t):
    return _mix(h, (255, 255, 255), t)


def _darken(h, t):
    return _mix(h, (0, 0, 0), t)


def _is_light(h):
    r, g, b = _rgb(h)
    return (0.299 * r + 0.587 * g + 0.114 * b) > 150


# ── 색 몇 개 → 완전한 테마 설정 ─────────────────────
def build_config(label: str, bg: str, accent: str, ink: str,
                 band_fill: bool = True, font_title: str = "맑은 고딕",
                 font_body: str = "맑은 고딕", desc: str = "") -> Dict[str, Any]:
    """배경/강조/텍스트 색 + 밴드 스타일로 render_deck.js가 쓰는 전체 설정을 만든다."""
    bg = _norm_hex(bg, "FFFFFF")
    accent = _norm_hex(accent, "2456C7")
    ink = _norm_hex(ink, "1A1A1A")
    C = {
        "hero": ink, "brand": accent, "med": _lighten(accent, 0.18),
        "body": bg, "white": "FFFFFF", "muted": _lighten(ink, 0.42),
        "gray": _lighten(ink, 0.34), "sky": _lighten(accent, 0.30),
        "teal": "2A9D99", "surface2": _lighten(accent, 0.82),
        "cardBg": "FFFFFF" if _is_light(bg) else _lighten(bg, 0.07),
        "cardInk": ink,
    }
    cfg = {
        "label": label, "desc": desc or "사용자 테마",
        "C": C, "F": {"title": font_title, "body": font_body},
        "useImages": False,
        "bandColor": accent if band_fill else _lighten(bg, 0.0),
        "bandInk": "FFFFFF" if band_fill else ink,
        "coverBg": bg, "coverInk": ink, "coverSub": accent, "coverFoot": _lighten(ink, 0.42),
        "logo": None, "closingBg": bg, "accent": accent,
    }
    if not band_fill:
        cfg["bandColor"] = bg
        cfg["bandLine"] = _darken(bg, 0.14) if _is_light(bg) else _lighten(bg, 0.18)
    return cfg


# ── 커스텀 테마 파일 완성/검증 ───────────────────────
def _complete(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """업로드된 부분 설정을 렌더에 안전하도록 누락 필드 보정."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("C"), dict):
        raise ValueError("테마에 색 팔레트(C)가 없습니다.")
    C = {k: _norm_hex(v) for k, v in cfg["C"].items() if isinstance(v, str)}
    # 필수 팔레트 키 보정
    ink = C.get("hero", "1A1A1A")
    accent = C.get("brand", "2456C7")
    bg = C.get("body", "FFFFFF")
    C.setdefault("med", _lighten(accent, 0.18))
    C.setdefault("white", "FFFFFF")
    C.setdefault("muted", _lighten(ink, 0.42))
    C.setdefault("gray", _lighten(ink, 0.34))
    C.setdefault("sky", _lighten(accent, 0.30))
    C.setdefault("teal", "2A9D99")
    C.setdefault("surface2", _lighten(accent, 0.82))
    C.setdefault("cardBg", "FFFFFF" if _is_light(bg) else _lighten(bg, 0.07))
    C.setdefault("cardInk", ink)
    F = cfg.get("F") if isinstance(cfg.get("F"), dict) else {}
    out = {
        "label": cfg.get("label") or "사용자 테마", "desc": cfg.get("desc") or "사용자 테마",
        "C": C, "F": {"title": F.get("title", "맑은 고딕"), "body": F.get("body", "맑은 고딕")},
        "useImages": False,  # 커스텀은 브랜드 이미지 에셋이 없으므로 도형 기반 강제
        "bandColor": _norm_hex(cfg.get("bandColor"), accent),
        "bandInk": _norm_hex(cfg.get("bandInk"), "FFFFFF"),
        "coverBg": _norm_hex(cfg.get("coverBg"), bg),
        "coverInk": _norm_hex(cfg.get("coverInk"), ink),
        "coverSub": _norm_hex(cfg.get("coverSub"), accent),
        "coverFoot": _norm_hex(cfg.get("coverFoot"), _lighten(ink, 0.42)),
        "logo": None, "closingBg": _norm_hex(cfg.get("closingBg"), bg),
        "accent": _norm_hex(cfg.get("accent"), accent),
    }
    if cfg.get("bandLine"):
        out["bandLine"] = _norm_hex(cfg.get("bandLine"), _darken(bg, 0.14))
    elif _is_light(out["bandColor"]) and out["bandColor"] == out["coverBg"]:
        out["bandLine"] = _darken(bg, 0.14)
    return out


def _slug(name: str, taken) -> str:
    s = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", (name or "").strip()).strip("-")
    s = re.sub(r"[가-힣]", "", s).strip("-") or "theme"
    base, i = s, 1
    while s in taken or s in _BUILTIN_IDS:
        i += 1
        s = f"{base}{i}"
    return s


# ── 공개 API ───────────────────────────────────────
def list_themes() -> List[Dict[str, str]]:
    items = [dict(t) for t in BUILTIN]
    if os.path.isdir(THEMES_DIR):
        for fn in sorted(os.listdir(THEMES_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(THEMES_DIR, fn), "r", encoding="utf-8") as f:
                    c = json.load(f)
                items.append({"id": fn[:-5], "label": c.get("label", fn[:-5]),
                              "desc": c.get("desc", "사용자 테마"), "custom": True})
            except Exception:
                continue
    return items


def resolve(theme_id: str) -> Optional[Dict[str, Any]]:
    """내장이면 None(JS가 처리), 커스텀이면 전체 설정 dict."""
    if not theme_id or theme_id in _BUILTIN_IDS:
        return None
    path = os.path.join(THEMES_DIR, f"{theme_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return _complete(json.load(f))


def _existing_ids():
    if not os.path.isdir(THEMES_DIR):
        return set()
    return {fn[:-5] for fn in os.listdir(THEMES_DIR) if fn.endswith(".json")}


def _save(cfg: Dict[str, Any], name: str) -> Dict[str, str]:
    os.makedirs(THEMES_DIR, exist_ok=True)
    tid = _slug(name, _existing_ids())
    cfg = _complete(cfg)
    cfg["label"] = name or cfg.get("label")
    with open(os.path.join(THEMES_DIR, f"{tid}.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    return {"id": tid, "label": cfg["label"]}


def add_from_file(name: str, src_path: str) -> Dict[str, str]:
    """업로드한 테마 JSON 파일을 검증·저장."""
    if not src_path or not os.path.exists(src_path):
        raise ValueError("테마 파일을 선택하세요.")
    with open(src_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)          # 잘못된 JSON이면 여기서 예외
    return _save(cfg, name or cfg.get("label") or os.path.splitext(os.path.basename(src_path))[0])


def add_from_spec(name: str, bg: str, accent: str, ink: str, band_fill: bool = True,
                  font_title: str = "맑은 고딕", font_body: str = "맑은 고딕") -> Dict[str, str]:
    """제작 창에서 받은 색·옵션으로 테마를 생성·저장."""
    if not (name or "").strip():
        raise ValueError("테마 이름을 입력하세요.")
    cfg = build_config(name, bg, accent, ink, band_fill, font_title, font_body)
    return _save(cfg, name)


def delete_theme(theme_id: str) -> bool:
    if theme_id in _BUILTIN_IDS:
        return False
    path = os.path.join(THEMES_DIR, f"{theme_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

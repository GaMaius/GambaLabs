# -*- coding: utf-8 -*-
"""경로 단일 기준점 — 소스 실행과 exe 빌드에서 똑같이 동작한다.

왜 필요한가:
  예전에는 모듈마다 `os.path.dirname(os.path.dirname(os.path.dirname(__file__)))`을
  각자 계산했다. 폴더를 한 칸만 옮겨도 조용히 엉뚱한 곳을 가리키고, PyInstaller로 묶으면
  `__file__`이 임시 추출 폴더(_MEIPASS)를 가리켜 전부 어긋난다.

핵심 구분 두 가지:
  RES_DIR   읽기 전용 리소스(에셋·JS·번들된 코드).  빌드본에서는 _MEIPASS.
  DATA_DIR  쓰기 가능한 작업 폴더(산출물·캐시·사용자 테마).  빌드본에서는 **exe 옆**.
  둘을 섞으면 빌드본이 자기 설치 폴더에 쓰려다 실패하거나, 임시 폴더에 써서
  앱을 끄는 순간 결과물이 사라진다.
"""
import os
import sys

IS_FROZEN = bool(getattr(sys, "frozen", False))

# ── 리소스 루트 ────────────────────────────────────────────────
# 소스 실행: 이 파일 기준 두 단계 위(= 프로젝트 루트)
# 빌드 실행: PyInstaller가 풀어 놓은 폴더
_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES_DIR = getattr(sys, "_MEIPASS", None) or _SRC_ROOT

# ── 작업 폴더 루트 ─────────────────────────────────────────────
# 빌드 실행: exe가 놓인 폴더. 소스 실행: 프로젝트 루트.
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if IS_FROZEN else _SRC_ROOT
DATA_DIR = os.environ.get("GAMBA_DATA_DIR") or APP_DIR

OUTPUT_DIR = os.path.join(DATA_DIR, "output")
CACHE_DIR = os.path.join(OUTPUT_DIR, "_cache")        # 그라데이션·배경장식·스톡이미지 캐시
TMP_DIR = os.path.join(OUTPUT_DIR, "_tmp")            # 렌더용 임시 JS/JSON
USER_THEMES_DIR = os.path.join(DATA_DIR, "themes")    # 사용자가 만든 테마(쓰기 필요)

# ── 리소스 경로 ────────────────────────────────────────────────
SKILL_DIR = os.path.join(RES_DIR, "ppt-skill")
ASSETS_DIR = os.path.join(SKILL_DIR, "assets")
UI_DIR = os.path.join(RES_DIR, "app", "ui")

# ── Node 런타임 ────────────────────────────────────────────────
# 빌드본에는 runtime/node/node.exe 와 node_modules 를 exe 옆에 함께 넣는다.
# 없으면 PATH의 node를 쓴다(개발 환경).
_BUNDLED_NODE = os.path.join(APP_DIR, "runtime", "node",
                             "node.exe" if os.name == "nt" else "node")


def node_exe() -> str:
    """실행할 node 바이너리. 번들본이 있으면 그걸 먼저 쓴다."""
    return _BUNDLED_NODE if os.path.exists(_BUNDLED_NODE) else "node"


def node_cwd() -> str:
    """node를 실행할 작업 폴더 = node_modules 가 있는 곳.

    require() 해석이 여기서부터 위로 올라가므로 이걸 틀리면
    'Cannot find module pptxgenjs'로 전부 죽는다.
    """
    for base in (APP_DIR, RES_DIR, _SRC_ROOT):
        if os.path.isdir(os.path.join(base, "node_modules")):
            return base
    return APP_DIR


def node_ready() -> bool:
    """node 바이너리와 node_modules가 둘 다 있는가."""
    exe = node_exe()
    have_exe = (exe != "node") or bool(_which("node"))
    return have_exe and os.path.isdir(os.path.join(node_cwd(), "node_modules"))


def _which(name):
    import shutil
    return shutil.which(name)


def env_file() -> str:
    """.env 위치. 빌드본은 exe 옆에 두고 사용자가 키를 채운다."""
    return os.path.join(DATA_DIR, ".env")


def res(*parts) -> str:
    """리소스 경로 조립. res('ppt-skill', 'assets')"""
    return os.path.join(RES_DIR, *parts)


def data(*parts) -> str:
    """작업 폴더 경로 조립(필요하면 상위 폴더까지 만든다)."""
    p = os.path.join(DATA_DIR, *parts)
    os.makedirs(os.path.dirname(p) if os.path.splitext(p)[1] else p, exist_ok=True)
    return p


def ensure_dirs():
    for d in (OUTPUT_DIR, CACHE_DIR, TMP_DIR, USER_THEMES_DIR):
        os.makedirs(d, exist_ok=True)


def describe() -> dict:
    """진단용 — 문제 생기면 이걸 찍어 보면 어디를 보고 있는지 바로 나온다."""
    return {
        "frozen": IS_FROZEN,
        "RES_DIR": RES_DIR,
        "APP_DIR": APP_DIR,
        "DATA_DIR": DATA_DIR,
        "assets": ASSETS_DIR,
        "node": node_exe(),
        "node_cwd": node_cwd(),
        "node_ready": node_ready(),
    }

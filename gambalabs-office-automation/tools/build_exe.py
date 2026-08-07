# -*- coding: utf-8 -*-
"""인수인계용 자립 실행 폴더 빌드 — 감바랩스 오피스 AI.

    python tools/build_exe.py            전체 빌드
    python tools/build_exe.py --no-node  Node 런타임 번들 생략(받는 사람이 Node 설치)
    python tools/build_exe.py --clean    build/·dist/ 지우고 새로

결과: dist/GambaLabsOffice/  ← 이 폴더째로 압축해 전달한다.
  GambaLabsOffice.exe   실행 파일
  _internal/            파이썬 런타임·라이브러리(건드리지 말 것)
  runtime/node/         Node 런타임(번들한 경우)
  node_modules/         pptxgenjs · resvg
  ppt-skill/assets/     브랜드 에셋
  .env.example          → .env 로 복사해 키 입력
  README_실행방법.txt

왜 onedir인가: onefile은 실행할 때마다 수백 MB를 임시 폴더에 풀어서 시작이 느리고,
Node를 옆에 두는 구조와도 맞지 않는다. 인수인계는 폴더째 전달이 낫다.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

def _utf8_console():
    """윈도우 콘솔 기본 인코딩(cp949)에서 한글·기호가 깨지지 않게."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_utf8_console()

APP_NAME = "GambaLabsOffice"
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(DIST, APP_NAME)

# exe에 함께 넣을 읽기 전용 리소스 (소스경로, 번들 안 경로)
DATAS = [
    ("app/ui", "app/ui"),
    ("ppt-skill/assets", "ppt-skill/assets"),
    ("app/ppt/render_deck.js", "app/ppt"),
    ("app/ppt/freeform_helpers.js", "app/ppt"),
    ("src/vector/_svg_raster.js", "src/vector"),
    ("ppt-skill/examples/build_samples.js", "ppt-skill/examples"),
    (".env.example", "."),          # 첫 저장 때 주석 있는 뼈대로 쓴다
    ("assets", "assets"),           # 영수증 표준 양식 · 보고서 도식
]

# 정적 분석으로 안 잡히는 것들(지연 import·플러그인)
HIDDEN = [
    "webview.platforms.edgechromium",
    "pillow_heif", "pillow_avif",
    "openpyxl.chart", "openpyxl.drawing.image",
    "pptx", "docx", "pandas", "vtracer",
    "src.common.envfile",          # 지연 import(설정 저장)
]

# 안 쓰는데 딸려 들어와 용량만 키우는 것들
EXCLUDE = [
    "tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6",
    "notebook", "IPython", "jupyter", "pytest", "sphinx",
]

# exe 옆에 그대로 복사할 것들(런타임에 읽고 쓰는 것 · Node)
SIDECAR_DIRS = ["node_modules"]
SIDECAR_FILES = [".env.example", "package.json", "package-lock.json"]


def sh(cmd, **kw):
    print("  $", " ".join(cmd[:6]), "…" if len(cmd) > 6 else "")
    r = subprocess.run(cmd, cwd=ROOT, **kw)
    if r.returncode != 0:
        raise SystemExit(f"명령 실패({r.returncode}): {cmd[0]}")


def clean():
    for d in (os.path.join(ROOT, "build"), DIST):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            print("  지움:", d)


def check_prereqs():
    missing = []
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        missing.append("pyinstaller  (pip install pyinstaller)")
    if not os.path.isdir(os.path.join(ROOT, "node_modules")):
        missing.append("node_modules  (npm install)")
    if missing:
        print("빌드 전 준비가 필요합니다:")
        for m in missing:
            print("  -", m)
        raise SystemExit(1)


def run_pyinstaller():
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller",
           "--noconfirm", "--clean", "--windowed", "--onedir",
           "--name", APP_NAME,
           "--distpath", DIST,
           "--workpath", os.path.join(ROOT, "build"),
           "--specpath", os.path.join(ROOT, "build")]
    for src, dst in DATAS:
        p = os.path.join(ROOT, src)
        if not os.path.exists(p):
            print(f"  [건너뜀] 없는 리소스: {src}")
            continue
        cmd += ["--add-data", f"{p}{sep}{dst}"]
    for h in HIDDEN:
        cmd += ["--hidden-import", h]
    for e in EXCLUDE:
        cmd += ["--exclude-module", e]
    icon = os.path.join(ROOT, "app", "ui", "assets", "app.ico")
    if os.path.exists(icon):
        cmd += ["--icon", icon]
    cmd.append(os.path.join(ROOT, "app", "main_app.py"))
    sh(cmd)


def copy_sidecars(bundle_node=True):
    for d in SIDECAR_DIRS:
        src, dst = os.path.join(ROOT, d), os.path.join(OUT, d)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print("  복사:", d)
    for f in SIDECAR_FILES:
        src = os.path.join(ROOT, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(OUT, f))
            print("  복사:", f)

    if bundle_node:
        node = shutil.which("node")
        if not node:
            print("  [경고] PATH에서 node를 못 찾았습니다 → Node 번들 생략")
            return
        dst_dir = os.path.join(OUT, "runtime", "node")
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(node, os.path.join(dst_dir, os.path.basename(node)))
        print(f"  복사: runtime/node/{os.path.basename(node)}  ({os.path.getsize(node) / 1e6:.0f}MB)")


def write_readme(bundled_node: bool):
    node_line = ("Node.js가 함께 들어 있어 따로 설치할 필요가 없습니다."
                 if bundled_node else
                 "Node.js 18 이상을 먼저 설치해 주세요 (https://nodejs.org).")
    txt = f"""감바랩스 오피스 AI  —  실행 방법
made by 지우가람 (Jiwoo Garam)
=====================================================

1) 이 폴더의  {APP_NAME}.exe  를 더블클릭하면 실행됩니다.
   파이썬을 설치할 필요는 없습니다. {node_line}

2) 처음 한 번만: 같은 폴더의  .env.example  을 복사해서
   파일 이름을   .env  로 바꾸고, 메모장으로 열어 API 키를 채우세요.
   (키가 없어도 앱은 켜지지만, AI 기능은 동작하지 않습니다)

3) 만들어진 파일은 이 폴더 안  output\\  에 저장됩니다.
   앱에서 '폴더 열기' 버튼을 누르면 바로 열립니다.

4) 폴더를 통째로 다른 위치에 옮겨도 됩니다.
   단, exe만 따로 빼내면 동작하지 않습니다(옆의 파일들이 필요합니다).

문제가 생기면
---------------------------------------------------
· 창이 안 뜬다        → Microsoft Edge WebView2 런타임을 설치해 주세요.
· PPT 생성이 실패한다 → runtime\\node 와 node_modules 폴더가 있는지 확인하세요.
· AI가 응답이 없다    → .env 의 키와 인터넷 연결을 확인하세요.

폴더 구성
---------------------------------------------------
  {APP_NAME}.exe   실행 파일
  _internal\\        프로그램 내부 파일 (건드리지 마세요)
  runtime\\node\\     Node 런타임
  node_modules\\     PPT 렌더 엔진
  ppt-skill\\assets\\ 브랜드 로고·배경
  output\\           결과물 (실행하면 생깁니다)
  themes\\           직접 만든 디자인 테마 (실행하면 생깁니다)
"""
    with open(os.path.join(OUT, "README_실행방법.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    print("  작성: README_실행방법.txt")


def folder_size(path):
    total = 0
    for r, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return total


def main():
    args = set(sys.argv[1:])
    bundle_node = "--no-node" not in args

    print("감바랩스 오피스 AI — 빌드 시작")
    check_prereqs()
    if "--clean" in args:
        clean()
    print("[1/4] PyInstaller")
    run_pyinstaller()
    print("[2/4] 런타임·에셋 복사")
    copy_sidecars(bundle_node)
    print("[3/4] 실행 안내 작성")
    write_readme(bundle_node and os.path.isdir(os.path.join(OUT, "runtime", "node")))
    print("[4/4] 확인")
    exe = os.path.join(OUT, f"{APP_NAME}.exe")
    if not os.path.exists(exe):
        raise SystemExit("exe가 만들어지지 않았습니다.")
    print(f"\n완료: {OUT}")
    print(f"  크기: {folder_size(OUT) / 1e9:.2f} GB")
    print("  이 폴더째로 압축해서 전달하세요.")


if __name__ == "__main__":
    main()

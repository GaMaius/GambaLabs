# -*- coding: utf-8 -*-
"""감바랩스 오피스 AI 데스크톱 앱 — pywebview 진입점.

실행: python -m app.main_app   (프로젝트 루트에서)
패키징: pyinstaller (--add-data 로 app/ui, ppt-skill/assets 포함)
"""
import os
import sys
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))

from src.common import paths

# pywebview가 WebView2 네이티브 창 속성을 훑다 내는 무해한 재귀/COM 오류 로그를 잠재움
# (window.native.* / E_NOINTERFACE / maximum recursion depth — 기능과 무관, 콘솔·CPU만 낭비)
logging.getLogger("pywebview").setLevel(logging.CRITICAL)

try:
    from dotenv import load_dotenv
    load_dotenv(paths.env_file())
except Exception:
    pass

import webview
from app.api import Api

UI = os.path.join(paths.UI_DIR, "index.html")


def selftest() -> int:
    """창을 띄우지 않고 환경을 점검해 output/_selftest.txt 에 적는다.

        GambaLabsOffice.exe --selftest

    빌드본은 콘솔이 없어서 문제가 생겨도 원인이 안 보인다. 실행이 안 될 때
    이걸 돌려서 나온 파일을 보내 달라고 하면 바로 진단이 된다.
    """
    lines = ["감바랩스 오피스 AI — 자체 점검", "made by 지우가람 (Jiwoo Garam)", "=" * 46]
    ok = True

    for k, v in paths.describe().items():
        lines.append(f"{k:12} {v}")
    lines.append("-" * 46)

    def check(label, cond, hint=""):
        nonlocal ok
        lines.append(f"[{'OK ' if cond else '실패'}] {label}" + ("" if cond else f"  → {hint}"))
        ok = ok and bool(cond)

    check("UI 파일", os.path.exists(UI), f"{UI} 없음")
    check("브랜드 에셋", os.path.exists(os.path.join(paths.ASSETS_DIR, "backgrounds", "band.png")),
          "ppt-skill/assets 누락")
    check("렌더러 JS", os.path.exists(os.path.join(paths.RES_DIR, "app", "ppt", "render_deck.js")))
    check("Node 준비", paths.node_ready(), "runtime/node 와 node_modules 를 확인하세요")

    if paths.node_ready():
        import subprocess
        try:
            r = subprocess.run([paths.node_exe(), "-e",
                                "require('pptxgenjs');console.log('ok')"],
                               cwd=paths.node_cwd(), capture_output=True, text=True, timeout=60)
            check("pptxgenjs 로드", r.returncode == 0 and "ok" in (r.stdout or ""),
                  (r.stderr or "")[-160:])
        except Exception as e:
            check("pptxgenjs 로드", False, str(e)[:160])

    try:
        paths.ensure_dirs()
        probe = os.path.join(paths.OUTPUT_DIR, "_write_test.tmp")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        check("출력 폴더 쓰기", True)
    except Exception as e:
        check("출력 폴더 쓰기", False, str(e)[:160])

    check("API 키", Api._has_key(), "앱의 '🔑 API 키 설정'에서 키를 입력하세요")

    lines += ["-" * 46, "결과: " + ("모두 정상" if ok else "문제 있음 — 위 '실패' 항목 확인")]
    report = "\n".join(lines)
    try:
        os.makedirs(paths.OUTPUT_DIR, exist_ok=True)
        out = os.path.join(paths.OUTPUT_DIR, "_selftest.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        report += f"\n\n저장: {out}"
    except Exception:
        pass
    try:
        print(report)          # --windowed 빌드에서는 stdout이 없을 수 있다
    except Exception:
        pass
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--vtrace" in sys.argv:
        # 빌드본에는 python.exe가 없다. 벡터 변환을 별도 프로세스로 돌리려면
        # (중지 버튼으로 kill 해야 하므로) exe가 자기 자신을 작업자로 재실행한다.
        i = sys.argv.index("--vtrace")
        job = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        from app.ppt import _vtrace_run
        raise SystemExit(_vtrace_run.run_job(job))
    api = Api()
    window = webview.create_window(
        "GambaLabs Office",
        UI,
        js_api=api,
        width=1180,
        height=820,
        min_size=(940, 660),
        background_color="#191817",
    )
    api._window = window   # 밑줄 필수: pywebview가 native 그래프를 재귀 훑는 것 방지(응답없음 해결)
    webview.start()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""감바랩스 오피스 AI 데스크톱 앱 — pywebview 진입점.

실행: python -m app.main_app   (프로젝트 루트에서)
패키징: pyinstaller (--add-data 로 app/ui, ppt-skill/assets 포함)
"""
import os
import sys
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(HERE)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# pywebview가 WebView2 네이티브 창 속성을 훑다 내는 무해한 재귀/COM 오류 로그를 잠재움
# (window.native.* / E_NOINTERFACE / maximum recursion depth — 기능과 무관, 콘솔·CPU만 낭비)
logging.getLogger("pywebview").setLevel(logging.CRITICAL)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_DIR, ".env"))
except Exception:
    pass

import webview
from app.api import Api

UI = os.path.join(HERE, "ui", "index.html")


def main():
    api = Api()
    window = webview.create_window(
        "감바랩스 오피스 AI",
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

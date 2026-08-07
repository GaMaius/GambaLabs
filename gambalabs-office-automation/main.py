# -*- coding: utf-8 -*-
"""감바랩스 오피스 LLM 자동화 — 개발용 CLI.

평소 사용은 데스크톱 앱(run_app.bat / GambaLabsOffice.exe)으로 한다.
이 CLI는 UI 없이 엔진만 돌려 볼 때 쓴다.

  python main.py excel "서버 임차비 200만원 추가" --dashboard my.xlsx
  python main.py ppt  문서.md  --out 덱.pptx
  python main.py paths
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _s in (sys.stdout, sys.stderr):        # 윈도우 콘솔(cp949)에서 한글 깨짐 방지
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.common import paths

try:
    from dotenv import load_dotenv
    load_dotenv(paths.env_file())
except Exception:
    pass


def cmd_excel(args):
    from src.excel.llm_extractor import LLMExtractor
    from src.excel.excel_updater import ExcelUpdater

    req = args.request
    request_text = open(req, "r", encoding="utf-8").read() if os.path.exists(req) else req
    dashboard = args.dashboard
    if not dashboard or not os.path.exists(dashboard):
        print("대상 .xlsx 를 --dashboard 로 지정하세요.")
        return 2
    out = args.output or os.path.join(paths.OUTPUT_DIR, "updated_dashboard.xlsx")

    updates = LLMExtractor().extract_updates(request_text, dashboard)
    print(f"추출된 셀 업데이트 ({len(updates)}건):")
    for u in updates:
        print(f"  - {u['sheet_name']} / {u['item_name']} / {u['column_name']} → {u['new_value']}")
    for lg in ExcelUpdater().apply_updates(dashboard, updates, out):
        print("  *", lg)
    print(f"저장: {out}  (사람이 검토 후 공유)")
    return 0


def cmd_ppt(args):
    from app.ppt.ppt_engine import generate
    doc = os.path.abspath(args.document)
    if not os.path.exists(doc):
        print(f"문서를 찾을 수 없습니다: {doc}")
        return 2
    out = args.out or os.path.join(paths.OUTPUT_DIR, "deck.pptx")
    print("생성:", generate(doc, out, theme=args.theme))
    return 0


def cmd_paths(args):
    for k, v in paths.describe().items():
        print(f"  {k:10} {v}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="감바랩스 오피스 LLM 자동화 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("excel", help="자연어 요청 → 대시보드 업데이트(수식·차트 보존)")
    pe.add_argument("request", help="요청 텍스트 또는 요청 파일 경로")
    pe.add_argument("--dashboard", required=True, help="대상 .xlsx")
    pe.add_argument("--output", help="출력 .xlsx 경로")
    pe.set_defaults(func=cmd_excel)

    pp = sub.add_parser("ppt", help="문서(md/txt) → 브랜드 .pptx")
    pp.add_argument("document", help="PPT로 만들 문서 경로")
    pp.add_argument("--out", help="출력 .pptx 경로")
    pp.add_argument("--theme", default="gamba", help="gamba | light | none | 사용자 테마 id")
    pp.set_defaults(func=cmd_ppt)

    pd = sub.add_parser("paths", help="경로·Node 준비 상태 진단")
    pd.set_defaults(func=cmd_paths)

    args = ap.parse_args()
    print("=" * 56)
    print("  Gamba Labs Office AI  ·  made by 지우가람 (Jiwoo Garam)")
    print("=" * 56)
    raise SystemExit(args.func(args) or 0)


if __name__ == "__main__":
    main()

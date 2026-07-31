# -*- coding: utf-8 -*-
"""감바랩스 오피스 LLM 자동화 — 통합 CLI.

서브커맨드:
  excel    자연어 요청으로 대시보드 업데이트 (수식·차트 보존)
  monitor  감시 폴더 기반 감지→확인→실행 오케스트레이터(데모)
  ppt      문서를 PPT 스킬(Codex) 제작으로 넘기는 핸드오프 안내

예:
  python main.py excel planing/sample_update_requests.txt
  python main.py excel "서버 임차비 200만원 추가" --dashboard my.xlsx
  python main.py monitor --once
  python main.py ppt gambalabs_tech_presentation.md
"""
import os
import sys
import argparse

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
TEST_ROOT = os.path.dirname(PROJECT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_DIR, ".env"))
except Exception:
    pass


def cmd_excel(args):
    from src.excel.llm_extractor import LLMExtractor
    from src.excel.excel_updater import ExcelUpdater

    req = args.request
    request_text = open(req, "r", encoding="utf-8").read() if os.path.exists(req) else req
    dashboard = args.dashboard or os.path.join(TEST_ROOT, "planing", "sample_gambalabs_dashboard.xlsx")
    out = args.output or os.path.join(PROJECT_DIR, "output", "updated_gambalabs_dashboard.xlsx")

    updates = LLMExtractor().extract_updates(request_text, dashboard)
    print(f"추출된 셀 업데이트 ({len(updates)}건):")
    for u in updates:
        print(f"  - {u['sheet_name']} / {u['item_name']} / {u['column_name']} → {u['new_value']}")
    logs = ExcelUpdater().apply_updates(dashboard, updates, out)
    print("적용 이력:")
    for lg in logs:
        print("  *", lg)
    print(f"✅ 저장: {out}  (사람이 검토 후 OneDrive/Teams 업로드)")


def cmd_ppt(args):
    doc = os.path.abspath(args.document)
    skill_dir = os.path.join(PROJECT_DIR, "ppt-skill")
    print("PPT는 에이전트+스킬(B형태)로 제작됩니다. 아래 폴더를 Codex에서 열고 지시하세요:")
    print(f"  스킬 패키지: {skill_dir}")
    print(f"  지시 예:  \"{doc}\" 이 문서로 감바랩스 발표자료 만들어줘.")
    print("  (Codex가 AGENTS.md/GAMBALABS_PPT_GUIDE.md를 읽고 테마·자산으로 브랜드 덱 생성)")


def main():
    ap = argparse.ArgumentParser(description="감바랩스 오피스 LLM 자동화 통합 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("excel", help="자연어 요청 → 대시보드 업데이트(수식·차트 보존)")
    pe.add_argument("request", help="요청 텍스트 또는 요청 파일 경로")
    pe.add_argument("--dashboard", help="대상 .xlsx (기본: 샘플 대시보드)")
    pe.add_argument("--output", help="출력 .xlsx 경로")
    pe.set_defaults(func=cmd_excel)

    pp = sub.add_parser("ppt", help="문서를 PPT 스킬(Codex) 제작으로 핸드오프")
    pp.add_argument("document", help="PPT로 만들 문서 경로")
    pp.set_defaults(func=cmd_ppt)

    args = ap.parse_args()
    print("=" * 60)
    print("  [Gamba Labs] Office LLM Automation")
    print("=" * 60)
    args.func(args)


if __name__ == "__main__":
    main()

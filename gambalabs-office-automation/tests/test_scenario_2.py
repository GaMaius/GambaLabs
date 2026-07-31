# -*- coding: utf-8 -*-
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
sys.path.insert(0, project_dir)

import openpyxl
from src.excel.llm_extractor import LLMExtractor
from src.excel.excel_updater import ExcelUpdater


def run_test():
    print("=== [Test Scenario 2] Excel 수식·차트 보존 대시보드 업데이트 ===")
    test_root = os.path.dirname(project_dir)
    sample_request_file = os.path.join(test_root, "planing", "sample_update_requests.txt")
    excel_file = os.path.join(test_root, "planing", "sample_gambalabs_dashboard.xlsx")
    output_excel = os.path.join(project_dir, "output", "updated_gambalabs_dashboard.xlsx")

    with open(sample_request_file, "r", encoding="utf-8") as f:
        request_text = f.read()

    # 1. 추출 (워크북 구조 문맥 전달 → 일반화)
    extractor = LLMExtractor()
    updates = extractor.extract_updates(request_text, excel_file)
    print(f"추출된 셀 업데이트 ({len(updates)}건):")
    for u in updates:
        print(f"  - {u.get('sheet_name')} / {u.get('item_name')} / {u.get('column_name')} → {u.get('new_value')}")
    assert updates, "추출 결과가 비어 있습니다 (LLM 키 설정 또는 폴백 확인)."

    # 2. 적용 (수식·차트 보존)
    updater = ExcelUpdater()
    logs = updater.apply_updates(excel_file, updates, output_excel)
    print("적용 이력:")
    for log in logs:
        print("   *", log)

    # 3. 검증 — 파일 존재 + 수식 보존 + 차트 보존
    assert os.path.exists(output_excel), "출력 파일이 없습니다."
    wb = openpyxl.load_workbook(output_excel, data_only=False)

    ws_cost = wb["연구비_집행내역"]
    assert str(ws_cost["B6"].value).startswith("=SUM"), "SUM 수식이 보존되지 않았습니다."
    assert str(ws_cost["D2"].value) == "=B2-C2", "잔여예산 수식이 보존되지 않았습니다."

    ws_dash = wb["요약_대시보드"]
    assert len(ws_dash._charts) >= 1, "대시보드 차트가 보존되지 않았습니다."

    print("검증 통과: 수식(SUM/산술) 및 차트 객체 보존 확인.")
    print(f"=== [Scenario 2 SUCCESS] {output_excel} ===\n")
    return output_excel


if __name__ == "__main__":
    run_test()

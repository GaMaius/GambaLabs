# -*- coding: utf-8 -*-
"""감바랩스 실험 로거 — 실험 스크립트에 한 줄로 심어 결과를 자동 기록.

사용 예 (실험 스크립트 안에서):
    from gamba_log import log_result
    log_result({"정확도(%)": 92.3, "SNR(dB)": -20, "오인식(건)": 1, "비고": "튜닝"})

- 기본 트래커: ./experiment_tracker.xlsx  (없으면 자동 생성, 있으면 누적)
- 기록할 때마다 추이 차트가 자동으로 다시 그려진다(데이터 늘면 차트도 커짐).
- 수식/차트/서식은 보존(openpyxl).
"""
import os
import sys
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _ensure_tracker(path, metrics, sheet):
    if os.path.exists(path):
        return
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    extra = [k for k in metrics.keys() if k not in ("회차", "날짜")]
    ws.append(["회차", "날짜"] + extra)
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    wb.save(path)


def log_result(metrics: dict, tracker: str = "experiment_tracker.xlsx", sheet: str = "실험기록") -> dict:
    """결과 dict를 트래커에 한 행 추가하고 차트를 갱신한다(제자리 저장·누적)."""
    from src.excel.experiment_logger import ExperimentLogger
    _ensure_tracker(tracker, metrics, sheet)
    res = ExperimentLogger(sheet).append_row(tracker, metrics)
    print(f"[gamba_log] {os.path.basename(tracker)} ← {res['total_rows']}행 기록: {metrics}")
    return res


if __name__ == "__main__":
    # 데모: 두 번 기록하면 누적 + 차트 확장
    demo = os.path.join(_HERE, "output", "demo_tracker.xlsx")
    if os.path.exists(demo):
        os.remove(demo)
    log_result({"정확도(%)": 88.5, "SNR(dB)": -10, "오인식(건)": 0, "비고": "초기"}, tracker=demo)
    log_result({"정확도(%)": 91.2, "SNR(dB)": -18, "오인식(건)": 1, "비고": "튜닝"}, tracker=demo)
    log_result({"정확도(%)": 93.0, "SNR(dB)": -22, "오인식(건)": 0, "비고": "증강"}, tracker=demo)

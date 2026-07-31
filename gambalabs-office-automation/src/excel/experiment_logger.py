# -*- coding: utf-8 -*-
"""실험/재무 결과 기록 + 자동 차트 엔진.

자연어 결과 설명("4회차 정확도 92.3%, SNR -20dB, 오인식 1건")을 트래커 시트에
한 줄로 기록하고, 추이 차트를 데이터 증가에 맞춰 자동으로 다시 그린다.
수식이 있는 셀은 건드리지 않는다(수식 보호는 excel_updater와 동일 철학).
"""
import os
import re
import datetime
from typing import List, Dict, Any, Optional

import openpyxl
from openpyxl.chart import LineChart, Reference


class ExperimentLogger:
    def __init__(self, sheet_name: Optional[str] = None):
        self.sheet_name = sheet_name

    def _sheet(self, wb):
        if self.sheet_name and self.sheet_name in wb.sheetnames:
            return wb[self.sheet_name]
        return wb.worksheets[0]

    def parse_result(self, text: str, headers: List[str], next_round: int) -> List[Any]:
        row = []
        for h in headers:
            hs = str(h or "")
            key = re.sub(r"\(.*?\)|\s|%|건|회", "", hs)  # 단위 제거
            if "회차" in hs:
                m = re.search(r"(\d+)\s*회", text)
                row.append(int(m.group(1)) if m else next_round)
            elif "날짜" in hs or "일자" in hs:
                row.append(datetime.date.today().isoformat())
            elif key and re.search(re.escape(key) + r"\s*(-?[\d.]+)", text):
                v = re.search(re.escape(key) + r"\s*(-?[\d.]+)", text).group(1)
                row.append(float(v) if "." in v else int(v))
            else:
                # 헤더명이 텍스트에 없으면: 비고류엔 원문 일부, 그 외 공란
                row.append("" if ("비고" in hs or "메모" in hs) else None)
        return row

    def _rebuild_chart(self, ws, n_data: int, value_col: int = 3, cat_col: int = 1, anchor: str = "H2"):
        ws._charts = []  # 기존 차트 제거 후 재생성(범위 자동 확장)
        chart = LineChart()
        chart.title = "추이"
        chart.height, chart.width = 8, 18
        chart.y_axis.majorGridlines = None
        data = Reference(ws, min_col=value_col, min_row=1, max_row=1 + n_data)
        cats = Reference(ws, min_col=cat_col, min_row=2, max_row=1 + n_data)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        if chart.series:
            chart.series[0].graphicalProperties.line.solidFill = "0038A3"
            chart.series[0].graphicalProperties.line.width = 28000
        ws.add_chart(chart, anchor)

    @staticmethod
    def _clean(s: str) -> str:
        return re.sub(r"\(.*?\)|\s|%|건|회", "", str(s or ""))

    def _row_from_dict(self, headers, data: Dict[str, Any], next_round: int):
        clean_data = {self._clean(k): v for k, v in data.items()}
        row = []
        for h in headers:
            hs = str(h or "")
            if "회차" in hs:
                row.append(data.get(h) or clean_data.get(self._clean(h)) or next_round)
            elif "날짜" in hs or "일자" in hs:
                row.append(data.get(h) or clean_data.get(self._clean(h)) or datetime.date.today().isoformat())
            else:
                row.append(clean_data.get(self._clean(h), ""))
        return row

    @staticmethod
    def _value_col_index(ws, headers) -> int:
        """차트에 쓸 수치 컬럼(첫 숫자형 열, 회차/날짜 제외)."""
        for ci in range(2, len(headers) + 1):
            v = ws.cell(row=2, column=ci).value if ws.max_row >= 2 else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return ci
        return min(3, len(headers))

    def append_row(self, xlsx_path: str, data: Dict[str, Any], output_path: str = None) -> Dict[str, Any]:
        """구조화된 dict를 트래커에 한 행 추가(파서 없이). 스크립트 연동용."""
        wb = openpyxl.load_workbook(xlsx_path)
        ws = self._sheet(wb)
        headers = [c.value for c in ws[1]]
        row = self._row_from_dict(headers, data, ws.max_row)
        ws.append(row)
        n_data = ws.max_row - 1
        self._rebuild_chart(ws, n_data, value_col=self._value_col_index(ws, headers))
        out = output_path or xlsx_path  # 기본은 제자리 업데이트(누적)
        wb.save(out)
        return {"sheet": ws.title, "appended": dict(zip([str(h) for h in headers], row)), "total_rows": n_data, "out": out}

    def append_result(self, xlsx_path: str, description: str, output_path: str,
                      value_col: int = 3) -> Dict[str, Any]:
        wb = openpyxl.load_workbook(xlsx_path)
        ws = self._sheet(wb)
        headers = [c.value for c in ws[1]]
        data_rows = ws.max_row - 1
        row = self.parse_result(description, headers, next_round=data_rows + 1)
        ws.append(row)
        n_data = ws.max_row - 1
        self._rebuild_chart(ws, n_data, value_col=value_col)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        wb.save(output_path)
        return {"sheet": ws.title, "appended": dict(zip([str(h) for h in headers], row)),
                "total_rows": n_data, "out": output_path}


def create_sample(path: str):
    """데모용 실험 트래커 생성(데이터 + 라인차트)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "실험기록"
    ws.append(["회차", "날짜", "정확도(%)", "SNR(dB)", "오인식(건)", "비고"])
    rows = [
        [1, "2026-07-01", 88.5, -10, 0, "초기 모델"],
        [2, "2026-07-08", 90.1, -15, 1, "하이퍼파라미터 튜닝"],
        [3, "2026-07-15", 91.4, -18, 0, "데이터 증강"],
    ]
    for r in rows:
        ws.append(r)
    ExperimentLogger()._rebuild_chart(ws, len(rows))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb.save(path)
    return path


if __name__ == "__main__":
    import sys
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sample = os.path.join(base, "planing", "sample_experiment_log.xlsx")
    if not os.path.exists(sample) or "--recreate" in sys.argv:
        print("샘플 생성:", create_sample(sample))
    out = os.path.join(base, "output", "experiment_logged.xlsx")
    res = ExperimentLogger().append_result(sample, "4회차 정확도 92.3%, SNR -20dB, 오인식 1건, 노이즈 강인성 개선", out)
    import json
    print(json.dumps(res, ensure_ascii=False, indent=2))

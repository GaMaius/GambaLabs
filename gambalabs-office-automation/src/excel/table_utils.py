# -*- coding: utf-8 -*-
"""워크시트에서 표의 '헤더 행'을 자동 감지.

실무 엑셀은 헤더가 항상 1행이 아니다 — 제목 줄·빈 줄·안내 문구 뒤 3~4행부터
표가 시작하기도 한다. 상단 몇 행을 훑어 '헤더처럼 생긴 행'(대부분 문자열이고,
바로 아래에 데이터가 이어지는 행)을 찾아 header_row를 반환한다.

기존 코드는 ws[1](1행)을 헤더로 가정했다. 이 유틸을 쓰면 1행 헤더는 그대로 1을
반환하므로(가장 이른 행 우선), 동작이 바뀌지 않으면서 지저분한 시트도 지원한다.
"""
from typing import List, Tuple, Any


def _nonempty(cells):
    return [c for c in cells if c not in (None, "")]


def detect_header_row(ws, scan: int = 15) -> int:
    """상단 scan행 중 헤더일 확률이 가장 높은 행 번호(1-base). 못 찾으면 1.

    주의: openpyxl은 존재 범위 밖 셀을 '읽기'만 해도 빈 셀을 생성해 max_row를 부풀린다.
    (그러면 이후 append 위치가 어긋난다.) 그래서 max_row/max_column을 한 번만 캐시하고
    그 경계 안에서만 접근한다."""
    mr = ws.max_row or 0
    if mr < 1:
        return 1
    mc = min(ws.max_column or 1, 40)
    best_row, best_score = 1, float("-inf")
    for r in range(1, min(mr, scan) + 1):
        row = [ws.cell(row=r, column=c).value for c in range(1, mc + 1)]
        ne = _nonempty(row)
        if len(ne) < 2:                     # 제목 한 줄(셀 1개) 등은 헤더 아님
            continue
        strc = sum(1 for c in ne if isinstance(c, str) and str(c).strip())
        nxt_num = 0
        if r + 1 <= mr:                     # 경계 밖 접근 금지(max_row 부풀림 방지)
            nxt = [ws.cell(row=r + 1, column=c).value for c in range(1, mc + 1)]
            nxt_num = sum(1 for c in nxt if isinstance(c, (int, float)) and not isinstance(c, bool))
        # 문자열 개수 + 채움도 + (아래 행에 숫자 데이터가 있으면 가점) — 헤더 신호
        score = strc + len(ne) * 0.4 + (2.5 if nxt_num else 0)
        if score > best_score:              # 동점이면 더 이른(위쪽) 행 유지
            best_score, best_row = score, r
    if best_row >= mr:                       # 헤더가 마지막 행이면(데이터 없음) 안전 폴백
        return 1
    return best_row


def detect_table(ws, scan: int = 15) -> Tuple[int, List[Any], int]:
    """(header_row, headers, first_data_row) 반환. headers는 뒤쪽 빈 칸을 잘라낸 목록."""
    hr = detect_header_row(ws, scan)
    max_c = min(ws.max_column or 1, 60)
    headers = [ws.cell(row=hr, column=c).value for c in range(1, max_c + 1)]
    while headers and headers[-1] in (None, ""):
        headers.pop()
    return hr, headers, hr + 1

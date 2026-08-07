# -*- coding: utf-8 -*-
"""감바랩스 10회차 랜덤 실험 자동 로깅 데모 (print() 가로채기 방식)

실행 방법:
    python tests/test_experiment_log.py
"""
import os
import sys
import time
import random

# 프로젝트 루트 경로 설정 및 gamba_log 모듈 로드
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from gamba_log import enable_print_logger

# 자동 기록될 엑셀 트래커 경로
TRACKER_PATH = os.path.join(ROOT_DIR, "output", "excel", "tracker", "log.xlsx")

print("=" * 65)
print("[START] 실험 기록 연동 시작")
print(f"저장 대상 엑셀: {TRACKER_PATH}")
print("=" * 65)

enable_print_logger(tracker=TRACKER_PATH, sheet="실험기록")

# 10회차 가상 반복 실험 루프
for epoch in range(1, 11):
    # 매 회차마다 무작위 실험 수치 생성
    acc = round(random.uniform(85.0, 99.5), 1)
    snr = random.choice([-25, -20, -15, -10, -5, 0])
    loss = round(random.uniform(0.01, 0.45), 3)
    err = random.randint(0, 4)
    memo = f"튜닝 회차_{epoch}"

    time.sleep(0.15)  # 학습 시간 시뮬레이션

    # 🌟 개발자는 기존 코드 그대로 print()만 출력하면 됩니다!
    print(f"Epoch {epoch}/10 - accuracy: {acc}% snr: {snr}dB loss: {loss} 오인식: {err}건 ({memo})")

print("\n" + "=" * 65)
print("[SUCCESS] 10회차 실험 출력 및 엑셀 자동 기록이 완료되었습니다!")
print(f"엑셀 파일 확인: {TRACKER_PATH}")
print("=" * 65)

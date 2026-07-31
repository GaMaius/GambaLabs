# -*- coding: utf-8 -*-
"""발표자료 '설계 방침' 분리 — 모델 급에 따라 다른 정책을 쓴다.

배경: 약한 로컬 모델(3b/7b)은 스스로 레이아웃을 잘 설계 못 해서 템플릿 규칙·후처리로
'대신 판단'해줘야 안정적이다. 반대로 강한 모델(회사 GPT/Claude)은 그 판단을 더 잘 하므로
같은 제약을 씌우면 오히려 품질이 깎인다(과제약의 역설).

그래서 설계 강도를 두 모드로 분리하고, 모델 급으로 자동 선택한다(수동 오버라이드 가능).

  - "template" (약한/로컬 모델): 강한 가드레일
        · 프롬프트에 슬라이드 1:1 매핑·유형 강제 규칙을 상세히
        · 후처리(_normalize)에서 지시문구 제거·카드 자동변환·빈 슬라이드 정리 등 적극 개입
  - "freeform" (강한/클라우드 모델): 모델을 신뢰
        · 프롬프트는 목표·스키마만 주고 설계는 모델에 위임(잔소리 최소)
        · 후처리는 형식 검증·빈 값 제거 등 '안전' 수준만(내용 재구성 안 함)
        · 렌더는 여전히 결정적(render_deck.js) — 코드 실행 위험 없이 자유도만 올림

전환:
  환경변수 PPT_DESIGN_MODE = auto(기본) | template | freeform
  auto일 때: 강한 클라우드 모델로 판단되면 freeform, 아니면 template.

※ 향후(로드맵): freeform을 더 밀어 '모델이 pptxgenjs 코드를 직접 생성 → 검증(validate) 후 렌더'
   단계까지 확장하면 클로드 버전급 자유설계가 가능. 지금은 안전을 위해 플랜→결정적 렌더 유지.
"""
import os

# 강한(클라우드) 모델로 볼 이름 힌트
_STRONG_HINTS = ("gpt-4", "gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3", "o4",
                 "claude", "sonnet", "opus", "gemini")


def is_local_endpoint() -> bool:
    base = (os.getenv("OPENAI_BASE_URL") or "").lower()
    return any(k in base for k in ("localhost", "127.0.0.1", "0.0.0.0", "11434", "ollama"))


def is_strong_model() -> bool:
    """비(非)로컬 엔드포인트 + 강한 모델명이면 강한 모델로 간주."""
    model = (os.getenv("OPENAI_MODEL") or "").lower()
    return (not is_local_endpoint()) and any(h in model for h in _STRONG_HINTS)


def design_mode() -> str:
    """현재 설계 방침: 'template' 또는 'freeform'. env로 강제 가능."""
    m = (os.getenv("PPT_DESIGN_MODE") or "auto").strip().lower()
    if m in ("template", "freeform"):
        return m
    return "freeform" if is_strong_model() else "template"


def is_strict() -> bool:
    """후처리를 적극 개입(strict)할지 여부. template=적극, freeform=안전수준만."""
    return design_mode() == "template"

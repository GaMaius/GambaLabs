# -*- coding: utf-8 -*-
"""AI 대화형 PPT 제작 에이전트 (스킬의 상담 워크플로우).

LLM이 필요한 것만 사용자에게 '질문'하고, 준비되면 '샘플 2장'을 제안해 확인받은 뒤
'전체'를 만든다. 매 턴 아래 JSON 하나만 반환한다:
  {"type":"question","text":"...","options":["...","기타"]}
  {"type":"sample","message":"...","plan":{PLAN}}
  {"type":"final","message":"...","plan":{PLAN}}
색·폰트·레이아웃(브랜드 테마)은 렌더러가 고정하므로 PLAN에 색을 넣지 않는다.
LLM 백엔드는 OpenAI 호환(.env: 데모=로컬 Ollama, 운영=GPT).
"""
import os
import re
import json
from typing import Dict, Any, List

SYSTEM = """너는 '감바랩스' 브랜드 발표자료 제작을 돕는 상담 에이전트다.
브랜드 테마(딥네이비/화이트, HY견고딕/맑은고딕, 헤더밴드·아치·사운드링 모티프)는
렌더러가 자동 적용하니 색/비율/폰트는 절대 묻지 말고 PLAN에도 넣지 마라.

진행 방식:
1) 내용 구성에 꼭 필요한 것만 1~2개씩 사용자에게 질문한다(예: 핵심 메시지, 대상 청중,
   특정 슬라이드를 표/카드/차트 중 무엇으로 할지, 강조점). 선택지를 줄 땐 항상 "기타"를 포함한다.
2) 방향이 잡히면 샘플 2장(type=sample)을 제안하고 확인받는다.
3) 사용자가 좋다고 하면 전체(type=final)를 만든다. 수정 요청이면 다시 질문/샘플로.

반드시 매 응답은 아래 셋 중 하나의 JSON '한 개'만 출력(설명·코드펜스 금지):
{"type":"question","text":"질문","options":["A","B","기타"]}
{"type":"sample","message":"샘플 2장입니다. 이대로 진행할까요?","plan":{PLAN}}
{"type":"final","message":"완성했습니다","plan":{PLAN}}

PLAN 스키마:
{"title":"표지 제목","subtitle":"부제","slides":[
  {"type":"content","title":"제목","lead":"한줄 요지","bullets":[{"text":"내용","emphasis":true|false}],
   "chart":{"kind":"bar|pie|line","cats":["A","B"],"vals":[1,2]},
   "image":{"query":"영문/한글 검색어","mode":"background|region","transparency":0}},
  {"type":"cards","title":"...","items":["항목1","항목2"]},
  {"type":"table","title":"...","rows":[["헤더1","헤더2"],["a","b"]]},
  {"type":"text","title":"...","bullets":["줄1","줄2"]}
]}
chart/image는 필요할 때만. sample은 slides 2장, final은 표지 제외 3~8장 권장."""


class PPTChatAgent:
    def __init__(self):
        from openai import OpenAI
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "ollama",
                             base_url=os.getenv("OPENAI_BASE_URL"))
        self.messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM}]

    def _parse(self, txt: str) -> Dict[str, Any]:
        txt = txt.strip()
        txt = re.sub(r"^```(json)?|```$", "", txt, flags=re.M).strip()
        try:
            return json.loads(txt)
        except Exception:
            m = re.search(r"\{.*\}", txt, re.S)  # 본문 속 첫 JSON 덩어리
            if m:
                return json.loads(m.group(0))
            return {"type": "question", "text": txt[:300] or "조금 더 구체적으로 알려주세요.", "options": ["기타"]}

    def _turn(self) -> Dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0.3,
            response_format={"type": "json_object"},
            messages=self.messages,
        )
        content = resp.choices[0].message.content
        self.messages.append({"role": "assistant", "content": content})
        out = self._parse(content)
        if out.get("type") not in ("question", "sample", "final"):
            out = {"type": "question", "text": out.get("text", "다시 알려주세요."), "options": ["기타"]}
        return out

    def start(self, brief: str) -> Dict[str, Any]:
        self.messages.append({"role": "user", "content": f"제작 요청/자료:\n{brief}\n\n먼저 필요한 질문부터 해줘."})
        return self._turn()

    def reply(self, text: str) -> Dict[str, Any]:
        self.messages.append({"role": "user", "content": text})
        return self._turn()

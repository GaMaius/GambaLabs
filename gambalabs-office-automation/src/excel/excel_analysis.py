# -*- coding: utf-8 -*-
"""Excel → LLM 분석/요약 (역방향 시나리오).

생성된 실험/재무 엑셀을 pandas로 빠르게 읽어(집계는 pandas가 openpyxl보다 빠름)
LLM에게 근거 데이터로 넘겨 요약·추세·이상치·최적조건을 답하게 한다.
LLM 백엔드는 OpenAI 호환(.env: 로컬 Ollama/GPT).
"""
import os
from typing import Optional, Dict, Any


def build_context(xlsx_path: str, max_rows: int = 24) -> str:
    """LLM 분석용 문맥. 큰 시트는 상·하위 샘플 + 전체 통계 + 추세 요약으로 압축해
    행이 많아도 핵심 근거를 잃지 않게 한다(약한 로컬 모델도 판단하도록 결정적 요약 제공)."""
    import pandas as pd
    dfs = pd.read_excel(xlsx_path, sheet_name=None)  # 전 시트
    parts = []
    for name, df in dfs.items():
        df = df.dropna(how="all")
        parts.append(f"## 시트: {name} ({len(df)}행 × {len(df.columns)}열)")
        parts.append("컬럼: " + ", ".join(map(str, df.columns)))
        num = df.select_dtypes("number")
        if not num.empty:
            parts.append("수치 요약(전체 행 기준):\n" + num.describe().round(2).to_string())
            trends = []
            for c in num.columns:
                s = num[c].dropna()
                if len(s) >= 2:
                    d = float(s.iloc[-1]) - float(s.iloc[0])
                    arrow = "▲" if d > 0 else ("▼" if d < 0 else "→")
                    trends.append(f"{c}: {round(float(s.iloc[0]),2)}→{round(float(s.iloc[-1]),2)} ({arrow}{round(abs(d),2)})")
            if trends:
                parts.append("처음→마지막 추세: " + " | ".join(trends))
        # 큰 시트는 상·하위만 샘플(중간 생략), 작으면 전체
        if len(df) > max_rows:
            half = max_rows // 2
            parts.append(f"데이터(상위 {half}행):\n" + df.head(half).to_string(index=False))
            parts.append(f"… (중간 {len(df) - max_rows}행 생략) …")
            parts.append(f"데이터(하위 {half}행):\n" + df.tail(half).to_string(index=False))
        else:
            parts.append("데이터(전체):\n" + df.to_string(index=False))
        parts.append("")
    return "\n".join(parts)[:9000]


def analyze(xlsx_path: str, question: Optional[str] = None) -> Dict[str, Any]:
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
        return {"error": "분석은 LLM이 필요합니다(.env 키/엔드포인트)."}
    context = build_context(xlsx_path)
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "ollama", base_url=os.getenv("OPENAI_BASE_URL"))
    q = question or "이 데이터의 핵심 요약, 눈에 띄는 추세·이상치, 개선/최적 조건 제안을 간결히."
    prompt = (f"다음 엑셀 데이터를 근거로만 답하라. 표에 없는 내용은 추측하지 말 것.\n\n"
              f"[데이터]\n{context}\n\n[요청]\n{q}\n\n한국어로 불릿 위주, 간결하게.")
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"), temperature=0.3,
        messages=[{"role": "system", "content": "너는 실험·재무 데이터 분석 도우미다. 근거 기반으로 간결히 답한다."},
                  {"role": "user", "content": prompt}])
    return {"answer": resp.choices[0].message.content, "preview": context[:600]}


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from src.common import paths
    load_dotenv(paths.env_file())
    if len(sys.argv) < 2:
        print("사용법: python -m src.excel.excel_analysis <파일.xlsx>")
        raise SystemExit(2)
    p = sys.argv[1]
    print("=== context ===")
    print(build_context(p)[:800])

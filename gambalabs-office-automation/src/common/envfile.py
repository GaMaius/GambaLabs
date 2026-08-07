# -*- coding: utf-8 -*-
"""앱 안에서 API 키를 읽고 저장한다(.env 파일 편집).

인수인계 대상이 메모장으로 .env를 고치게 하지 않으려고 만들었다.
exe 빌드본에서는 .env가 exe 옆에 놓이므로(paths.env_file()) 앱이 직접 쓴다.

저장하면 os.environ도 같이 갱신해서 **재시작 없이** 바로 적용된다.
llm_client는 호출할 때마다 os.getenv를 읽으므로 이걸로 충분하다.
"""
import os
import re

from src.common import paths

# 화면에 노출·편집할 항목만 다룬다(.env의 나머지 줄은 건드리지 않는다).
FIELDS = [
    ("LLM_PROVIDER", False),
    ("GROQ_API_KEY", True),
    ("GROQ_API_KEY2", True),
    ("GROQ_MODEL", False),
    ("OPENAI_API_KEY", True),
    ("OPENAI_MODEL", False),
    ("OPENAI_BASE_URL", False),
    ("PEXELS_API_KEY", True),
    ("UNSPLASH_ACCESS_KEY", True),
]
SECRET = {k for k, s in FIELDS if s}
_VALID = re.compile(r"^[A-Z0-9_]+$")


def mask(v: str) -> str:
    """키를 화면에 보여줄 때. 앞뒤만 남긴다."""
    v = (v or "").strip()
    if not v:
        return ""
    if len(v) <= 10:
        return v[:2] + "•" * max(0, len(v) - 2)
    return f"{v[:6]}{'•' * 8}{v[-4:]}"


def read_all() -> dict:
    """현재 값(환경변수 우선). 비밀 항목은 마스킹해서 돌려준다."""
    out = {}
    for k, secret in FIELDS:
        v = (os.getenv(k) or "").strip()
        out[k] = {"set": bool(v), "display": mask(v) if secret else v, "secret": secret}
    out["_path"] = paths.env_file()
    return out


def _parse(text: str):
    """.env 원문을 (줄 목록, {키: 줄번호})로."""
    lines = text.splitlines()
    index = {}
    for i, ln in enumerate(lines):
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", ln)
        if m and not ln.lstrip().startswith("#"):
            index[m.group(1)] = i
    return lines, index


def save(values: dict) -> dict:
    """받은 항목만 .env에 반영한다.

    - 값이 빈 문자열이면 '지우지 않고 그대로 둔다'(마스킹된 값을 그대로 되보내는
      실수로 키가 날아가는 걸 막는다). 지우려면 값에 "-" 를 넣는다.
    - 파일의 주석·순서·다른 항목은 보존한다.
    """
    path = paths.env_file()
    text = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    else:
        # 첫 실행: 예시 파일을 뼈대로 삼아 주석·설명을 살린다.
        for cand in (os.path.join(paths.RES_DIR, ".env.example"),
                     os.path.join(paths.APP_DIR, ".env.example")):
            if os.path.exists(cand):
                with open(cand, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                break

    lines, index = _parse(text)
    changed = []
    for k, raw in (values or {}).items():
        if not _VALID.match(str(k)) or k not in {f for f, _ in FIELDS}:
            continue
        v = str(raw if raw is not None else "").strip()
        if v == "":
            continue                       # 빈 입력 = 변경 없음
        if v == "-":
            v = ""                         # 명시적 삭제
        if "\n" in v or "\r" in v:
            continue
        line = f"{k}={v}"
        if k in index:
            lines[index[k]] = line
        else:
            lines.append(line)
        os.environ[k] = v                  # 즉시 적용(재시작 불필요)
        changed.append(k)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    _invalidate_caches()
    return {"ok": True, "path": path, "changed": changed}


def _invalidate_caches():
    """키/프로바이더가 바뀌었으니 모델 목록 캐시를 버린다."""
    try:
        from src.common import llm_client
        if hasattr(llm_client, "_groq_cache"):
            llm_client._groq_cache = (None, 0.0)
    except Exception:
        pass

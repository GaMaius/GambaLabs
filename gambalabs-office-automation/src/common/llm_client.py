# -*- coding: utf-8 -*-
"""감바랩스 LLM 팩토리 — OpenAI, Ollama, Groq (GPT OSS) 멀티 백엔드 통합 클라이언트 모듈."""

import os
from typing import Tuple, List, Dict, Any, Optional
from openai import OpenAI

# Groq 모델 목록은 API에서 실시간으로 받아온다(fetch_groq_models).
# Groq는 모델을 수시로 폐기하므로 하드코딩하면 얼마 못 가 'model_decommissioned' 400이 난다.
# 아래는 조회 실패 시에만 쓰는 폴백이다.
GROQ_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# 채팅용이 아닌 모델(음성 인식·합성, 안전 분류기)은 모델 선택 목록에서 뺀다.
_GROQ_NON_CHAT = ("whisper", "orpheus", "prompt-guard", "safeguard", "tts", "-guard-")

OLLAMA_DEFAULT_MODELS = [
    "qwen2.5:7b-instruct",
    "qwen2.5:3b",
    "llama3:8b",
]

# (모델목록, 조회시각) — 프로세스 수명 동안 캐시
_groq_cache: Tuple[Optional[List[str]], float] = (None, 0.0)
_GROQ_CACHE_TTL = 600.0


try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def groq_keys() -> List[str]:
    """쓸 수 있는 Groq 키 전부. GROQ_API_KEY, GROQ_API_KEY_2, _3 … 순서."""
    keys = []
    for name in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4"):
        v = (os.getenv(name) or "").strip()
        if v and v not in keys:
            keys.append(v)
    return keys


# 한 키가 한도에 걸리면 다음 키로 넘어가고, 성공한 키를 다음 호출의 시작점으로 삼는다.
_key_cursor = 0


def _is_switchable(err: Exception) -> bool:
    """키를 바꿔서 해결될 만한 오류인가(한도 초과·인증·일시 장애)."""
    s = str(err).lower()
    return any(t in s for t in (
        "rate_limit", "rate limit", "429", "413", "quota", "insufficient",
        "invalid api key", "invalid_api_key", "401", "403",
        "500", "502", "503", "over capacity", "overloaded"))


class _Completions:
    def __init__(self, owner):
        self._o = owner

    def create(self, **kw):
        return self._o._create(**kw)


class _Chat:
    def __init__(self, owner):
        self.completions = _Completions(owner)


class FailoverClient:
    """키를 여러 개 두고 실패하면 다음 키로 넘기는 OpenAI 호환 클라이언트.

    호출부는 그대로 `client.chat.completions.create(...)`를 쓰면 된다.
    """

    def __init__(self, keys: List[str], base_url: Optional[str], **client_kwargs):
        self._keys = keys or [""]
        self._base = base_url
        self._kw = client_kwargs
        self._cache: Dict[str, OpenAI] = {}
        self.chat = _Chat(self)

    def _client(self, key: str) -> OpenAI:
        if key not in self._cache:
            self._cache[key] = OpenAI(api_key=key or "not_set", base_url=self._base, **self._kw)
        return self._cache[key]

    def _create(self, **kw):
        global _key_cursor
        n = len(self._keys)
        last = None
        for off in range(n):
            i = (_key_cursor + off) % n
            try:
                r = self._client(self._keys[i]).chat.completions.create(**kw)
                _key_cursor = i          # 성공한 키를 다음에도 먼저 쓴다
                return r
            except Exception as e:
                last = e
                if not _is_switchable(e) or off == n - 1:
                    raise
                print(f"[llm_client] API 키 {i + 1}번 실패({str(e)[:90]}…) → {((i + 1) % n) + 1}번 키로 전환")
        raise last


def fetch_groq_models(timeout: float = 4.0, force: bool = False) -> Optional[List[str]]:
    """Groq에서 지금 실제로 쓸 수 있는 채팅 모델 목록. 실패하면 None."""
    global _groq_cache
    import time
    models, ts = _groq_cache
    if models is not None and not force and (time.time() - ts) < _GROQ_CACHE_TTL:
        return models

    keys = groq_keys() or [os.getenv("OPENAI_API_KEY") or ""]
    keys = [k for k in keys if k]
    if not keys:
        return None
    base = (os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    ids = None
    for k in keys:                      # 한 키가 죽어도 다른 키로 목록을 받는다
        try:
            import requests
            r = requests.get(base + "/models", headers={"Authorization": f"Bearer {k}"}, timeout=timeout)
            if r.status_code == 200:
                ids = [m.get("id", "") for m in r.json().get("data", [])]
                break
        except Exception:
            continue
    if ids is None:
        return None

    chat = sorted(i for i in ids if i and not any(x in i.lower() for x in _GROQ_NON_CHAT))
    if not chat:
        return None
    _groq_cache = (chat, time.time())
    return chat


def get_llm_provider() -> str:
    """현재 설정된 LLM 프로바이더 반환 ('groq', 'ollama', 'openai')"""
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider in ("groq", "ollama", "openai"):
        return provider

    # 자동 감지: GROQ_API_KEY가 존재하거나 OPENAI_BASE_URL에 groq 포함 시 Groq 우선
    base_url = os.getenv("OPENAI_BASE_URL", "")
    if os.getenv("GROQ_API_KEY") or "groq" in base_url.lower():
        return "groq"
    if base_url:
        return "ollama"
    return "openai"


def get_llm_client_and_model(
    override_api_key: Optional[str] = None,
    override_base_url: Optional[str] = None,
    override_model: Optional[str] = None
) -> Tuple[OpenAI, str]:
    """현재 프로바이더(Groq, Ollama, OpenAI)에 적합한 OpenAI 클라이언트 객체와 모델명 반환"""
    provider = get_llm_provider()

    if provider == "groq":
        base_url = override_base_url or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        model = override_model or os.getenv("GROQ_MODEL") or GROQ_DEFAULT_MODEL
        keys = [override_api_key] if override_api_key else groq_keys()
        if not keys:
            keys = [os.getenv("OPENAI_API_KEY") or "groq_key"]
        # 키가 여러 개면 한도(TPM)에 걸릴 때 자동으로 다음 키로 넘어간다.
        return FailoverClient(keys, base_url), model
    elif provider == "ollama":
        api_key = override_api_key or os.getenv("OPENAI_API_KEY") or "ollama"
        base_url = override_base_url or os.getenv("OPENAI_BASE_URL") or "http://localhost:11434/v1"
        model = override_model or os.getenv("OPENAI_MODEL") or "qwen2.5:7b-instruct"
    else:  # openai
        api_key = override_api_key or os.getenv("OPENAI_API_KEY") or "not_set"
        base_url = override_base_url or os.getenv("OPENAI_BASE_URL")  # None → 공식 OpenAI 엔드포인트
        model = override_model or os.getenv("OPENAI_MODEL", "gpt-4o")

    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


def list_available_models() -> Dict[str, Any]:
    """UI 및 시스템에 노출할 현재 백엔드 상태와 모델 옵션 목록 반환"""
    provider = get_llm_provider()
    cur_model = (os.getenv("GROQ_MODEL") or GROQ_DEFAULT_MODEL) if provider == "groq" else (os.getenv("OPENAI_MODEL") or "gpt-4o")

    options = []
    if provider == "groq":
        live = fetch_groq_models()
        if live:
            options = live
            # 설정된 모델이 폐기됐으면 목록에 끼워 넣지 말고 살아 있는 모델로 되돌린다.
            # (끼워 넣으면 죽은 모델이 계속 선택된 채로 남아 400 model_decommissioned가 난다)
            if cur_model not in options:
                cur_model = GROQ_DEFAULT_MODEL if GROQ_DEFAULT_MODEL in options else options[0]
                os.environ["GROQ_MODEL"] = cur_model
        else:
            options = list(GROQ_FALLBACK_MODELS)
            if cur_model and cur_model not in options:
                options.insert(0, cur_model)
        return {
            "provider": "groq",
            "current": cur_model,
            "options": options,
            "label": "Groq LPU (GPT OSS)"
        }
    elif provider == "ollama":
        base = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
        try:
            import requests
            r = requests.get(base.rstrip("/") + "/models", timeout=3)
            options = [m["id"] for m in r.json().get("data", [])]
        except Exception:
            options = list(OLLAMA_DEFAULT_MODELS)
        if not options:
            options = list(OLLAMA_DEFAULT_MODELS)
        if cur_model not in options:
            options.insert(0, cur_model)
        return {
            "provider": "ollama",
            "current": cur_model,
            "options": options,
            "label": "Ollama (로컬)"
        }
    else:
        options = ["gpt-4o", "gpt-4o-mini", "o3-mini"]
        if cur_model not in options:
            options.insert(0, cur_model)
        return {
            "provider": "openai",
            "current": cur_model,
            "options": options,
            "label": "OpenAI GPT"
        }

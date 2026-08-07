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


def fetch_groq_models(timeout: float = 4.0, force: bool = False) -> Optional[List[str]]:
    """Groq에서 지금 실제로 쓸 수 있는 채팅 모델 목록. 실패하면 None."""
    global _groq_cache
    import time
    models, ts = _groq_cache
    if models is not None and not force and (time.time() - ts) < _GROQ_CACHE_TTL:
        return models

    key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    base = (os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    try:
        import requests
        r = requests.get(base + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=timeout)
        if r.status_code != 200:
            return None
        ids = [m.get("id", "") for m in r.json().get("data", [])]
    except Exception:
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
        api_key = override_api_key or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or "groq_key"
        base_url = override_base_url or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        model = override_model or os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
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

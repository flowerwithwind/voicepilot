"""引擎设置服务：默认值合并、持久化、API Key 脱敏、能力探测。"""
from __future__ import annotations

from typing import Any

from app.config import ASR_ENGINE
from app.llm.client import LLMClient
from app.storage import db

MODEL_KEY = "model"
ASR_KEY = "asr"
TTS_KEY = "tts"

_DEFAULT_MODEL = {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 1024,
}

_DEFAULT_ASR = {
    "engine": ASR_ENGINE,
    "base_url": "",
    "api_key": "",
    "model": "whisper-1",
}

_DEFAULT_TTS = {
    "engine": "browser",
    "voice": "",
    "rate": 1.0,
    "pitch": 1.0,
}


def get_model_settings() -> dict[str, Any]:
    return {**_DEFAULT_MODEL, **db.get_setting(MODEL_KEY, {})}


def get_asr_settings() -> dict[str, Any]:
    return {**_DEFAULT_ASR, **db.get_setting(ASR_KEY, {})}


def get_tts_settings() -> dict[str, Any]:
    return {**_DEFAULT_TTS, **db.get_setting(TTS_KEY, {})}


def mask_api_key(key: str) -> str:
    """脱敏展示：仅保留前 4 与后 4 位，中间以星号替代。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _save(key: str, data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    cur = {**defaults, **db.get_setting(key, {})}
    allowed = {k: v for k, v in data.items() if k in cur}
    if "api_key" in allowed:
        incoming = allowed["api_key"]
        if incoming == "" or incoming == mask_api_key(cur.get("api_key", "")):
            del allowed["api_key"]
    cur.update(allowed)
    db.set_setting(key, cur)
    return cur


def save_model_settings(data: dict[str, Any]) -> dict[str, Any]:
    return _save(MODEL_KEY, data, _DEFAULT_MODEL)


def save_asr_settings(data: dict[str, Any]) -> dict[str, Any]:
    return _save(ASR_KEY, data, _DEFAULT_ASR)


def save_tts_settings(data: dict[str, Any]) -> dict[str, Any]:
    return _save(TTS_KEY, data, _DEFAULT_TTS)


def get_capabilities() -> dict[str, bool]:
    """能力探测（前端降级提示依据）。"""
    m = get_model_settings()
    return {"asr": True, "llm": bool(m.get("api_key")), "tts": True}


def build_llm_client() -> LLMClient:
    m = get_model_settings()
    return LLMClient(
        base_url=m["base_url"],
        api_key=m["api_key"],
        model=m["model"],
        temperature=float(m["temperature"]),
        max_tokens=int(m["max_tokens"]),
    )


def test_connection(data: dict[str, Any]) -> dict[str, Any]:
    """用给定配置（或当前配置）测试模型连接。"""
    cur = get_model_settings()
    incoming = {k: v for k, v in data.items() if k in cur}
    if "api_key" in incoming:
        key = incoming["api_key"]
        if key == "" or key == mask_api_key(cur.get("api_key", "")):
            del incoming["api_key"]  # 空/脱敏值视为不修改，避免用掩码串测试
    cur.update(incoming)
    client = LLMClient(
        base_url=cur["base_url"],
        api_key=cur["api_key"],
        model=cur["model"],
        temperature=float(cur["temperature"]),
        max_tokens=int(cur["max_tokens"]),
    )
    err = client.test()
    return {"ok": not err, "error": err}

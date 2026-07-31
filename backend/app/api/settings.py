"""引擎设置 API：LLM / ASR / TTS 配置，API Key 脱敏，连接测试。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.models import CapabilitiesOut, SettingsOut
from app.services import settings as settings_svc

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _masked_model() -> dict[str, Any]:
    m = settings_svc.get_model_settings()
    m["api_key"] = settings_svc.mask_api_key(m.get("api_key", ""))
    return m


def _masked_asr() -> dict[str, Any]:
    m = settings_svc.get_asr_settings()
    m["api_key"] = settings_svc.mask_api_key(m.get("api_key", ""))
    return m


@router.get("", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return SettingsOut(
        model=_masked_model(),
        asr=_masked_asr(),
        tts=settings_svc.get_tts_settings(),
        capabilities=settings_svc.get_capabilities(),
    )


@router.put("", response_model=SettingsOut)
def update_settings(body: dict[str, Any]) -> SettingsOut:
    if "model" in body:
        settings_svc.save_model_settings(body["model"])
    if "asr" in body:
        settings_svc.save_asr_settings(body["asr"])
    if "tts" in body:
        settings_svc.save_tts_settings(body["tts"])
    return get_settings()


@router.post("/test", response_model=CapabilitiesOut)
def test_connection(body: dict[str, Any]) -> dict[str, Any]:
    return settings_svc.test_connection(body.get("model") or {})

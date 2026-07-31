"""健康检查：版本与能力探测（前端降级提示依据）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import APP_NAME, ASR_ENGINE, VERSION
from app.models import HealthOut

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        status="ok",
        version=VERSION,
        app=APP_NAME,
        asr_engine=ASR_ENGINE,
        capabilities={"asr": True, "llm": False, "tts": False},
    )

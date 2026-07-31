"""Pydantic 响应模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    app: str
    asr_engine: str
    capabilities: dict[str, bool]


class TranscribeOut(BaseModel):
    text: str
    engine: str
    duration: float | None = None
    elapsed_ms: int
    session_id: int
    message_id: int


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    audio_path: str | None = None
    duration_ms: int | None = None
    created_at: str


class SessionOut(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class SessionsOut(BaseModel):
    total: int
    items: list[SessionOut]


class ErrorOut(BaseModel):
    detail: str = Field(..., description="中文错误提示")

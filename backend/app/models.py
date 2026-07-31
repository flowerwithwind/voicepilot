"""Pydantic 响应模型。"""
from __future__ import annotations

from typing import Any

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
    audio_path: str | None = None  # M4 回听


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

class ChatRequest(BaseModel):
    """聊天请求：会话 + 文本 + 工具二次确认（可选）。"""
    session_id: int | None = None
    content: str
    approval: dict[str, Any] | None = None
    save_user: bool = True  # 语音流程已由 transcribe 落库，置 False 避免重复

class CapabilitiesOut(BaseModel):
    ok: bool
    error: str | None = None


class SettingsOut(BaseModel):
    model: dict[str, Any]
    asr: dict[str, Any]
    tts: dict[str, Any]
    capabilities: dict[str, bool]

class ReminderOut(BaseModel):
    id: int
    session_id: int
    content: str
    remind_at: str
    created_at: str
    done: int = 0

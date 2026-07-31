"""VoicePilot FastAPI 应用入口。"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audio, chat, health, realtime, reminders, sessions, settings
from app.config import VERSION, ensure_dirs
from app.services import query_data
from app.storage import db
from app.utils.logging import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    db.init_db()
    query_data.init_db()
    logger.info("VoicePilot 启动完成")
    yield


def cors_origins() -> list[str]:
    """CORS 白名单：默认覆盖 Vite 开发端口 5173~5179，可用 VOICEPILOT_CORS_ORIGINS 覆盖。"""
    env = os.getenv("VOICEPILOT_CORS_ORIGINS", "").strip()
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    ports = range(5173, 5180)
    return [f"http://localhost:{p}" for p in ports] + [f"http://127.0.0.1:{p}" for p in ports]


app = FastAPI(
    title="VoicePilot API",
    description="语音实时助手后端：录音上传 → ASR 适配层 → 文本回显",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(audio.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(settings.router)
app.include_router(reminders.router)
app.include_router(realtime.router)

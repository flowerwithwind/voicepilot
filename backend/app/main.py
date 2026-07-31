"""VoicePilot FastAPI 应用入口。"""
from __future__ import annotations

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


app = FastAPI(
    title="VoicePilot API",
    description="语音实时助手后端：录音上传 → ASR 适配层 → 文本回显",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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

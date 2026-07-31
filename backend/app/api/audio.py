"""音频 API：上传录音 → ASR 转写 → 落库回显（M1 语音管道）。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import AUDIO_DIR
from app.models import TranscribeOut
from app.services.asr import ASRError, get_provider
from app.storage import db
from app.storage.files import is_allowed, safe_audio_path, safe_store
from app.utils.logging import get_logger

logger = get_logger("audio")

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.post("/transcribe", response_model=TranscribeOut)
def transcribe(
    file: Annotated[UploadFile, File(...)],
    session_id: Annotated[int | None, Form()] = None,
    duration: Annotated[float | None, Form()] = None,
) -> TranscribeOut:
    """上传一段录音，返回转写文本并写入会话消息。"""
    if file.filename is None or not is_allowed(file.filename):
        raise HTTPException(status_code=422, detail="不支持的音频格式（支持 webm/ogg/wav/mp3/m4a）")

    try:
        path, size = safe_store(file)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # 会话归属：缺省自动新建
    session = db.get_session(session_id) if session_id else None
    if session_id and session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session is None:
        session = db.create_session(title="语音会话")

    try:
        result = get_provider().transcribe(path, duration=duration)
    except ASRError as e:
        raise HTTPException(status_code=502, detail=f"语音识别失败：{e}") from e
    # M4：保留音频片段供消息回听（audio_path 为相对 AUDIO_DIR 的路径）
    message = db.add_message(
        session_id=session["id"],
        role="user",
        content=result.text,
        audio_path=path.relative_to(AUDIO_DIR).as_posix(),
        duration_ms=int((result.duration or 0) * 1000),
    )
    logger.info(
        f"转写完成 session={session['id']} engine={result.engine} "
        f"duration={result.duration}s elapsed={result.elapsed_ms}ms size={size}B"
    )
    return TranscribeOut(
        text=result.text,
        engine=result.engine,
        duration=result.duration,
        elapsed_ms=result.elapsed_ms,
        session_id=session["id"],
        message_id=message["id"],
        audio_path=path.relative_to(AUDIO_DIR).as_posix(),
    )

@router.get("/files/{file_path:path}")
def get_audio_file(file_path: str) -> FileResponse:
    """按相对路径读取已保存的音频片段（回听用），带路径穿越防护。"""
    path = safe_audio_path(file_path)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="音频文件不存在")
    return FileResponse(path, media_type="audio/wav")

"""音频 API：上传录音 → ASR 转写 → 落库回显（M1 语音管道）。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models import TranscribeOut
from app.services.asr import ASRError, get_provider
from app.storage import db
from app.storage.files import is_allowed, safe_store
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
    finally:
        # 转录完成后清理上传的临时音频（M4 回听功能再按需保留）
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning(f"清理临时音频失败：{path}")

    message = db.add_message(
        session_id=session["id"],
        role="user",
        content=result.text,
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
    )

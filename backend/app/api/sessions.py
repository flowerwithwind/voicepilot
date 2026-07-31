"""会话 API：列表 / 消息详情 / 回放 / 示例会话（M1 基础版，M2 增删改，M5 演示与可观测）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.audio.pcm import write_wav
from app.config import AUDIO_DIR
from app.models import MessageOut, SessionOut, SessionsOut
from app.storage import db
from app.storage.files import safe_audio_path
from app.utils.logging import get_logger

logger = get_logger("sessions")

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut)
def create_session(body: dict[str, Any] | None = None) -> SessionOut:
    title = (body or {}).get("title") or "新会话"
    row = db.create_session(title=title)
    return SessionOut(**row)


@router.get("", response_model=SessionsOut)
def list_sessions(limit: int = 50) -> SessionsOut:
    limit = min(max(limit, 1), 200)
    items = db.list_sessions(limit=limit)
    return SessionsOut(total=len(items), items=[SessionOut(**i) for i in items])


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: int) -> list[MessageOut]:
    if db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    rows = db.list_messages(session_id)
    return [MessageOut(**r) for r in rows]


@router.delete("/{session_id}")
def delete_session(session_id: int) -> dict[str, bool]:
    if db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    # KN-10：删除会话时按消息 audio_path 清理磁盘音频文件（safe_audio_path 防穿越）。
    # demo/ 为多会话共享的演示音频，保留不删（示例会话重建时会重写同名文件）。
    for m in db.list_messages(session_id):
        rel = m.get("audio_path")
        if not rel or rel.startswith("demo/"):
            continue
        path = safe_audio_path(rel)
        if path is None or not path.is_file():
            continue
        try:
            path.unlink()
        except OSError:
            logger.warning(f"删除会话 {session_id} 音频失败：{path}")
    db.delete_session(session_id)
    return {"deleted": True}


@router.get("/{session_id}/replay")
def replay_session(session_id: int) -> dict:
    """回放时间线：按阶段归类（ASR/LLM/工具/TTS），供回放页与可观测使用。"""
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    rows = db.list_messages(session_id)
    timeline = []
    for r in rows:
        stage = "llm"
        if r["role"] == "user":
            stage = "asr" if r.get("audio_path") else "input"
        elif r["role"] == "tool":
            stage = "tool"
        item = {
            "id": r["id"],
            "role": r["role"],
            "stage": stage,
            "text": r["content"],
            "audio_path": r.get("audio_path"),
            "duration_ms": r.get("duration_ms"),
            "elapsed_ms": r.get("elapsed_ms"),
            "prompt_tokens": r.get("prompt_tokens"),
            "completion_tokens": r.get("completion_tokens"),
            "created_at": r["created_at"],
        }
        # assistant 消息含 TTS 播报阶段（浏览器端 speechSynthesis）
        if r["role"] == "assistant":
            item["tts"] = {"engine": "browser"}
        timeline.append(item)
    return {"session": session, "timeline": timeline}


@router.post("/demo", response_model=SessionOut)
def create_demo_session() -> SessionOut:
    """创建内置示例会话：预置完整一轮「语音→ASR→LLM→工具二次确认→TTS」对话。

    示例音频为生成的静音 WAV，供回听与回放页演示；提醒记录同步写入 reminders 表。
    """
    session = db.create_session(title="示例会话：语音工具调用")
    remind_at = (
        (datetime.now(timezone.utc).astimezone() + timedelta(days=1))
        .replace(hour=9, minute=0, second=0, microsecond=0)
        .isoformat(timespec="seconds")
    )
    audio1 = _demo_audio(1.6)
    audio2 = _demo_audio(1.2)
    db.add_message(session["id"], "user", "明天早上 9 点提醒我开周会", audio1, 1600)
    db.add_message(
        session["id"],
        "assistant",
        "好的，我来帮你设置提醒：明天 09:00 开周会。这是一个敏感操作，需要你确认后才会真正创建。",
    )
    db.add_message(
        session["id"],
        "tool",
        f"工具调用：set_reminder(content=开周会, remind_at={remind_at}) → 等待用户确认",
    )
    db.add_message(session["id"], "user", "确认执行", audio2, 1200)
    db.add_message(session["id"], "tool", "✅ 提醒已创建：开周会（明天 09:00）")
    db.add_message(
        session["id"],
        "assistant",
        "提醒已经设置好啦，明天早上 9 点我会准时提醒你。还有其他需要帮忙的吗？",
    )
    db.create_reminder(session["id"], "开周会", remind_at)
    row = db.get_session(session["id"])
    row["message_count"] = 6
    return SessionOut(**row)


def _demo_audio(seconds: float) -> str:
    """生成一段静音演示音频（16kHz WAV），返回相对 AUDIO_DIR 的路径。"""
    demo_dir = AUDIO_DIR / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    path = demo_dir / f"demo_{int(seconds * 10):02d}.wav"
    write_wav(path, b"\x00\x00" * int(16000 * seconds), 16000)
    return path.relative_to(AUDIO_DIR).as_posix()

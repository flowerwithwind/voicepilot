"""会话 API：列表 / 消息详情（M1 基础版，M2 扩展增删改）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.models import MessageOut, SessionOut, SessionsOut
from app.storage import db

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
    db.delete_session(session_id)
    return {"deleted": True}

"""聊天 API：SSE 流式对话（含工具二次确认闭环）。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models import ChatRequest
from app.services.chat import stream_chat
from app.storage import db

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@router.post("/messages")
def chat_messages(body: ChatRequest) -> StreamingResponse:
    """对话：SSE 流式返回 delta / tool_call / done / error 事件。"""
    session_id = body.session_id
    if session_id is None:
        session = db.create_session(title="对话会话")
        session_id = session["id"]
    elif db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    def gen():
        try:
            for ev in stream_chat(
                session_id, body.content, approval=body.approval, save_user=body.save_user
            ):
                yield _sse(ev)
        except Exception as e:  # noqa: BLE001 - 边界兜底，避免 SSE 中断
            yield _sse({"type": "error", "detail": f"服务异常：{e}"})

    return StreamingResponse(gen(), media_type="text/event-stream")

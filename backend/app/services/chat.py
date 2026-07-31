"""对话引擎：多轮上下文 + LLM 流式 / 规则降级 + 工具二次确认闭环。"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from app.llm.client import LLMError
from app.services import settings as settings_svc
from app.services.tools import (
    SENSITIVE_TOOLS,
    TOOL_SCHEMAS,
    detect_tool_intent,
    execute_tool,
)
from app.storage import db
from app.utils.logging import get_logger

logger = get_logger("chat")

MAX_HISTORY = 10  # 携带的最近消息数（多轮上下文窗口）


def _role_map(role: str) -> str:
    return "assistant" if role == "assistant" else "user"


def build_history(session_id: int, limit: int = MAX_HISTORY) -> list[dict]:
    """从消息表构建 LLM 上下文（工具结果并入 system）。"""
    rows = db.list_messages(session_id)
    messages: list[dict] = []
    for row in rows[-limit:]:
        role = _role_map(row["role"])
        if row["role"] == "tool":
            messages.append(
                {"role": "system", "content": f"[工具执行结果] {row['content']}"}
            )
        else:
            messages.append({"role": role, "content": row["content"]})
    return messages


# ---- 规则降级（无 Key 演示） ----
_RULE_INTRO = "（规则模式）我是 VoicePilot 的本地回复引擎。"

def _rule_reply(text: str) -> str:
    t = text.strip()
    if not t:
        return "请说点什么吧～"
    if any(k in t for k in ("你好", "您好", "hi", "hello", "嗨")):
        return _RULE_INTRO + " 你好！可以试着对我说「设置明天9点提醒我开会」或「上海天气怎么样」。"
    if any(k in t for k in ("你是谁", "介绍", "能做什么")):
        return (
            _RULE_INTRO + " 我能听懂你的语音并回复，还能调用工具："
            "设置提醒、查询时间、查天气、搜索。配置 LLM API Key 后，我会切换为智能模型回答。"
        )
    if any(k in t for k in ("谢谢", "感谢")):
        return "不客气～ 还有什么需要帮忙的吗？"
    return _RULE_INTRO + " 我听到了你说：" + t[:60] + "。配置 LLM 引擎后，我会给出真正的智能回答。"


def _stream_text(text: str, chunk: int = 6) -> Iterator[dict]:
    """将整段文本按小块流式吐出（模拟 LLM 打字效果）。"""
    for i in range(0, len(text), chunk):
        yield {"type": "delta", "text": text[i : i + chunk]}
        time.sleep(0.012)


def _llm_stream(client, messages: list[dict]) -> Iterator[dict]:
    """LLM 流式生成（含工具调用解析）。"""
    yield from client.stream_chat(messages, tools=TOOL_SCHEMAS)


def stream_chat(
    session_id: int,
    user_text: str,
    approval: dict[str, Any] | None = None,
    save_user: bool = True,
) -> Iterator[dict]:
    """SSE 事件生成器。

    事件：
      delta: {type, text}
      tool_call: {type, request_id, tool, args, preview}
      await_approval: {type, request_id}
      done: {type, message_id, reply}
      error: {type, detail}
    """
    user_text = (user_text or "").strip()
    if not user_text:
        yield {"type": "error", "detail": "消息不能为空"}
        return

    # 二次确认重提交时不重复落库 user 消息；语音转录已由 transcribe 落库，save_user=False 避免重复
    if not approval and save_user:
        db.add_message(session_id, "user", user_text)

    intent = detect_tool_intent(user_text)

    # 命中工具且未确认 → 返回确认请求
    if intent and not approval:
        tool, args = intent
        request_id = uuid.uuid4().hex[:12]
        preview = _tool_preview(tool, args)
        yield {"type": "tool_call", "request_id": request_id, "tool": tool, "args": args, "preview": preview}
        if tool in SENSITIVE_TOOLS:
            yield {"type": "await_approval", "request_id": request_id}
        else:
            # 非敏感工具直接执行
            yield from _run_tool_and_reply(session_id, user_text, tool, args)
        return

    # 工具 + 已确认
    if intent and approval and approval.get("approved"):
        tool, args = intent
        yield from _run_tool_and_reply(session_id, user_text, tool, args)
        return

    if intent and approval and not approval.get("approved"):
        reply = "好的，已取消该操作。"
        yield from _stream_text(reply)
        db.add_message(session_id, "assistant", reply)
        yield {"type": "done", "message_id": db.list_messages(session_id)[-1]["id"], "reply": reply}
        return

    yield from _plain_reply(session_id, user_text)


def _tool_preview(tool: str, args: dict[str, Any]) -> str:
    if tool == "set_reminder":
        return f"设置提醒：{args.get('content', '')}（{args.get('remind_at', '')}）"
    if tool == "query_weather":
        return f"查询天气：{args.get('city', '')}"
    if tool == "web_search":
        return f"搜索：{args.get('query', '')}"
    return f"执行工具：{tool}"


def _run_tool_and_reply(
    session_id: int, user_text: str, tool: str, args: dict[str, Any]
) -> Iterator[dict]:
    """执行工具 → 结果注入 → 生成最终回复。"""
    try:
        result = execute_tool(session_id, tool, args)
    except ValueError as e:
        yield {"type": "error", "detail": str(e)}
        return
    db.add_message(session_id, "tool", f"[{tool}] {result}")
    reply = f"✅ 已完成：{result}"
    yield from _stream_text(reply)
    db.add_message(session_id, "assistant", reply)
    yield {"type": "done", "message_id": db.list_messages(session_id)[-1]["id"], "reply": reply}


def _plain_reply(session_id: int, user_text: str) -> Iterator[dict]:
    """普通对话：LLM 优先，无 Key 规则降级。"""
    client = settings_svc.build_llm_client()
    if not client.api_key:
        reply = _rule_reply(user_text)
        yield from _stream_text(reply)
        db.add_message(session_id, "assistant", reply)
        yield {"type": "done", "message_id": db.list_messages(session_id)[-1]["id"], "reply": reply}
        return

    history = build_history(session_id)
    try:
        reply_parts: list[str] = []
        for ev in _llm_stream(client, history):
            if ev["type"] == "delta":
                reply_parts.append(ev["text"])
                yield ev
            elif ev["type"] == "tool_call":
                # LLM 模式工具调用：同样进入确认流程
                request_id = uuid.uuid4().hex[:12]
                try:
                    args = json.loads(ev["arguments"] or "{}")
                except ValueError:
                    args = {}
                yield {
                    "type": "tool_call",
                    "request_id": request_id,
                    "tool": ev["name"],
                    "args": args,
                    "preview": _tool_preview(ev["name"], args),
                }
                if ev["name"] in SENSITIVE_TOOLS:
                    yield {"type": "await_approval", "request_id": request_id}
                    return
                yield from _run_tool_and_reply(session_id, user_text, ev["name"], args)
                return
        reply = "".join(reply_parts).strip() or "（模型未返回内容）"
    except LLMError as e:
        logger.warning(f"LLM 调用失败，降级规则回复：{e}")
        reply = _rule_reply(user_text) + f"（模型异常：{e}）"
        yield from _stream_text(reply)
    db.add_message(session_id, "assistant", reply)
    yield {"type": "done", "message_id": db.list_messages(session_id)[-1]["id"], "reply": reply}

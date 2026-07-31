"""对话引擎测试：规则回复 / 工具意图 / 二次确认闭环 / SSE。"""
from __future__ import annotations

from app.services.chat import stream_chat
from app.storage import db


def _events(gen):
    return list(gen)


def test_rule_reply_stream(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "你好"))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "规则模式" in texts
    assert events[-1]["type"] == "done"
    msgs = db.list_messages(sid)
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_reminder_requires_approval(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "明天9点提醒我开会"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds
    assert "await_approval" in kinds
    # 未确认前不落库 assistant / tool
    roles = [m["role"] for m in db.list_messages(sid)]
    assert roles == ["user"]
    tc = next(e for e in events if e["type"] == "tool_call")
    assert tc["tool"] == "set_reminder"
    assert tc["args"]["content"] == "开会"


def test_reminder_approved_executes(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "9点提醒我喝水", approval={"approved": True}))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "已创建提醒" in texts
    assert events[-1]["type"] == "done"
    reminders = db.list_reminders()
    assert len(reminders) == 1
    assert reminders[0]["content"] == "喝水"


def test_reminder_rejected(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "9点提醒我喝水", approval={"approved": False}))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "已取消" in texts
    assert db.list_reminders() == []


def test_weather_direct_execute(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "北京天气怎么样"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds
    assert "await_approval" not in kinds  # 非敏感工具直接执行
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "北京" in texts


def test_time_direct_execute(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "现在几点了"))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "现在是" in texts


def test_search_tool(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "搜索一下 VoicePilot 是什么"))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "演示占位结果" in texts


def test_empty_message(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "   "))
    assert events[0]["type"] == "error"


def test_sse_api_flow(client):
    """端到端 SSE：POST /api/chat/messages 返回事件流。"""
    r = client.post("/api/chat/messages", json={"content": "你好"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "data:" in body
    assert '"type": "done"' in body


def test_save_user_false_skips_duplicate(client):
    """语音流程：transcribe 已落库 user，chat 不再重复保存。"""
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "北京天气怎么样", save_user=False))
    assert events[-1]["type"] == "done"
    roles = [m["role"] for m in db.list_messages(sid)]
    assert roles == ["tool", "assistant"]  # 无重复 user

    # 默认行为不变：文本流程仍落库 user
    sid2 = db.create_session()["id"]
    _events(stream_chat(sid2, "你好"))
    roles2 = [m["role"] for m in db.list_messages(sid2)]
    assert roles2 == ["user", "assistant"]

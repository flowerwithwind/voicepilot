"""实时 WebSocket 集成测试：VAD 分段 → 增量 ASR → 回复流 → 审批 → 打断。"""
from __future__ import annotations

import json
import math
import struct

from app.storage import db


def sine_pcm(seconds: float, freq: int = 440, amp: float = 0.4, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    return struct.pack(
        f"<{n}h",
        *(int(32767 * amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)),
    )


def silence_pcm(seconds: float, rate: int = 16000) -> bytes:
    return b"\x00\x00" * int(rate * seconds)


def _collect_until_done(ws):
    """收事件直到 done / error（测试中服务端保证会发送）。"""
    events = []
    while True:
        ev = ws.receive_json()
        events.append(ev)
        if ev["type"] in ("done", "error"):
            return events


def test_realtime_voice_turn(client):
    """音频分片 → VAD → partial/final ASR → 规则回复 → tts → done。"""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["session_id"] > 0
        sid = ready["session_id"]

        ws.send_bytes(sine_pcm(0.5))
        ws.send_bytes(sine_pcm(0.5))
        ws.send_bytes(silence_pcm(0.9))

        events = _collect_until_done(ws)
        kinds = [e["type"] for e in events]
        assert "vad" in kinds
        assert "asr.partial" in kinds
        assert "asr.final" in kinds
        assert "delta" in kinds
        assert "tts" in kinds
        assert events[-1]["type"] == "done"

        partial = next(e for e in events if e["type"] == "asr.partial")
        assert "正在识别" in partial["text"]

        final = next(e for e in events if e["type"] == "asr.final")
        assert final["engine"] == "rule"
        assert final["audio_path"].endswith(".wav")

        # 落库：user（含音频路径，M4 回听用）+ assistant
        msgs = db.list_messages(sid)
        assert msgs[0]["role"] == "user"
        assert msgs[0]["audio_path"] == final["audio_path"]
        assert msgs[0]["duration_ms"] > 0
        assert msgs[-1]["role"] == "assistant"


def test_realtime_utterance_approval_flow(client):
    """文本 utterance → 敏感工具 → 二次确认 → 执行。"""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        ws.receive_json()
        ws.send_text(json.dumps({"type": "utterance", "text": "明天9点提醒我开会"}))
        tc = ws.receive_json()
        assert tc["type"] == "tool_call"
        assert tc["tool"] == "set_reminder"
        req_id = tc["request_id"]
        assert ws.receive_json()["type"] == "await_approval"

        ws.send_text(json.dumps({"type": "approval", "request_id": req_id, "approved": True}))
        events = _collect_until_done(ws)
        texts = "".join(e["text"] for e in events if e["type"] == "delta")
        assert "已创建提醒" in texts
        assert events[-1]["type"] == "done"
        reminders = db.list_reminders()
        assert len(reminders) == 1
        assert reminders[0]["content"] == "开会"


def test_realtime_approval_rejected(client):
    """拒绝审批 → 不执行工具；错误 request_id 被忽略。"""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        ws.receive_json()
        ws.send_text(json.dumps({"type": "utterance", "text": "9点提醒我喝水"}))
        tc = ws.receive_json()  # tool_call
        ws.receive_json()  # await_approval
        # 错误 request_id 应被忽略（回合继续等待）
        ws.send_text(json.dumps({"type": "approval", "request_id": "stale", "approved": False}))
        ws.send_text(
            json.dumps({"type": "approval", "request_id": tc["request_id"], "approved": False})
        )
        events = _collect_until_done(ws)
        texts = "".join(e["text"] for e in events if e["type"] == "delta")
        assert "已取消" in texts
        assert db.list_reminders() == []


def test_realtime_cancel_barge_in(client):
    """回复等待审批时 cancel → interrupt，连接仍可继续使用。"""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        ws.receive_json()
        ws.send_text(json.dumps({"type": "utterance", "text": "明天9点提醒我开会"}))
        ws.receive_json()  # tool_call
        ws.receive_json()  # await_approval
        ws.send_text(json.dumps({"type": "cancel"}))
        assert ws.receive_json()["type"] == "interrupt"
        # 未审批 → 不执行工具
        assert db.list_reminders() == []
        # 打断后连接仍可用
        ws.send_text(json.dumps({"type": "utterance", "text": "现在几点了"}))
        events = _collect_until_done(ws)
        texts = "".join(e["text"] for e in events if e["type"] == "delta")
        assert "现在是" in texts


def test_realtime_flush_ends_segment(client):
    """无 hello 时音频自动建会话；flush 强制结束语音段。"""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_bytes(sine_pcm(0.4))
        ws.send_text(json.dumps({"type": "flush"}))
        events = _collect_until_done(ws)
        kinds = [e["type"] for e in events]
        assert "ready" in kinds  # 隐式建会话
        assert "asr.final" in kinds
        assert events[-1]["type"] == "done"


def test_realtime_hello_invalid_session_autocreates(client):
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": 99999}))
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["session_id"] != 99999
        ws.send_text(json.dumps({"type": "ping"}))
        assert ws.receive_json()["type"] == "pong"


def test_realtime_unknown_text_type(client):
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "nope"}))
        ev = ws.receive_json()
        assert ev["type"] == "error"
        assert "未知消息类型" in ev["detail"]



def test_realtime_over_limit_force_ends_turn(client, monkeypatch):
    """KN-09：分片累计超限后 force_end 当前语音段，回合不悬挂。"""
    import app.api.realtime as realtime_mod

    monkeypatch.setattr(realtime_mod, "MAX_TURN_BYTES", 40_000)  # 模拟 5MB 上限
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        ws.receive_json()
        # 第一片触发 speech_start（audio_buf 清空），第二片入缓冲，
        # 第三片使 len(audio_buf)+len(data) 超过上限 → 触发 force_end
        ws.send_bytes(sine_pcm(1))  # 32KB
        ws.send_bytes(sine_pcm(1))
        ws.send_bytes(sine_pcm(1))
        events = _collect_until_done(ws)  # 无需静音分片也应正常结束
        kinds = [e["type"] for e in events]
        assert "asr.final" in kinds
        assert any(e["type"] == "vad" and e["event"] == "speech_end" for e in events)
        assert events[-1]["type"] == "done"

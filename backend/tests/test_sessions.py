"""会话与消息查询测试。"""
from __future__ import annotations

from tests.conftest import make_wav_bytes


def test_sessions_empty(client):
    body = client.get("/api/sessions").json()
    assert body == {"total": 0, "items": []}


def test_messages_404(client):
    assert client.get("/api/sessions/99999/messages").status_code == 404


def test_sessions_sorted_by_updated(client):
    r1 = client.post("/api/audio/transcribe", files={"file": ("a.wav", make_wav_bytes(0.2))})
    sid1 = r1.json()["session_id"]
    r2 = client.post("/api/audio/transcribe", files={"file": ("b.wav", make_wav_bytes(0.2))})
    sid2 = r2.json()["session_id"]
    items = client.get("/api/sessions").json()["items"]
    assert [i["id"] for i in items] == [sid2, sid1]
    assert items[0]["message_count"] == 1

def test_replay_timeline_stages(client):
    """回放接口：语音消息标 ASR 阶段，助手消息含 TTS 信息。"""
    r = client.post("/api/audio/transcribe", files={"file": ("a.wav", make_wav_bytes(0.2))})
    sid = r.json()["session_id"]
    body = client.get(f"/api/sessions/{sid}/replay").json()
    assert body["session"]["id"] == sid
    assert len(body["timeline"]) == 1
    item = body["timeline"][0]
    assert item["stage"] == "asr"
    assert item["role"] == "user"
    assert item["audio_path"]
    assert item["duration_ms"] > 0
    # 404
    assert client.get("/api/sessions/99999/replay").status_code == 404


def test_demo_session_seeded(client):
    """内置示例会话：预置完整一轮语音工具调用对话，回放阶段齐全。"""
    r = client.post("/api/sessions/demo")
    assert r.status_code == 200
    body = r.json()
    sid = body["id"]
    assert "示例" in body["title"]
    assert body["message_count"] == 6
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "user", "tool", "assistant"]
    replay = client.get(f"/api/sessions/{sid}/replay").json()
    assert [t["stage"] for t in replay["timeline"]] == ["asr", "llm", "tool", "asr", "tool", "llm"]
    assert replay["timeline"][0]["audio_path"] == "demo/demo_16.wav"
    assert replay["timeline"][0]["duration_ms"] == 1600
    assert replay["timeline"][1]["tts"]["engine"] == "browser"
    # 演示音频可回听（RIFF WAV）
    resp = client.get("/api/audio/files/" + replay["timeline"][0]["audio_path"])
    assert resp.status_code == 200
    assert resp.content[:4] == b"RIFF"

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

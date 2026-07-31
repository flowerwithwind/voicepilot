"""语音管道测试：上传 → ASR 回声 → 落库。"""
from __future__ import annotations

import pytest

from tests.conftest import make_wav_bytes


def test_transcribe_wav_ok(client):
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("demo.wav", make_wav_bytes(0.5), "audio/wav")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "rule"
    assert "演示转写" in body["text"]
    assert body["duration"] == pytest.approx(0.5, abs=0.02)
    assert body["session_id"] > 0
    assert body["message_id"] > 0
    # 会话与消息已落库
    sessions = client.get("/api/sessions").json()
    assert sessions["total"] == 1
    msgs = client.get(f"/api/sessions/{body['session_id']}/messages").json()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_transcribe_with_session(client):
    # 先建一个会话再转录
    r = client.post("/api/audio/transcribe", files={"file": ("a.wav", make_wav_bytes(0.3))})
    sid = r.json()["session_id"]
    r2 = client.post(
        "/api/audio/transcribe",
        files={"file": ("b.wav", make_wav_bytes(0.2))},
        data={"session_id": str(sid)},
    )
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert len(msgs) == 2


def test_transcribe_bad_extension(client):
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 422
    assert "不支持的音频格式" in r.json()["detail"]


def test_transcribe_empty_file(client):
    r = client.post("/api/audio/transcribe", files={"file": ("a.wav", b"")})
    assert r.status_code == 422
    assert "为空" in r.json()["detail"]


def test_transcribe_oversize(client, monkeypatch):
    import app.storage.files as file_store

    monkeypatch.setattr(file_store, "MAX_AUDIO_BYTES", 100)
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("big.wav", b"x" * 200)},
    )
    assert r.status_code == 422
    assert "大小限制" in r.json()["detail"]


def test_transcribe_missing_session(client):
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("a.wav", make_wav_bytes(0.1))},
        data={"session_id": "99999"},
    )
    assert r.status_code == 404
    assert "会话不存在" in r.json()["detail"]


def test_transcribe_without_file(client):
    assert client.post("/api/audio/transcribe").status_code == 422

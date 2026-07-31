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

def test_transcribe_keeps_audio_for_replay(client):
    """M4：转录后保留音频文件，消息带 audio_path 且可通过回听接口读取。"""
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("demo.wav", make_wav_bytes(0.5), "audio/wav")},
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert len(msgs) == 1
    audio_path = msgs[0]["audio_path"]
    assert audio_path and audio_path.endswith(".wav")
    assert msgs[0]["duration_ms"] == pytest.approx(500, abs=10)
    # 回听接口可读取
    resp = client.get(f"/api/audio/files/{audio_path}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/")
    assert len(resp.content) > 0


def test_audio_file_traversal_blocked(client):
    """路径穿越/绝对路径一律 404。"""
    for bad in ("../voicepilot.db", "..%2Fvoicepilot.db", "realtime/../../voicepilot.db"):
        r = client.get(f"/api/audio/files/{bad}")
        assert r.status_code == 404, (bad, r.status_code)


def test_audio_file_missing(client):
    assert client.get("/api/audio/files/no-such-file.wav").status_code == 404

def test_audio_file_backslash_path_served(client):
    """KN-03：Windows 反斜杠风格 URL 经回放接口可正常读取（容器路径规则）。"""
    from app.config import AUDIO_DIR

    realtime_dir = AUDIO_DIR / "realtime"
    realtime_dir.mkdir(parents=True, exist_ok=True)
    wav = realtime_dir / "legacy-backslash.wav"
    wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    # 前端旧版本会把反斜杠 encodeURIComponent 为 %5C
    r = client.get("/api/audio/files/realtime%5Clegacy-backslash.wav")
    assert r.status_code == 200, r.text
    assert r.content == b"RIFF\x00\x00\x00\x00WAVE"
    assert r.headers["content-type"].startswith("audio/")


def test_legacy_backslash_audio_path_normalized_on_read(client):
    """KN-03：DB 中反斜杠旧数据在 messages/replay 接口返回正斜杠。"""
    from app.storage import db

    sid = db.create_session()["id"]
    db.add_message(sid, "user", "旧数据", audio_path="realtime\\legacy.wav", duration_ms=500)
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert msgs[0]["audio_path"] == "realtime/legacy.wav"
    replay = client.get(f"/api/sessions/{sid}/replay").json()
    assert replay["timeline"][0]["audio_path"] == "realtime/legacy.wav"


def test_legacy_backslash_stored_data_playable(client):
    """KN-03：反斜杠旧数据按容器路径规则可完整回听。"""
    from app.config import AUDIO_DIR
    from app.storage import db

    realtime_dir = AUDIO_DIR / "realtime"
    realtime_dir.mkdir(parents=True, exist_ok=True)
    wav = realtime_dir / "legacy-stored.wav"
    wav.write_bytes(b"RIFFlegacyWAVE")
    sid = db.create_session()["id"]
    db.add_message(sid, "user", "旧数据", audio_path="realtime\\legacy-stored.wav", duration_ms=500)
    # 前端旧 URL（反斜杠被编码为 %5C）也应命中
    r = client.get("/api/audio/files/realtime%5Clegacy-stored.wav")
    assert r.status_code == 200, r.text
    assert r.content == b"RIFFlegacyWAVE"

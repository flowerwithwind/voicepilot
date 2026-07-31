"""提醒 API 测试。"""
from __future__ import annotations


def test_reminders_empty(client):
    assert client.get("/api/reminders").json() == []


def test_reminders_crud(client):
    r = client.post("/api/chat/messages", json={"content": "9点提醒我喝水", "approval": {"approved": True}})
    assert r.status_code == 200
    items = client.get("/api/reminders").json()
    assert len(items) == 1
    rid = items[0]["id"]
    assert client.delete(f"/api/reminders/{rid}").json() == {"deleted": True}
    assert client.get("/api/reminders").json() == []
    assert client.delete(f"/api/reminders/{rid}").status_code == 404


def test_sessions_create_delete(client):
    r = client.post("/api/sessions", json={"title": "测试会话"})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["title"] == "测试会话"
    assert client.delete(f"/api/sessions/{sid}").json() == {"deleted": True}
    assert client.delete(f"/api/sessions/{sid}").status_code == 404

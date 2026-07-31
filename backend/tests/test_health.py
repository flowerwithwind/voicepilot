"""健康检查与基础能力探测测试。"""
from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["asr_engine"] == "rule"
    assert body["capabilities"]["asr"] is True


def test_health_unknown_route(client):
    assert client.get("/api/nope").status_code == 404

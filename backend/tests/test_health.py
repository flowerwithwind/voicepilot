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



def test_cors_allows_dev_ports(client):
    """KN-12：CORS 覆盖 5173~5179 开发端口。"""
    for origin in (
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5179",
        "http://127.0.0.1:5174",
    ):
        r = client.get("/api/health", headers={"Origin": origin})
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == origin
    # 白名单外来源不带 CORS 头
    r = client.get("/api/health", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_env_override(monkeypatch):
    """KN-12：VOICEPILOT_CORS_ORIGINS 可覆盖默认白名单。"""
    from app.main import cors_origins

    monkeypatch.setenv(
        "VOICEPILOT_CORS_ORIGINS", "http://localhost:9999, http://localhost:8888"
    )
    assert cors_origins() == ["http://localhost:9999", "http://localhost:8888"]

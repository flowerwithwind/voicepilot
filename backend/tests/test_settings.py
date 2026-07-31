"""引擎设置 API 测试：默认值 / 保存 / 脱敏 / 连接测试。"""
from __future__ import annotations


def test_settings_defaults(client):
    body = client.get("/api/settings").json()
    assert body["model"]["model"] == "deepseek-chat"
    assert body["asr"]["engine"] == "rule"
    assert body["tts"]["engine"] == "browser"
    assert body["capabilities"]["llm"] is False
    assert body["capabilities"]["asr"] is True


def test_settings_update_persists(client):
    r = client.put("/api/settings", json={"model": {"temperature": 0.3}})
    assert r.status_code == 200
    assert r.json()["model"]["temperature"] == 0.3
    assert client.get("/api/settings").json()["model"]["temperature"] == 0.3


def test_settings_api_key_masked(client):
    key = "sk-test1234567890abcd"
    r = client.put("/api/settings", json={"model": {"api_key": key}})
    assert r.status_code == 200
    assert key not in r.text
    assert r.json()["model"]["api_key"] == "sk-t****abcd"
    assert client.get("/api/settings").json()["model"]["api_key"] == "sk-t****abcd"
    # 提交脱敏值不覆盖
    r2 = client.put("/api/settings", json={"model": {"api_key": "sk-t****abcd"}})
    assert r2.json()["model"]["api_key"] == "sk-t****abcd"
    assert r2.json()["capabilities"]["llm"] is True


def test_settings_unknown_keys_ignored(client):
    r = client.put("/api/settings", json={"model": {"hacker": True}})
    assert r.status_code == 200
    assert "hacker" not in r.json()["model"]


def test_test_connection_ignores_masked_key(client, monkeypatch):
    key = "sk-test1234567890abcd"
    client.put("/api/settings", json={"model": {"api_key": key}})
    seen = {}

    def fake_test(self):
        seen["key"] = self.api_key

    monkeypatch.setattr("app.llm.client.LLMClient.test", fake_test)
    r = client.post("/api/settings/test", json={"model": {"api_key": "sk-t****abcd"}})
    assert r.status_code == 200
    assert seen["key"] == key  # 用真实 Key 而不是掩码串
    assert r.json()["ok"] is True


def test_test_connection_without_key(client):
    r = client.post("/api/settings/test", json={"model": {"api_key": ""}})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error"]

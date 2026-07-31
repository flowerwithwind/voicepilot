"""KN-04 可观测测试：Mock LLM 流耗时/token 落库、回放 API 指标字段、旧库补列幂等。"""
from __future__ import annotations

import json
import sqlite3

from app.services import settings as settings_svc
from app.storage import db


class FakeLLMClient:
    """Mock LLMClient：产出流式 delta，并预置 KN-04 指标（模拟流末 usage 采集）。"""

    def __init__(self) -> None:
        self.api_key = "sk-test"
        self.last_elapsed_ms = 3200
        self.last_prompt_tokens = 120
        self.last_completion_tokens = 480

    def last_metrics(self) -> dict[str, int | None]:
        return {
            "elapsed_ms": self.last_elapsed_ms,
            "prompt_tokens": self.last_prompt_tokens,
            "completion_tokens": self.last_completion_tokens,
        }

    def stream_chat(self, messages, tools=None):
        yield {"type": "delta", "text": "你好，这是 Mock LLM 回复"}


class FakeLLMToolClient(FakeLLMClient):
    """Mock LLMClient：产出工具调用（流末同样采集到指标）。"""

    def stream_chat(self, messages, tools=None):
        yield {
            "type": "tool_call",
            "id": "call_1",
            "name": "query_weather",
            "arguments": json.dumps({"city": "北京"}),
        }


def _collect_until_done(ws):
    """收集事件直到 done / error（与服务端保证发终态一致）。"""
    events = []
    while True:
        ev = ws.receive_json()
        events.append(ev)
        if ev["type"] in ("done", "error"):
            return events


def test_stream_chat_captures_usage_and_elapsed(monkeypatch):
    """真实 LLMClient 流式解析：流末 usage chunk 采集 token，耗时被记录。"""
    import httpx

    from app.llm.client import LLMClient

    chunks = [
        {"choices": [{"delta": {"content": "你好"}}]},
        {"choices": [{"delta": {"content": "世界"}}]},
        {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 34}},
    ]
    body = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def _client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("app.llm.client.httpx.Client", _client)
    client = LLMClient(base_url="https://api.test", api_key="sk-test", model="m")
    text = "".join(ev["text"] for ev in client.stream_chat([{"role": "user", "content": "hi"}]))
    assert text == "你好世界"
    assert client.last_prompt_tokens == 12
    assert client.last_completion_tokens == 34
    assert client.last_elapsed_ms is not None
    assert client.last_elapsed_ms >= 0


def test_chat_stream_metrics_persisted(client, monkeypatch):
    """SSE 对话：Mock LLM 流结束后耗时/token 随 assistant 消息落库。"""
    monkeypatch.setattr(settings_svc, "build_llm_client", lambda: FakeLLMClient())
    r = client.post("/api/chat/messages", json={"content": "你好"})
    assert r.status_code == 200
    sid = db.list_sessions()[0]["id"]
    assistant = db.list_messages(sid)[-1]
    assert assistant["role"] == "assistant"
    assert assistant["elapsed_ms"] == 3200
    assert assistant["prompt_tokens"] == 120
    assert assistant["completion_tokens"] == 480


def test_chat_tool_turn_metrics_attached(client, monkeypatch):
    """LLM 产出工具调用：本轮耗时/token 随最终回复落库。"""
    monkeypatch.setattr(settings_svc, "build_llm_client", lambda: FakeLLMToolClient())
    r = client.post("/api/chat/messages", json={"content": "随便聊聊"})
    assert r.status_code == 200
    sid = db.list_sessions()[0]["id"]
    assistant = db.list_messages(sid)[-1]
    assert assistant["role"] == "assistant"
    assert assistant["elapsed_ms"] == 3200
    assert assistant["prompt_tokens"] == 120
    assert assistant["completion_tokens"] == 480


def test_realtime_stream_metrics_persisted(client, monkeypatch):
    """实时 WS 文本回合：Mock LLM 流结束后耗时/token 随 assistant 消息落库。"""
    monkeypatch.setattr(settings_svc, "build_llm_client", lambda: FakeLLMClient())
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        sid = ready["session_id"]
        ws.send_text(json.dumps({"type": "utterance", "text": "你好"}))
        events = _collect_until_done(ws)
        assert events[-1]["type"] == "done"
        assistant = db.list_messages(sid)[-1]
        assert assistant["role"] == "assistant"
        assert assistant["elapsed_ms"] == 3200
        assert assistant["prompt_tokens"] == 120
        assert assistant["completion_tokens"] == 480


def test_replay_returns_llm_metrics(client, monkeypatch):
    """回放 API：LLM 消息返回 elapsed_ms / prompt_tokens / completion_tokens。"""
    monkeypatch.setattr(settings_svc, "build_llm_client", lambda: FakeLLMClient())
    sid = db.create_session()["id"]
    client.post("/api/chat/messages", json={"content": "你好", "session_id": sid})
    body = client.get(f"/api/sessions/{sid}/replay").json()
    llm_items = [t for t in body["timeline"] if t["stage"] == "llm"]
    assert len(llm_items) == 1
    item = llm_items[0]
    assert item["elapsed_ms"] == 3200
    assert item["prompt_tokens"] == 120
    assert item["completion_tokens"] == 480


def test_replay_metrics_null_when_absent(client):
    """无指标消息：回放字段存在但为 null（前端优雅隐藏）。"""
    sid = client.post("/api/sessions/demo").json()["id"]
    body = client.get(f"/api/sessions/{sid}/replay").json()
    llm_items = [t for t in body["timeline"] if t["stage"] == "llm"]
    assert llm_items
    for item in llm_items:
        assert item["elapsed_ms"] is None
        assert item["prompt_tokens"] is None
        assert item["completion_tokens"] is None


def test_init_db_adds_metrics_columns_idempotent(client, monkeypatch, tmp_path):
    """旧库（无 KN-04 列）init_db 幂等补列；重复执行不报错。"""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            audio_path TEXT,
            duration_ms INTEGER,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    db.init_db()  # 幂等：第二次执行不报错、不重复加列

    conn = sqlite3.connect(path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    conn.close()
    assert {"elapsed_ms", "prompt_tokens", "completion_tokens"} <= cols

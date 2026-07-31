"""C3 query_data 工具测试：工具链 / 参数校验 / 规则降级 / 二次确认 / 回放。"""
from __future__ import annotations

import json

import pytest

from app.services.chat import stream_chat
from app.services.query_data import run_query
from app.services.tools import TOOL_SCHEMAS, detect_tool_intent, execute_tool
from app.storage import db


def _events(gen):
    return list(gen)


def _tool_call(events):
    return next(e for e in events if e["type"] == "tool_call")


# ---- 工具注册表 / 规则意图（无 Key 降级） ----

def test_tool_registry_contains_query_data(client):
    names = [s["function"]["name"] for s in TOOL_SCHEMAS]
    assert "query_data" in names
    schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "query_data")
    params = schema["function"]["parameters"]["properties"]
    assert set(params["table"]["enum"]) == {"orders", "products", "customers"}
    assert set(params["action"]["enum"]) == {"list", "summary", "export", "delete"}
    assert params["limit"]["maximum"] == 100


def test_rule_intent_order_summary(client):
    tool, args = detect_tool_intent("帮我做一下订单汇总")
    assert tool == "query_data"
    assert args["table"] == "orders"
    assert args["action"] == "summary"


def test_rule_intent_stock_list_with_filter(client):
    tool, args = detect_tool_intent("库存不足10的商品有哪些")
    assert tool == "query_data"
    assert args == {"table": "products", "action": "list", "filters": {"stock_lt": 10}, "limit": 10}


def test_rule_intent_customers_direct(client):
    tool, args = detect_tool_intent("有哪些客户")
    assert (tool, args["table"], args["action"]) == ("query_data", "customers", "list")


def test_rule_intent_export_orders(client):
    tool, args = detect_tool_intent("导出全部订单数据")
    assert (tool, args["table"], args["action"]) == ("query_data", "orders", "export")


def test_rule_intent_delete_with_status_filter(client):
    tool, args = detect_tool_intent("删除所有待发货订单")
    assert (tool, args["table"], args["action"]) == ("query_data", "orders", "delete")
    assert args["filters"] == {"status": "待发货"}


# ---- 参数校验 ----

def test_validation_bad_table(client):
    with pytest.raises(ValueError, match="未知数据表"):
        run_query({"table": "users", "action": "list"})


def test_validation_bad_action(client):
    with pytest.raises(ValueError, match="未知操作"):
        run_query({"table": "orders", "action": "drop"})


def test_validation_bad_limit(client):
    with pytest.raises(ValueError, match="limit"):
        run_query({"table": "orders", "action": "list", "limit": 0})
    with pytest.raises(TypeError, match="limit"):
        run_query({"table": "orders", "action": "list", "limit": "10"})


def test_validation_bad_filter_key(client):
    with pytest.raises(ValueError, match="不支持筛选"):
        run_query({"table": "products", "action": "list", "filters": {"status": "已发货"}})


def test_validation_bad_status(client):
    with pytest.raises(ValueError, match="未知订单状态"):
        run_query({"table": "orders", "action": "list", "filters": {"status": "已签收"}})


def test_validation_delete_requires_filter(client):
    with pytest.raises(ValueError, match="至少一个筛选条件"):
        run_query({"table": "orders", "action": "delete"})


# ---- 执行 / 工具调用链 ----

def test_summary_executes_and_logs_tool(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "订单汇总"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds
    assert "await_approval" not in kinds
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "订单汇总" in texts
    roles = [m["role"] for m in db.list_messages(sid)]
    assert roles == ["user", "tool", "assistant"]
    tool_msg = next(m for m in db.list_messages(sid) if m["role"] == "tool")
    assert "[query_data]" in tool_msg["content"]
    assert "总金额" in tool_msg["content"]


def test_products_list_direct_execute(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "库存不足10的商品有哪些"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds
    assert "await_approval" not in kinds  # 非敏感查询直接执行
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "无线耳机" in texts  # 库存 8 < 10
    assert "机械键盘" in texts  # 库存 3 < 10


def test_execute_tool_chain_direct(client):
    """execute_tool 直接调用链：参数化查询 + 结果文本。"""
    result = execute_tool(0, "query_data", {"table": "orders", "action": "summary"})
    assert "订单汇总" in result
    result2 = execute_tool(
        0, "query_data", {"table": "customers", "action": "list", "filters": {"city": "北京"}}
    )
    assert "张三" in result2
    assert "李四" not in result2


# ---- 二次确认流程 ----

def test_orders_detail_requires_approval(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "查看订单明细"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds
    assert "await_approval" in kinds
    tc = _tool_call(events)
    assert tc["tool"] == "query_data"
    assert tc["args"]["table"] == "orders"
    assert tc["args"]["action"] == "list"
    assert "数据查询" in tc["preview"]
    # 未确认前不执行
    assert [m["role"] for m in db.list_messages(sid)] == ["user"]


def test_delete_requires_approval(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "删除所有待发货订单"))
    kinds = [e["type"] for e in events]
    assert "tool_call" in kinds
    assert "await_approval" in kinds
    tc = _tool_call(events)
    assert tc["args"]["filters"] == {"status": "待发货"}
    assert [m["role"] for m in db.list_messages(sid)] == ["user"]


def test_export_requires_approval(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "导出全部订单数据"))
    assert "await_approval" in [e["type"] for e in events]
    tc = _tool_call(events)
    assert (tc["args"]["table"], tc["args"]["action"]) == ("orders", "export")


def test_delete_approved_executes(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "删除所有待发货订单", approval={"approved": True}))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "已删除 3 条订单记录" in texts
    assert events[-1]["type"] == "done"
    roles = [m["role"] for m in db.list_messages(sid)]
    assert roles == ["tool", "assistant"]


def test_orders_detail_approved_executes(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "查看订单明细", approval={"approved": True}))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "订单明细" in texts
    assert "共 10 条" in texts


def test_export_approved_executes_full_rows(client):
    """导出为全量（不受 limit=10 限制）：种子订单共 10 条全部导出。"""
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "导出全部订单数据", approval={"approved": True}))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "全量导出 10 条" in texts
    assert "已取消" not in texts


def test_rejection_cancels(client):
    sid = db.create_session()["id"]
    events = _events(stream_chat(sid, "删除所有待发货订单", approval={"approved": False}))
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "已取消" in texts
    assert [m["role"] for m in db.list_messages(sid)] == ["assistant"]


# ---- 会话回放包含工具链 ----

def test_replay_contains_tool_chain(client):
    sid = db.create_session()["id"]
    _events(stream_chat(sid, "订单汇总"))
    body = client.get(f"/api/sessions/{sid}/replay").json()
    stages = [t["stage"] for t in body["timeline"]]
    assert stages == ["input", "tool", "llm"]
    tool_item = next(t for t in body["timeline"] if t["stage"] == "tool")
    assert tool_item["role"] == "tool"
    assert "[query_data]" in tool_item["text"]


def test_replay_after_approved_sensitive(client):
    sid = db.create_session()["id"]
    _events(stream_chat(sid, "查看订单明细", approval={"approved": True}))
    body = client.get(f"/api/sessions/{sid}/replay").json()
    stages = [t["stage"] for t in body["timeline"]]
    assert "tool" in stages
    assert stages[-1] == "llm"
    tool_item = next(t for t in body["timeline"] if t["stage"] == "tool")
    assert "[query_data]" in tool_item["text"]


# ---- 实时语音链路（WS） ----

def test_realtime_query_data_approval_flow(client):
    """WS：query_data 敏感操作（删除）→ 二次确认 → 执行。"""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "hello", "session_id": None}))
        assert ws.receive_json()["type"] == "ready"
        ws.send_text(json.dumps({"type": "utterance", "text": "删除所有待发货订单"}))
        tc = ws.receive_json()
        assert tc["type"] == "tool_call"
        assert tc["tool"] == "query_data"
        assert tc["args"]["action"] == "delete"
        req_id = tc["request_id"]
        assert ws.receive_json()["type"] == "await_approval"
        ws.send_text(json.dumps({"type": "approval", "request_id": req_id, "approved": True}))
        events = []
        while True:
            ev = ws.receive_json()
            events.append(ev)
            if ev["type"] in ("done", "error"):
                break
        texts = "".join(e["text"] for e in events if e["type"] == "delta")
        assert "已删除 3 条订单记录" in texts
        assert events[-1]["type"] == "done"
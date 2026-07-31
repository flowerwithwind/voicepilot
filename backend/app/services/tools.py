"""工具注册表：意图检测 + 执行（提醒/时间/天气/搜索）。

M2 以规则检测为主；LLM 模式通过 tool schema 调用同一执行器。
敏感操作（reminder）需要前端二次确认后才执行。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.storage import db

# ---- 工具 schema（OpenAI 兼容 tools 参数） ----
TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "设置一个提醒事项，包含提醒内容与提醒时间（如 9:00 / 明天上午10点）",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "提醒内容"},
                    "remind_at": {"type": "string", "description": "提醒时间，ISO 格式"},
                },
                "required": ["content", "remind_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前日期与时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_weather",
            "description": "查询指定城市的天气（演示数据）",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索网络信息（演示数据）",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

SENSITIVE_TOOLS = {"set_reminder"}

# ---- 规则意图检测（无 Key 演示） ----
_REMINDER_RE = re.compile(r"(?:提醒|记得)(?:我)?s*(?P<content>.{1,30}?)(?=，|。|$)")
_HOUR_RE = re.compile(r"(?P<hour>\d{1,2})\s*点")
_TOMORROW_RE = re.compile(r"明天|明早|明晚")
_TIME_RE = re.compile(r"(?:时间|几点了|现在几点|日期|今天几号|星期)")
_WEATHER_RE = re.compile(r"(?P<city>[一-龥]{2,6}?)(?:的)?(?:天气|气温|下雨|温度)(?:怎么样|如何)?$")
_WEATHER_NO_CITY_RE = re.compile(r"(?:天气|气温|下雨|温度)")
_SEARCH_RE = re.compile(r"(?:搜索|查一下|查查|百度|搜一下)s*(?P<query>.{1,40})")


def detect_tool_intent(text: str) -> tuple[str, dict[str, Any]] | None:
    """规则意图检测：返回 (tool_name, args)；未命中返回 None。"""
    t = text.strip()
    if _REMINDER_RE.search(t) and _HOUR_RE.search(t):
        m = _REMINDER_RE.search(t)
        h = _HOUR_RE.search(t)
        content = (m.group("content") if m and m.group("content") else "提醒事项").strip() or "提醒事项"
        hour = int(h.group("hour"))
        minute = 0
        hm = re.search(r"(?P<hour>\d{1,2})\s*[:：]\s*(?P<min>\d{1,2})", t)
        if hm:
            hour = int(hm.group("hour"))
            minute = int(hm.group("min"))
        now = datetime.now(timezone.utc).astimezone()
        remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if _TOMORROW_RE.search(t):
            remind_at += timedelta(days=1)
        if remind_at <= now:
            remind_at += timedelta(days=1)
        return "set_reminder", {
            "content": content,
            "remind_at": remind_at.isoformat(timespec="minutes"),
        }
    if _TIME_RE.search(t):
        return "get_current_time", {}
    m = _WEATHER_RE.search(t)
    if m and m.group("city"):
        return "query_weather", {"city": m.group("city")}
    if _WEATHER_NO_CITY_RE.search(t):
        return "query_weather", {"city": "上海"}
    m = _SEARCH_RE.search(t)
    if m and m.group("query"):
        return "web_search", {"query": m.group("query").strip()}
    return None


# ---- 执行器 ----
def _parse_remind_at(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%m月%d日 %H:%M")
    except ValueError:
        return iso


def execute_tool(session_id: int, name: str, args: dict[str, Any]) -> str:
    """执行工具，返回给对话引擎的结果文本。"""
    if name == "set_reminder":
        content = str(args.get("content", "提醒事项"))
        remind_at = str(args.get("remind_at", ""))
        row = db.create_reminder(session_id, content, remind_at)
        return f"已创建提醒 #{row['id']}：{content}（{_parse_remind_at(remind_at)}）"
    if name == "get_current_time":
        now = datetime.now(timezone.utc).astimezone()
        return f"现在是 {now.strftime('%Y年%m月%d日 %H:%M %A')}（UTC{now.strftime('%z')}）"
    if name == "query_weather":
        city = str(args.get("city", "上海"))
        return f"{city}今日天气：多云转晴，24~31℃，东南风 3 级（演示数据）"
    if name == "web_search":
        q = str(args.get("query", ""))
        return f"关于「{q}」的搜索结果：未接入真实搜索，这是演示占位结果（共 3 条）"
    raise ValueError(f"未知工具：{name}")

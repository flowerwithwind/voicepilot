"""工具注册表：意图检测 + 执行（提醒/时间/天气/搜索/数据查询）。

M2 以规则检测为主；LLM 模式通过 tool schema 调用同一执行器。
敏感操作（reminder / query_data 的删除、全量导出、订单明细）需要前端二次确认后才执行。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import query_data
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
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": (
                "查询内置电商样例数据库（orders 订单 / products 商品库存 / customers 客户）："
                "list 明细列表、summary 汇总统计、export 全量导出、delete 删除；"
                "其中删除、全量导出、订单明细属敏感操作，会请求用户二次确认"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "enum": ["orders", "products", "customers"],
                        "description": "数据表：orders 订单 / products 商品库存 / customers 客户",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["list", "summary", "export", "delete"],
                        "description": "操作：list 明细列表 / summary 汇总统计 / export 全量导出（敏感） / delete 删除（敏感，必须带筛选条件）",
                    },
                    "filters": {
                        "type": "object",
                        "description": "筛选条件：status 订单状态 / city 城市 / customer 客户名 / amount_gt、amount_lt 金额范围 / stock_lt、stock_gt 库存范围 / category 分类 / name、keyword 关键字",
                        "properties": {
                            "status": {"type": "string"},
                            "city": {"type": "string"},
                            "customer": {"type": "string"},
                            "keyword": {"type": "string"},
                            "amount_gt": {"type": "number"},
                            "amount_lt": {"type": "number"},
                            "stock_lt": {"type": "number"},
                            "stock_gt": {"type": "number"},
                            "category": {"type": "string"},
                            "name": {"type": "string"},
                        },
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "返回条数上限，默认 10",
                    },
                },
                "required": ["table"],
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
_SEARCH_RE = re.compile(r"(?:搜索|查一下|查查|百度|搜一下)\s*(?P<query>.{1,40})")

# ---- C3 query_data 规则意图（无 Key 演示：关键词 → SQL 模板） ----
_DATA_ORDER_SUMMARY_RE = re.compile(r"(?:订单汇总|订单统计|销售额|卖了多少钱|多少订单|订单总数|总金额)")
_DATA_ORDER_DETAIL_RE = re.compile(r"(?:订单明细|查看订单|查订单|订单列表|订单详情|有哪些订单|看看订单|订单)")
_DATA_STOCK_RE = re.compile(r"(?:库存|缺货|补货)")
_DATA_PRODUCT_RE = re.compile(r"(?:有哪些商品|商品列表|产品列表|查商品|看看商品|商品)")
_DATA_CUSTOMER_RE = re.compile(r"(?:客户|会员|用户列表|有哪些客户)")
_DATA_EXPORT_RE = re.compile(r"(?:导出|全量|全部数据|下载数据)")
_DATA_DELETE_RE = re.compile(r"(?:删除|清空|移除).{0,8}(?:订单|数据)")
_DATA_CITY_RE = re.compile(r"(北京|上海|广州|深圳|杭州|成都)")
_DATA_STATUS_RE = re.compile(r"(未发货|待发货|已发货|已完成|已取消)")
_DATA_STOCK_LT_RE = re.compile(r"(?:库存)?(?:不足|少于|低于|小于)\s*(\d+)")
_DATA_AMOUNT_GT_RE = re.compile(r"(?:超过|高于|大于|以上)\s*(\d+)\s*元?")
_DATA_AMOUNT_LT_RE = re.compile(r"(?:低于|少于|小于|不超过)\s*(\d+)\s*元?")

_QUERY_DATA_ACTION_LABELS = {"list": "明细", "summary": "汇总", "export": "全量导出", "delete": "删除"}
_QUERY_DATA_TABLE_LABELS = {"orders": "订单", "products": "商品库存", "customers": "客户"}


def is_tool_sensitive(name: str, args: dict[str, Any]) -> bool:
    """工具级敏感判定：query_data 按参数（删除 / 全量导出 / 订单明细）判定。"""
    if name in SENSITIVE_TOOLS:
        return True
    if name == "query_data":
        return query_data.is_sensitive(args)
    return False


def query_data_preview(args: dict[str, Any]) -> str:
    """数据查询预览文案（供二次确认弹窗展示）。"""
    table = _QUERY_DATA_TABLE_LABELS.get(str(args.get("table") or ""), "数据表")
    action = _QUERY_DATA_ACTION_LABELS.get(str(args.get("action") or "list"), str(args.get("action") or "list"))
    return f"数据查询：{table} {action}"


def _query_data_args(text: str, table: str, action: str = "list") -> dict[str, Any]:
    """规则模式：关键词 → query_data 参数（表 / 动作 / 筛选条件 / limit）。"""
    filters: dict[str, Any] = {}
    m = _DATA_STATUS_RE.search(text)
    if m and table == "orders":
        filters["status"] = m.group(1)
    m = _DATA_CITY_RE.search(text)
    if m and table in ("orders", "customers"):
        filters["city"] = m.group(1)
    m = _DATA_AMOUNT_GT_RE.search(text)
    if m and table == "orders":
        filters["amount_gt"] = int(m.group(1))
    m = _DATA_AMOUNT_LT_RE.search(text)
    if m and table == "orders":
        filters["amount_lt"] = int(m.group(1))
    m = _DATA_STOCK_LT_RE.search(text)
    if m and table == "products":
        filters["stock_lt"] = int(m.group(1))
    return {"table": table, "action": action, "filters": filters, "limit": 10}


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
    # C3：数据查询（先于通用搜索，避免「查订单」等被吞进 web_search）
    if _DATA_DELETE_RE.search(t):
        table = "products" if _DATA_STOCK_RE.search(t) else "orders"
        return "query_data", _query_data_args(t, table, action="delete")
    if _DATA_EXPORT_RE.search(t):
        if _DATA_STOCK_RE.search(t):
            table = "products"
        elif _DATA_CUSTOMER_RE.search(t):
            table = "customers"
        else:
            table = "orders"
        return "query_data", _query_data_args(t, table, action="export")
    if _DATA_ORDER_SUMMARY_RE.search(t):
        return "query_data", _query_data_args(t, "orders", action="summary")
    if _DATA_ORDER_DETAIL_RE.search(t):
        return "query_data", _query_data_args(t, "orders", action="list")
    if _DATA_STOCK_RE.search(t) or _DATA_PRODUCT_RE.search(t):
        return "query_data", _query_data_args(t, "products", action="list")
    if _DATA_CUSTOMER_RE.search(t):
        return "query_data", _query_data_args(t, "customers", action="list")
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
    if name == "query_data":
        return query_data.run_query(args)
    raise ValueError(f"未知工具：{name}")

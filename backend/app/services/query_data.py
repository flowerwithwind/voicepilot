"""C3 query_data 工具：内置 SQLite 样例数据库（电商订单 / 商品库存 / 客户）。

样例库独立于主库（data/querydata.db），应用启动时幂等初始化种子数据，
所有查询走参数化 SQL；删除 / 全量导出 / 订单明细属敏感操作，由上层二次确认把关。
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.config import DATA_DIR

QUERY_DB_PATH = DATA_DIR / "querydata.db"

TABLES = {"orders", "products", "customers"}
ACTIONS = {"list", "summary", "export", "delete"}
TABLE_LABELS = {"orders": "订单", "products": "商品库存", "customers": "客户"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    phone TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    stock INTEGER NOT NULL,
    price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    status TEXT NOT NULL,
    amount REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""

# 每个表允许的筛选键（未知键在参数校验阶段拒绝）
_FILTER_KEYS = {
    "orders": {"status", "city", "customer", "keyword", "amount_gt", "amount_lt"},
    "products": {"category", "name", "keyword", "stock_lt", "stock_gt"},
    "customers": {"city", "name", "keyword"},
}
_NUMERIC_FILTERS = {"amount_gt", "amount_lt", "stock_gt", "stock_lt"}
_STATUSES = {"已发货", "待发货", "已完成", "已取消"}

_SEED_CUSTOMERS = [
    ("张三", "北京", "13800000001"),
    ("李四", "上海", "13800000002"),
    ("王五", "广州", "13800000003"),
    ("赵六", "深圳", "13800000004"),
    ("钱七", "杭州", "13800000005"),
    ("孙八", "北京", "13800000006"),
]
_SEED_PRODUCTS = [
    ("智能手机", "数码", 42, 5999.0),
    ("无线耳机", "数码", 8, 899.0),
    ("机械键盘", "外设", 3, 429.0),
    ("显示器", "数码", 15, 1299.0),
    ("运动水杯", "生活", 120, 59.0),
    ("蓝牙音箱", "数码", 5, 349.0),
    ("办公椅", "家居", 2, 799.0),
    ("台灯", "家居", 30, 129.0),
]
_SEED_ORDERS = [
    (1, 1, "已发货", 5999.0, "2026-07-01"),
    (1, 2, "已发货", 899.0, "2026-07-03"),
    (2, 3, "待发货", 429.0, "2026-07-05"),
    (3, 4, "已发货", 1299.0, "2026-07-08"),
    (4, 5, "已完成", 59.0, "2026-07-10"),
    (5, 6, "待发货", 349.0, "2026-07-12"),
    (2, 7, "已完成", 799.0, "2026-07-15"),
    (6, 8, "已发货", 129.0, "2026-07-18"),
    (3, 1, "待发货", 5999.0, "2026-07-20"),
    (4, 2, "已发货", 899.0, "2026-07-22"),
]


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(QUERY_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    """灌入种子数据（幂等调用方保证先判空）。"""
    conn.executemany(
        "INSERT INTO customers(name, city, phone) VALUES(?, ?, ?)", _SEED_CUSTOMERS
    )
    conn.executemany(
        "INSERT INTO products(name, category, stock, price) VALUES(?, ?, ?, ?)",
        _SEED_PRODUCTS,
    )
    conn.executemany(
        "INSERT INTO orders(customer_id, product_id, status, amount, created_at) "
        "VALUES(?, ?, ?, ?, ?)",
        _SEED_ORDERS,
    )


def init_db() -> None:
    """建表 + 空库时灌入种子数据（幂等，随应用启动初始化）。"""
    conn = _conn()
    try:
        conn.executescript(_SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
            _seed(conn)
        conn.commit()
    finally:
        conn.close()


def reseed() -> None:
    """清空样例库并重新灌入种子数据（测试夹具用，重建表以重置自增 id）。"""
    conn = _conn()
    try:
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.execute("DROP TABLE IF EXISTS customers")
        conn.executescript(_SCHEMA)
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def is_sensitive(args: dict[str, Any]) -> bool:
    """query_data 敏感判定：删除 / 全量导出 / 订单明细需要二次确认。"""
    action = str(args.get("action") or "list")
    table = str(args.get("table") or "")
    return action in ("delete", "export") or (table == "orders" and action == "list")


def _validate(args: dict[str, Any]) -> tuple[str, str, dict[str, Any], int]:
    """参数校验：表名 / 动作 / 筛选键 / limit / 删除前置条件。"""
    table = str(args.get("table") or "").strip()
    if table not in TABLES:
        raise ValueError(f"未知数据表：{table or '（空）'}（可选：orders/products/customers）")
    action = str(args.get("action") or "list").strip()
    if action not in ACTIONS:
        raise ValueError(f"未知操作：{action or '（空）'}（可选：list/summary/export/delete）")
    limit = args.get("limit", 10)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit 必须为整数")
    if not 1 <= limit <= 100:
        raise ValueError("limit 需在 1~100 之间")
    raw_filters = args.get("filters") or {}
    if not isinstance(raw_filters, dict):
        raise TypeError("filters 必须为对象")
    filters: dict[str, Any] = {}
    for key, value in raw_filters.items():
        if key not in _FILTER_KEYS[table]:
            raise ValueError(f"数据表 {table} 不支持筛选条件：{key}")
        if value is None or value == "":
            continue
        if key in _NUMERIC_FILTERS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"筛选条件 {key} 必须为数值")
            filters[key] = float(value)
        elif key == "status" and str(value) not in _STATUSES:
            raise ValueError(f"未知订单状态：{value}（可选：{'/'.join(sorted(_STATUSES))}）")
        else:
            filters[key] = str(value).strip()
    if action == "delete" and not filters:
        raise ValueError("删除操作必须指定至少一个筛选条件，避免误删全部数据")
    return table, action, filters, limit


def _where(table: str, filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """按白名单拼参数化 WHERE（表名已由 _validate 白名单校验）。"""
    clauses: list[str] = []
    params: list[Any] = []
    for key, value in filters.items():
        if table == "orders":
            if key == "status":
                clauses.append("o.status = ?")
                params.append(value)
            elif key == "city":
                clauses.append("c.city = ?")
                params.append(value)
            elif key == "customer":
                clauses.append("c.name LIKE ?")
                params.append(f"%{value}%")
            elif key == "keyword":
                clauses.append("(p.name LIKE ? OR c.name LIKE ?)")
                params.extend([f"%{value}%", f"%{value}%"])
            elif key == "amount_gt":
                clauses.append("o.amount > ?")
                params.append(value)
            elif key == "amount_lt":
                clauses.append("o.amount < ?")
                params.append(value)
        elif table == "products":
            if key == "category":
                clauses.append("category = ?")
                params.append(value)
            elif key in ("name", "keyword"):
                clauses.append("name LIKE ?")
                params.append(f"%{value}%")
            elif key == "stock_lt":
                clauses.append("stock < ?")
                params.append(value)
            elif key == "stock_gt":
                clauses.append("stock > ?")
                params.append(value)
        elif table == "customers":
            if key == "city":
                clauses.append("city = ?")
                params.append(value)
            elif key in ("name", "keyword"):
                clauses.append("name LIKE ?")
                params.append(f"%{value}%")
    return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params


def _base(table: str, filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """FROM/JOIN + WHERE 片段（orders 联表展示客户与商品名）。"""
    where, params = _where(table, filters)
    if table == "orders":
        base = (
            "FROM orders o "
            "JOIN customers c ON c.id = o.customer_id "
            "JOIN products p ON p.id = o.product_id"
        )
    else:
        base = f"FROM {table}"
    return f"{base} {where}".strip(), params


def _fmt_num(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"


def _fmt_filters(filters: dict[str, Any]) -> str:
    return "、".join(f"{k}={v}" for k, v in filters.items()) or "无"


def _run_summary(table: str, filters: dict[str, Any]) -> str:
    conn = _conn()
    try:
        base, params = _base(table, filters)
        if table == "orders":
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt, COALESCE(SUM(o.amount), 0) AS total {base}",
                params,
            ).fetchone()
            status_rows = conn.execute(
                f"SELECT o.status, COUNT(*) AS cnt {base} GROUP BY o.status ORDER BY cnt DESC",
                params,
            ).fetchall()
            parts = "，".join(f"{r['status']} {r['cnt']} 笔" for r in status_rows) or "无"
            cond = f"（条件：{_fmt_filters(filters)}）" if filters else ""
            return (
                f"订单汇总（匹配 {row['cnt']} 笔{cond}）："
                f"总金额 ¥{_fmt_num(row['total'])}，其中 {parts}"
            )
        if table == "products":
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt, COALESCE(SUM(stock), 0) AS stock_total, "
                f"COALESCE(AVG(price), 0) AS avg_price {base}",
                params,
            ).fetchone()
            return (
                f"商品库存汇总（共 {row['cnt']} 款）：库存总量 {int(row['stock_total'])} 件，"
                f"平均单价 ¥{_fmt_num(row['avg_price'])}"
            )
        row = conn.execute(f"SELECT COUNT(*) AS cnt {base}", params).fetchone()
        city_rows = conn.execute(
            f"SELECT city, COUNT(*) AS cnt {base} GROUP BY city ORDER BY cnt DESC",
            params,
        ).fetchall()
        parts = "，".join(f"{r['city']} {r['cnt']} 位" for r in city_rows) or "无"
        return f"客户汇总（共 {row['cnt']} 位）：{parts}"
    finally:
        conn.close()


def _run_list(table: str, filters: dict[str, Any], limit: int, export: bool) -> str:
    conn = _conn()
    try:
        base, params = _base(table, filters)
        limit_sql = "" if export else " LIMIT ?"
        qparams = params if export else params + [limit]
        if table == "orders":
            rows = conn.execute(
                f"SELECT o.id, c.name AS customer, p.name AS product, o.amount, "
                f"o.status, o.created_at {base} ORDER BY o.id DESC{limit_sql}",
                qparams,
            ).fetchall()
            headers = ["ID", "客户", "商品", "金额(元)", "状态", "日期"]
            cells = [
                [
                    str(r["id"]),
                    r["customer"],
                    r["product"],
                    _fmt_num(r["amount"]),
                    r["status"],
                    r["created_at"],
                ]
                for r in rows
            ]
            title = "订单明细"
        elif table == "products":
            rows = conn.execute(
                f"SELECT id, name, category, stock, price {base} ORDER BY id{limit_sql}",
                qparams,
            ).fetchall()
            headers = ["ID", "商品", "分类", "库存", "单价(元)"]
            cells = [
                [str(r["id"]), r["name"], r["category"], str(r["stock"]), _fmt_num(r["price"])]
                for r in rows
            ]
            title = "商品库存"
        else:
            rows = conn.execute(
                f"SELECT id, name, city, phone {base} ORDER BY id{limit_sql}",
                qparams,
            ).fetchall()
            headers = ["ID", "客户", "城市", "电话"]
            cells = [[str(r["id"]), r["name"], r["city"], r["phone"]] for r in rows]
            title = "客户列表"
        total = conn.execute(f"SELECT COUNT(*) AS cnt {base}", params).fetchone()["cnt"]
        cond = f"（条件：{_fmt_filters(filters)}）" if filters else ""
        if not cells:
            return f"{title}{cond}：匹配 0 条，无数据"
        if export:
            note = f"全量导出 {total} 条"
        elif total > len(rows):
            note = f"共 {total} 条，展示前 {len(rows)} 条"
        else:
            note = f"共 {total} 条"
        head = "| " + " | ".join(headers) + " |"
        sep = "|" + "|".join(":---" for _ in headers) + "|"
        body = "\n".join("| " + " | ".join(cell) + " |" for cell in cells)
        return f"{title}{cond}（{note}）：\n{head}\n{sep}\n{body}"
    finally:
        conn.close()


def _delete_where(table: str, filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """按白名单拼参数化 DELETE WHERE（orders 通过子查询关联客户 / 商品）。"""
    clauses: list[str] = []
    params: list[Any] = []
    if table == "orders":
        for key, value in filters.items():
            if key == "status":
                clauses.append("status = ?")
                params.append(value)
            elif key == "city":
                clauses.append("customer_id IN (SELECT id FROM customers WHERE city = ?)")
                params.append(value)
            elif key == "customer":
                clauses.append("customer_id IN (SELECT id FROM customers WHERE name LIKE ?)")
                params.append(f"%{value}%")
            elif key == "keyword":
                clauses.append(
                    "(customer_id IN (SELECT id FROM customers WHERE name LIKE ?) "
                    "OR product_id IN (SELECT id FROM products WHERE name LIKE ?))"
                )
                params.extend([f"%{value}%", f"%{value}%"])
            elif key == "amount_gt":
                clauses.append("amount > ?")
                params.append(value)
            elif key == "amount_lt":
                clauses.append("amount < ?")
                params.append(value)
    else:
        for key, value in filters.items():
            if key == "category":
                clauses.append("category = ?")
                params.append(value)
            elif key in ("name", "keyword"):
                clauses.append("name LIKE ?")
                params.append(f"%{value}%")
            elif key == "stock_lt":
                clauses.append("stock < ?")
                params.append(value)
            elif key == "stock_gt":
                clauses.append("stock > ?")
                params.append(value)
    return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params


def _run_delete(table: str, filters: dict[str, Any]) -> str:
    conn = _conn()
    try:
        where, params = _delete_where(table, filters)
        # table 已由 _validate 白名单校验（orders/products/customers）
        cur = conn.execute(f"DELETE FROM {table} {where}", params)
        conn.commit()
        label = TABLE_LABELS.get(table, table)
        return f"已删除 {cur.rowcount} 条{label}记录（条件：{_fmt_filters(filters)}）"
    finally:
        conn.close()


def run_query(args: dict[str, Any]) -> str:
    """校验并执行 query_data，返回格式化结果文本（表格 / 摘要）。"""
    table, action, filters, limit = _validate(args)
    try:
        if action == "summary":
            return _run_summary(table, filters)
        if action == "delete":
            return _run_delete(table, filters)
        return _run_list(table, filters, limit, export=action == "export")
    except sqlite3.Error as e:
        raise ValueError(f"数据查询执行失败：{e}") from e

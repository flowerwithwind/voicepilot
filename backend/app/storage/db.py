"""SQLite 存储：会话与消息（WAL、外键、全参数化 SQL）。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import DB_PATH
from app.utils.audio_path import normalize_audio_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '新会话',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    audio_path TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def init_db() -> None:
    """建表（幂等）。"""
    conn = _conn()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def create_session(title: str | None = None) -> dict[str, Any]:
    """新建会话，返回行 dict。"""
    now = now_iso()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO sessions(title, created_at, updated_at) VALUES(?, ?, ?)",
            (title or "新会话", now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def add_message(
    session_id: int,
    role: str,
    content: str,
    audio_path: str | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    """追加消息并刷新会话 updated_at。"""
    now = now_iso()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO messages(session_id, role, content, audio_path, duration_ms, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (session_id, role, content, audio_path, duration_ms, now),
        )
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        conn.commit()
        row = conn.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_session(session_id: int) -> dict[str, Any] | None:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_session(session_id: int) -> None:
    """删除会话（消息级联删除）。"""
    conn = _conn()
    try:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS message_count "
            "FROM sessions s ORDER BY s.updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_messages(session_id: int) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        messages = [dict(r) for r in rows]
        # 读取侧归一化：历史反斜杠 audio_path 统一为正斜杠（KN-03）
        for m in messages:
            m["audio_path"] = normalize_audio_path(m["audio_path"])
        return messages
    finally:
        conn.close()


def wipe_data() -> None:
    """清空业务数据（测试夹具用）。"""
    conn = _conn()
    try:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM reminders")
        conn.execute("DELETE FROM settings")
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: Any = None) -> Any:
    """读取设置（JSON 解码）。"""
    conn = _conn()
    try:
        row = conn.execute("SELECT value_json FROM settings WHERE key=?", (key,)).fetchone()
        return jloads(row["value_json"], default) if row else default
    finally:
        conn.close()


def set_setting(key: str, value: Any) -> None:
    """写入设置（UPSERT）。"""
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO settings(key, value_json) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def create_reminder(session_id: int, content: str, remind_at: str) -> dict[str, Any]:
    now = now_iso()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO reminders(session_id, content, remind_at, created_at) VALUES(?,?,?,?)",
            (session_id, content, remind_at, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM reminders WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_reminders(limit: int = 50) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM reminders ORDER BY remind_at ASC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_reminder(reminder_id: int) -> bool:
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def jloads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default

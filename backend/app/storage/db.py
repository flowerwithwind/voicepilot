"""SQLite 存储：会话与消息（WAL、外键、全参数化 SQL）。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import DB_PATH

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
        return [dict(r) for r in rows]
    finally:
        conn.close()


def wipe_data() -> None:
    """清空业务数据（测试夹具用）。"""
    conn = _conn()
    try:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        conn.close()


def jloads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default

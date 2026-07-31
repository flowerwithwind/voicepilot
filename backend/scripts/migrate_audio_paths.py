"""一次性数据迁移：messages.audio_path 反斜杠 → 正斜杠（KN-03）。

- 用法（backend/ 目录下）：python scripts/migrate_audio_paths.py
- 幂等：SQLite replace() 对已归一化的行无副作用，可重复执行；第二次运行时受影响行数为 0。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_UPDATE_SQL = "UPDATE messages SET audio_path = replace(audio_path, '\\', '/') WHERE audio_path LIKE '%\\%'"


def db_path() -> Path:
    """返回项目 DB 路径（脚本从 backend/ 或仓库根目录运行均可）。"""
    backend_dir = Path(__file__).resolve().parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from app.config import DB_PATH

    return DB_PATH


def migrate(path: Path | None = None) -> int:
    """执行归一化 UPDATE，返回受影响行数。"""
    conn = sqlite3.connect(path or db_path())
    try:
        cur = conn.execute(_UPDATE_SQL)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def main() -> None:
    changed = migrate()
    print(f"[migrate_audio_paths] audio_path 归一化完成，受影响 {changed} 行")


if __name__ == "__main__":
    main()

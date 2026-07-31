"""KN-03 迁移脚本测试：一次性归一化 + 幂等可重复执行。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.storage import db

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "migrate_audio_paths.py"


def _load_migrate_module():
    spec = importlib.util.spec_from_file_location("migrate_audio_paths", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migrate_audio_paths_idempotent(client):
    """反斜杠旧数据归一化为正斜杠，第二次执行无副作用（0 行）。"""
    mod = _load_migrate_module()
    sid = db.create_session()["id"]
    db.add_message(sid, "user", "旧数据", audio_path="realtime\\legacy.wav", duration_ms=500)
    db.add_message(sid, "user", "新数据", audio_path="realtime/new.wav", duration_ms=500)

    assert mod.migrate() == 1

    rows = db.list_messages(sid)
    assert rows[0]["audio_path"] == "realtime/legacy.wav"
    assert rows[1]["audio_path"] == "realtime/new.wav"

    assert mod.migrate() == 0
    assert db.list_messages(sid)[0]["audio_path"] == "realtime/legacy.wav"

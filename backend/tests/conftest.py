"""pytest 全局夹具：临时数据目录 + 测试客户端 + 录音构造工具。"""
from __future__ import annotations

import io
import os
import tempfile
import wave

os.environ["VOICEPILOT_DATA_DIR"] = tempfile.mkdtemp(prefix="voicepilot-test-")
os.environ["VOICEPILOT_ASR"] = "rule"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import db


@pytest.fixture()
def client():
    with TestClient(app) as c:
        db.wipe_data()
        yield c


def make_wav_bytes(seconds: float = 0.5, rate: int = 8000) -> bytes:
    """生成静音 wav（16bit 单声道），用于上传测试。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()

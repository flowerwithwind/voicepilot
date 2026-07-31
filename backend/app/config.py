"""全局配置：数据目录、上传限制、引擎选择（环境变量可覆盖）。"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.getenv("VOICEPILOT_DATA_DIR", str(PROJECT_ROOT / "data")))
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "voicepilot.db"

# 上传限制
ALLOWED_AUDIO_EXTS = {".webm", ".ogg", ".wav", ".mp3", ".m4a"}
MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20MB
MAX_DURATION_SECONDS = 600.0  # 10 分钟

# 引擎选择：rule（演示回声）/ openai（OpenAI 兼容 ASR，M2 接入）
ASR_ENGINE = os.getenv("VOICEPILOT_ASR", "rule")
# OpenAI 兼容 Whisper 端点（M2 使用）
ASR_BASE_URL = os.getenv("VOICEPILOT_ASR_BASE_URL", "")
ASR_API_KEY = os.getenv("VOICEPILOT_ASR_API_KEY", "")
ASR_MODEL = os.getenv("VOICEPILOT_ASR_MODEL", "whisper-1")

VERSION = "1.1.0"
APP_NAME = "VoicePilot"


def ensure_dirs() -> None:
    """确保数据目录存在（幂等）。"""
    for d in (DATA_DIR, AUDIO_DIR):
        d.mkdir(parents=True, exist_ok=True)

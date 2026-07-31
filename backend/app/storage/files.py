"""音频文件安全存储：扩展名白名单、uuid 存储名、大小限制。"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import ALLOWED_AUDIO_EXTS, AUDIO_DIR, MAX_AUDIO_BYTES
from app.utils.audio_path import normalize_audio_path

_FILENAME_RE = re.compile(r"^[^\/:*?<>|]{1,200}\.(webm|ogg|wav|mp3|m4a)$", re.IGNORECASE)


def ext_of(name: str) -> str:
    return Path(name or "").suffix.lower()


def is_allowed(name: str) -> bool:
    """扩展名白名单（含文件名基础合法性校验）。"""
    if not _FILENAME_RE.match(name or ""):
        return False
    return ext_of(name) in ALLOWED_AUDIO_EXTS


def safe_store(upload: UploadFile) -> tuple[Path, int]:
    """保存为 uuid 存储名，返回 (路径, 字节数)。超限抛 ValueError。"""
    data = upload.file.read()
    size = len(data)
    if size == 0:
        raise ValueError("音频文件为空")
    if size > MAX_AUDIO_BYTES:
        raise ValueError(f"音频超过大小限制（最大 {MAX_AUDIO_BYTES // 1024 // 1024}MB）")
    ext = ext_of(upload.filename or "")
    if ext not in ALLOWED_AUDIO_EXTS:
        raise ValueError("不支持的音频格式")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIO_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return path, size

REALTIME_DIR = AUDIO_DIR / "realtime"


def save_realtime_pcm(pcm16: bytes, sample_rate: int = 16000) -> Path:
    """保存实时语音分段为 WAV（M4 回听用），返回绝对路径。"""
    from app.audio.pcm import write_wav

    REALTIME_DIR.mkdir(parents=True, exist_ok=True)
    path = REALTIME_DIR / f"{uuid.uuid4().hex}.wav"
    write_wav(path, pcm16, sample_rate)
    return path

def safe_audio_path(rel: str) -> Path | None:
    """将相对 AUDIO_DIR 的路径解析为绝对路径；越界（路径穿越）返回 None。
    读取侧归一化：Windows 反斜杠路径（旧数据）统一为正斜杠（KN-03）。"""
    try:
        base = AUDIO_DIR.resolve()
        target = (base / normalize_audio_path(rel)).resolve()
    except OSError:
        return None
    if target != base and base not in target.parents:
        return None
    return target

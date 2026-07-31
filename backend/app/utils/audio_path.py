"""audio_path 归一化工具：Windows 反斜杠 → POSIX 正斜杠（KN-03）。"""
from __future__ import annotations


def normalize_audio_path(value: str | None) -> str | None:
    """将 Windows 风格反斜杠分隔符统一为 POSIX 正斜杠；幂等，None 原样返回。"""
    if value is None:
        return None
    return value.replace("\\", "/")

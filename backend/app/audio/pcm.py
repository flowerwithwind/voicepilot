"""PCM16 工具：16bit 单声道小端 PCM 的 WAV 封装（实时链路分段存储用）。"""
from __future__ import annotations

import wave
from pathlib import Path


def write_wav(path: Path, pcm16: bytes, sample_rate: int = 16000) -> None:
    """将 16bit 单声道 PCM 写入 WAV 文件（供 ASR 读取）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)


def pcm_duration(pcm16: bytes, sample_rate: int = 16000) -> float:
    """按字节数估算 PCM 时长（秒）。"""
    return (len(pcm16) // 2) / float(sample_rate or 1)

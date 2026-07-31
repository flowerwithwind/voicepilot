"""ASR 适配层：Provider 抽象 + 规则回声兜底（无 Key 可演示）。

M1 提供 RuleEchoProvider；M2 起可扩展 OpenAI 兼容 / FunASR / 厂商 Provider。
"""
from __future__ import annotations

import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.config import ASR_ENGINE


class ASRError(Exception):
    """ASR 处理失败（对外统一错误类型）。"""


@dataclass
class TranscriptionResult:
    text: str
    engine: str
    elapsed_ms: int
    duration: float | None = None
    partials: list[str] = field(default_factory=list)  # M3 流式增量预留


class ASRProvider(ABC):
    """ASR 引擎抽象。"""

    name: str = "abstract"

    @abstractmethod
    def transcribe(self, audio_path: Path, duration: float | None = None) -> TranscriptionResult:
        """转写音频文件为文本。"""


def _read_wav_duration(audio_path: Path) -> float | None:
    """仅对 wav 精确读取时长；其他格式返回 None。"""
    try:
        with wave.open(str(audio_path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate() or 1)
    except (wave.Error, OSError, ZeroDivisionError):
        return None


class RuleEchoProvider(ASRProvider):
    """演示兜底：根据音频元数据生成回声文本，验证整条管道可用。"""

    name = "rule"

    def transcribe(self, audio_path: Path, duration: float | None = None) -> TranscriptionResult:
        size_kb = audio_path.stat().st_size / 1024.0
        real_duration = _read_wav_duration(audio_path) or duration
        dur_txt = f"{real_duration:.1f} 秒" if real_duration is not None else "未知时长"
        text = (
            f"（演示转写）已识别 {dur_txt} 语音，音频 {size_kb:.0f} KB。"
            "当前为规则回声引擎，配置 ASR 引擎后返回真实转写文本。"
        )
        return TranscriptionResult(
            text=text,
            engine=self.name,
            elapsed_ms=8,
            duration=real_duration,
            partials=[text],
        )


_PROVIDERS: dict[str, type[ASRProvider]] = {
    "rule": RuleEchoProvider,
}


def get_provider() -> ASRProvider:
    """按配置实例化 ASR Provider（未知引擎回退 rule）。"""
    cls = _PROVIDERS.get(ASR_ENGINE, RuleEchoProvider)
    return cls()


def available_engines() -> list[str]:
    return sorted(_PROVIDERS)

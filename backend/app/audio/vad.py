"""能量 VAD：RMS 阈值检测语音起止，驱动自动分段 / 自动停止。

输入：16bit 单声道 PCM（小端）；输出事件：
- {"type": "speech_start"}
- {"type": "speech_end", "duration": float}  （持续静音超过 silence_ms 触发）
- {"type": "speech_continue", "duration": float}
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field


def rms(pcm16: bytes) -> float:
    """16bit 单声道 PCM 的归一化 RMS 能量（0~1）。"""
    if not pcm16:
        return 0.0
    n = len(pcm16) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", pcm16[: n * 2])
    return math.sqrt(sum(s * s for s in samples) / n) / 32768.0


@dataclass
class EnergyVAD:
    """基于能量阈值的端点检测器。"""

    threshold: float = 0.015
    sample_rate: int = 16000
    silence_ms: int = 700
    min_speech_ms: int = 250

    _speaking: bool = field(default=False, init=False)
    _speech_samples: int = field(default=0, init=False)
    _silence_samples: int = field(default=0, init=False)
    _last_duration: float = field(default=0.0, init=False)

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def reset(self) -> None:
        self._speaking = False
        self._speech_samples = 0
        self._silence_samples = 0
        self._last_duration = 0.0  # 每段语音独立计时，保证下一段仍能触发 speech_continue

    def feed(self, pcm16: bytes, sample_rate: int | None = None) -> list[dict]:
        """喂入一帧 PCM，返回本轮触发的事件列表。"""
        if sample_rate:
            self.sample_rate = sample_rate
        energy = rms(pcm16)
        active = energy >= self.threshold
        events: list[dict] = []
        frames = len(pcm16) // 2  # 16bit mono

        if active:
            if not self._speaking:
                # 需要积累足够长度才判定为语音，避免瞬态噪声误触发
                self._silence_samples = 0
            self._speech_samples += frames
            self._silence_samples = 0
            if not self._speaking and self._speech_samples >= self._ms_to_frames(self.min_speech_ms):
                self._speaking = True
                events.append({"type": "speech_start"})
            elif self._speaking:
                duration = self._speech_samples / self.sample_rate
                if duration - self._last_duration >= 0.25:
                    self._last_duration = duration
                    events.append({"type": "speech_continue", "duration": duration})
        else:
            if self._speaking:
                self._silence_samples += frames
                if self._silence_samples >= self._ms_to_frames(self.silence_ms):
                    duration = self._speech_samples / self.sample_rate
                    events.append({"type": "speech_end", "duration": duration})
                    self.reset()
            else:
                # 非语音期间的噪声不积累
                self._silence_samples = 0

        return events

    def force_end(self) -> dict | None:
        """客户端手动停止时强制结束当前语音段；无活动语音返回 None。"""
        if not self._speaking:
            return None
        duration = self._speech_samples / self.sample_rate
        self.reset()
        return {"type": "speech_end", "duration": duration}

    def _ms_to_frames(self, ms: int) -> int:
        return max(1, int(self.sample_rate * ms / 1000))

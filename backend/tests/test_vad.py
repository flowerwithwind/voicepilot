"""VAD 单元测试：RMS 能量、事件序列、强制结束、PCM→WAV 封装。"""
from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

import pytest

from app.audio.pcm import pcm_duration, write_wav
from app.audio.vad import EnergyVAD, rms


def sine_pcm(seconds: float, freq: int = 440, amp: float = 0.4, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    return struct.pack(
        f"<{n}h",
        *(int(32767 * amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)),
    )


def silence_pcm(seconds: float, rate: int = 16000) -> bytes:
    return b"\x00\x00" * int(rate * seconds)


def test_rms_basic():
    assert rms(b"") == 0.0
    assert rms(b"\x00\x00" * 10) == 0.0
    # 满幅方波（交替 ±32767）RMS ≈ 1.0
    sq = struct.pack(f"<{100}h", *([32767, -32767] * 50))
    assert rms(sq) == pytest.approx(1.0, abs=0.05)


def test_silence_no_events():
    vad = EnergyVAD()
    events = vad.feed(silence_pcm(0.5))
    events += vad.feed(silence_pcm(0.5))
    assert events == []
    assert not vad.is_speaking


def test_speech_start_continue_end_sequence():
    vad = EnergyVAD()
    events = vad.feed(sine_pcm(0.1))  # 低于 min_speech_ms，不触发
    assert events == []
    assert not vad.is_speaking
    events += vad.feed(sine_pcm(0.3))  # 累计 0.4s → speech_start
    kinds = [e["type"] for e in events]
    assert "speech_start" in kinds
    assert vad.is_speaking
    events += vad.feed(sine_pcm(0.5))  # 继续语音 → speech_continue
    assert any(e["type"] == "speech_continue" for e in events)
    events += vad.feed(silence_pcm(0.8))  # 静音 0.7s+ → speech_end
    end = [e for e in events if e["type"] == "speech_end"]
    assert len(end) == 1
    assert end[0]["duration"] == pytest.approx(0.9, abs=0.1)
    assert not vad.is_speaking


def test_force_end():
    vad = EnergyVAD()
    vad.feed(sine_pcm(0.4))
    assert vad.is_speaking
    ev = vad.force_end()
    assert ev is not None
    assert ev["type"] == "speech_end"
    assert not vad.is_speaking
    assert vad.force_end() is None  # 无活动语音


def test_write_wav_roundtrip():
    pcm = sine_pcm(0.25)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "seg.wav"
        write_wav(p, pcm)
        with wave.open(str(p), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getnframes() == len(pcm) // 2
            assert wf.readframes(wf.getnframes()) == pcm
    assert pcm_duration(pcm) == pytest.approx(0.25)

def test_multiple_utterances_emit_continue_each() -> None:
    """多段语音：每段都要能触发 speech_continue（regression：reset 未重置 _last_duration）。"""
    vad = EnergyVAD()
    partials: list[float] = []
    for _ in range(2):
        events = vad.feed(sine_pcm(0.1))
        events += vad.feed(sine_pcm(0.4))  # speech_start
        events += vad.feed(sine_pcm(0.4))  # speech_continue
        events += vad.feed(silence_pcm(0.8))  # speech_end
        partials.extend(e["duration"] for e in events if e["type"] == "speech_continue")
        assert not vad.is_speaking
    # 两段语音都应产生至少一次 partial（0.5s 处）；若 _last_duration 未重置，第二段将缺失
    assert len(partials) >= 2

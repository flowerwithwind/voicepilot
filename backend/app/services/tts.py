"""TTS 适配层：浏览器 speechSynthesis 引擎（后端仅透出文本帧）。

M3 实时链路使用：服务端把回复文本包装为 tts 事件帧，前端用 speechSynthesis 播报；
后续如需接入厂商引擎（如 edge-tts），可扩展 audio 字段返回 base64 音频帧。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.services import settings as settings_svc


class TTSError(Exception):
    """TTS 处理失败。"""


class TTSProvider(ABC):
    """TTS 引擎抽象。"""

    name: str = "abstract"

    @abstractmethod
    def synthesize(self, text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """合成文本，返回给前端播放的事件负载。"""


class BrowserTTSProvider(TTSProvider):
    """浏览器 speechSynthesis 模式：后端不产音频，只下发文本帧。"""

    name = "browser"

    def synthesize(self, text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"type": "tts", "text": text, "engine": self.name, "audio": None}


_PROVIDERS: dict[str, type[TTSProvider]] = {
    "browser": BrowserTTSProvider,
}


def get_provider() -> TTSProvider:
    engine = settings_svc.get_tts_settings().get("engine", "browser")
    cls = _PROVIDERS.get(engine, BrowserTTSProvider)
    return cls()


def synthesize(text: str) -> dict[str, Any]:
    """合成回复文本，返回事件帧；引擎异常时降级为浏览器文本帧。"""
    try:
        return get_provider().synthesize(text)
    except TTSError as e:
        return {
            "type": "tts",
            "text": text,
            "engine": "browser",
            "audio": None,
            "note": str(e),
        }

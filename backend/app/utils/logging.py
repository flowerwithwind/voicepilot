"""结构化日志：loguru 单例，控制台输出。"""
from __future__ import annotations

import sys

from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

# 供外部复用（测试中可通过 monkeypatch 校验）
__all__ = ["logger"]


def get_logger(name: str):
    return logger.bind(module=name)

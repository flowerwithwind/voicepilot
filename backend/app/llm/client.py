"""OpenAI 兼容 LLM 客户端：流式对话 + 工具调用解析 + 错误归一化。"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator

import httpx

DEFAULT_TIMEOUT = 30.0


class LLMError(Exception):
    """LLM 调用失败（对外统一错误类型）。"""


class LLMClient:
    """OpenAI 兼容 /chat/completions 客户端（DeepSeek 等）。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or "deepseek-chat"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        # KN-04：最近一次流式调用的可观测指标（LLM 耗时 / token 用量）
        self.last_elapsed_ms: int | None = None
        self.last_prompt_tokens: int | None = None
        self.last_completion_tokens: int | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Iterator[dict]:
        """流式对话。

        yield 事件：
          {"type": "delta", "text": str}
          {"type": "tool_call", "id": str, "name": str, "arguments": str(JSON)}
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},  # KN-04：流末回传 usage
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        # KN-04：每次调用前重置指标，避免串用上一次结果
        self.last_elapsed_ms = None
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        started = time.monotonic()
        try:
            with (
                httpx.Client(timeout=self.timeout) as client,
                client.stream("POST", self._url(), json=payload, headers=self._headers()) as resp,
            ):
                    if resp.status_code >= 400:
                        raise LLMError(
                            f"模型接口错误 {resp.status_code}: {resp.read()[:200]}"
                        )
                    tool_buf: dict[str, dict] = {}
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except ValueError:
                            continue
                        usage = chunk.get("usage")
                        if usage:
                            # KN-04：流末 usage chunk（choices 为空），记录 token 用量
                            if usage.get("prompt_tokens") is not None:
                                self.last_prompt_tokens = int(usage["prompt_tokens"])
                            if usage.get("completion_tokens") is not None:
                                self.last_completion_tokens = int(usage["completion_tokens"])
                        try:
                            delta = chunk["choices"][0].get("delta", {})
                        except (KeyError, IndexError):
                            continue
                        text = delta.get("content")
                        if text:
                            yield {"type": "delta", "text": text}
                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            slot = tool_buf.setdefault(
                                idx, {"id": tc.get("id", ""), "name": "", "arguments": ""}
                            )
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            if tc.get("function", {}).get("name"):
                                slot["name"] = tc["function"]["name"]
                            if tc.get("function", {}).get("arguments"):
                                slot["arguments"] += tc["function"]["arguments"]
                    # KN-04：流式响应结束，记录耗时（毫秒）
                    self.last_elapsed_ms = int((time.monotonic() - started) * 1000)
                    for slot in tool_buf.values():
                        yield {
                            "type": "tool_call",
                            "id": slot["id"],
                            "name": slot["name"],
                            "arguments": slot["arguments"],
                        }
        except httpx.HTTPError as e:
            raise LLMError(f"模型请求失败：{e.__class__.__name__}") from e

    def complete(self, messages: list[dict]) -> str:
        """非流式补全（工具执行后收尾等场景）。"""
        parts: list[str] = []
        for ev in self.stream_chat(messages):
            if ev["type"] == "delta":
                parts.append(ev["text"])
        return "".join(parts)

    def last_metrics(self) -> dict[str, int | None]:
        """KN-04：返回最近一次流式调用的耗时/token 指标（未采集时为 None）。"""
        return {
            "elapsed_ms": self.last_elapsed_ms,
            "prompt_tokens": self.last_prompt_tokens,
            "completion_tokens": self.last_completion_tokens,
        }

    def test(self) -> str | None:
        """连通性测试：返回错误信息或 None。"""
        if not self.api_key:
            return "未配置 API Key"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    self.base_url.rstrip("/") + "/models",
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    return f"接口返回 {resp.status_code}"
                return None
        except httpx.HTTPError as e:
            return f"{e.__class__.__name__}: 连接失败"

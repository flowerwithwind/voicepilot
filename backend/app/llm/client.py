"""OpenAI 兼容 LLM 客户端：流式对话 + 工具调用解析 + 错误归一化。"""
from __future__ import annotations

import json
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
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
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
                            delta = chunk["choices"][0].get("delta", {})
                        except (KeyError, IndexError, ValueError):
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

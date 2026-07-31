"""WebSocket 实时语音对话：音频分片 → VAD → 增量 ASR → LLM 增量 → TTS 帧。

协议（双向 JSON + 二进制帧）：
  客户端 → 服务端
    hello     {type:"hello", session_id?: number}   建立/切换会话
    ping      {type:"ping"}
    cancel    {type:"cancel"}                       打断当前回复（barge-in）
    flush     {type:"flush"}                        手动停止录音时强制结束语音段
    approval  {type:"approval", request_id, approved: bool}
    utterance {type:"utterance", text}              文本输入兜底（走同一回合流程）
    二进制帧：16bit 单声道 16kHz PCM 音频分片

  服务端 → 客户端
    ready          {type:"ready", session_id}
    pong           {type:"pong"}
    vad            {type:"vad", event:"speech_start|speech_continue|speech_end", duration?}
    asr.partial    {type:"asr.partial", text, duration}
    asr.final      {type:"asr.final", text, engine, message_id, audio_path, duration}
    delta          {type:"delta", text}
    tool_call      {type:"tool_call", request_id, tool, args, preview}
    await_approval {type:"await_approval", request_id}
    tts            {type:"tts", text, engine, audio?}
    done           {type:"done", message_id, reply}
    interrupt      {type:"interrupt"}
    error          {type:"error", detail}
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.audio.vad import EnergyVAD
from app.config import AUDIO_DIR
from app.services import settings as settings_svc
from app.services.asr import get_provider
from app.services.chat import build_history, rule_reply, tool_preview
from app.services.tools import (
    SENSITIVE_TOOLS,
    TOOL_SCHEMAS,
    detect_tool_intent,
    execute_tool,
)
from app.services.tts import synthesize
from app.storage import db
from app.storage.files import save_realtime_pcm
from app.utils.logging import get_logger

logger = get_logger("realtime")

router = APIRouter(prefix="/ws", tags=["realtime"])

PCM_SAMPLE_RATE = 16000
APPROVAL_TIMEOUT = 60.0
MAX_TURN_BYTES = 5 * 1024 * 1024  # 单段音频保护上限 5MB
STREAM_CHUNK = 6
STREAM_INTERVAL = 0.012


class RealtimeHandler:
    """单连接实时会话：VAD 分段、增量 ASR、回复流、审批与打断。"""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.vad = EnergyVAD(sample_rate=PCM_SAMPLE_RATE)
        self.audio_buf = bytearray()
        self.session_id: int | None = None
        self.busy = False
        self.barge = False
        self.closing = False
        self.turn_task: asyncio.Task | None = None
        self._approval_evt: asyncio.Event | None = None
        self._approval_request_id: str | None = None
        self._approval: dict[str, Any] | None = None

    # ---------- 生命周期 ----------
    async def run(self) -> None:
        await self.ws.accept()
        logger.info("WS 连接建立")
        try:
            while True:
                msg = await self.ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    await self._on_audio(msg["bytes"])
                elif msg.get("text"):
                    await self._on_text(msg["text"])
        except WebSocketDisconnect:
            pass
        finally:
            self.closing = True
            self._abort_turn()
            logger.info(f"WS 连接关闭 session={self.session_id}")

    # ---------- 音频 / 文本入口 ----------
    async def _on_audio(self, data: bytes) -> None:
        if not data:
            return
        await self._ensure_session()
        if len(self.audio_buf) + len(data) > MAX_TURN_BYTES:
            return  # 超长保护：丢弃后续分片，静音后自然结束
        self.audio_buf.extend(data)
        for ev in self.vad.feed(data, PCM_SAMPLE_RATE):
            await self._on_vad_event(ev)

    async def _on_text(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            await self.ws.send_json({"type": "error", "detail": "非法 JSON 消息"})
            return
        mtype = msg.get("type")
        if mtype == "hello":
            sid = msg.get("session_id")
            if sid is not None and db.get_session(sid) is None:
                logger.warning(f"hello 会话不存在，自动新建：{sid}")
            self.session_id = self._ensure_session_id(sid)
            await self.ws.send_json({"type": "ready", "session_id": self.session_id})
        elif mtype == "ping":
            await self.ws.send_json({"type": "pong"})
        elif mtype == "cancel":
            self._abort_turn()
            await self.ws.send_json({"type": "interrupt"})
        elif mtype == "flush":
            if self.busy:
                self._abort_turn()  # 手动停止时若正在回复，先打断
            ev = self.vad.force_end()
            if ev:
                await self._on_vad_event(ev)
        elif mtype == "approval":
            await self._resolve_approval(msg)
        elif mtype == "utterance":
            text = str(msg.get("text") or "").strip()
            if not text:
                await self.ws.send_json({"type": "error", "detail": "消息不能为空"})
                return
            await self._wait_turn_finish()
            await self._ensure_session()
            db.add_message(self.session_id, "user", text)
            await self._start_text_turn(text)
        else:
            await self.ws.send_json({"type": "error", "detail": f"未知消息类型：{mtype}"})

    # ---------- 会话 ----------
    async def _ensure_session(self) -> int:
        if self.session_id is None:
            self.session_id = db.create_session(title="实时语音会话")["id"]
            await self.ws.send_json({"type": "ready", "session_id": self.session_id})
        return self.session_id

    def _ensure_session_id(self, sid: int | None) -> int:
        if sid is not None and db.get_session(sid) is not None:
            return sid
        return db.create_session(title="实时语音会话")["id"]

    # ---------- VAD 事件 ----------
    async def _on_vad_event(self, ev: dict) -> None:
        payload = {"type": "vad", "event": ev["type"]}
        if "duration" in ev:
            payload["duration"] = ev["duration"]
        await self.ws.send_json(payload)
        etype = ev["type"]
        if etype == "speech_start":
            if self.busy:
                # barge-in：检测到人声，立即打断正在进行的回复
                self._abort_turn()
                await self.ws.send_json({"type": "interrupt"})
            self.audio_buf.clear()
        elif etype == "speech_continue":
            provider = get_provider()
            partial = provider.partial_text(ev.get("duration", 0.0))
            await self.ws.send_json(
                {"type": "asr.partial", "text": partial, "duration": ev.get("duration", 0.0)}
            )
        elif etype == "speech_end":
            await self._start_turn(ev.get("duration", 0.0))

    # ---------- 回合调度 ----------
    def _should_abort(self) -> bool:
        return self.barge or self.closing

    def _abort_turn(self) -> None:
        self.barge = True
        if self._approval_evt is not None:
            self._approval_evt.set()  # 唤醒等待审批的回合（按未确认处理）
        if self.turn_task is not None and not self.turn_task.done():
            self.turn_task.cancel()

    async def _wait_turn_finish(self) -> None:
        """等待旧回合完全退出（其 finally 复位 busy），避免状态竞争。"""
        if self.turn_task is None:
            return
        if not self.turn_task.done():
            try:
                await self.turn_task
            except asyncio.CancelledError:
                if not self.turn_task.cancelled():
                    raise
        self.turn_task = None

    async def _start_turn(self, duration: float) -> None:
        await self._wait_turn_finish()
        self.busy = True
        self.barge = False
        pcm = bytes(self.audio_buf)
        self.audio_buf.clear()
        self.turn_task = asyncio.create_task(self._process_turn(pcm, duration))

    async def _start_text_turn(self, text: str) -> None:
        self.busy = True
        self.barge = False

        async def run() -> None:
            try:
                await self._run_chat_turn(text)
            except Exception as e:
                logger.exception("实时文本回合失败")
                if not self._should_abort():
                    await self.ws.send_json({"type": "error", "detail": f"实时处理失败：{e}"})
            finally:
                self.busy = False

        self.turn_task = asyncio.create_task(run())

    # ---------- 语音回合：ASR → 落库 → 对话 ----------
    async def _process_turn(self, pcm: bytes, duration: float) -> None:
        try:
            wav_path = await asyncio.to_thread(save_realtime_pcm, pcm, PCM_SAMPLE_RATE)
            result = await asyncio.to_thread(get_provider().transcribe, wav_path, duration)
            if self._should_abort():
                return
            rel_path = str(wav_path.relative_to(AUDIO_DIR))
            message = db.add_message(
                self.session_id,
                "user",
                result.text,
                audio_path=rel_path,
                duration_ms=int((result.duration or duration) * 1000),
            )
            await self.ws.send_json(
                {
                    "type": "asr.final",
                    "text": result.text,
                    "engine": result.engine,
                    "message_id": message["id"],
                    "audio_path": rel_path,
                    "duration": result.duration or duration,
                }
            )
            await self._run_chat_turn(result.text)
        except Exception as e:
            logger.exception("实时语音回合失败")
            if not self._should_abort():
                await self.ws.send_json({"type": "error", "detail": f"实时处理失败：{e}"})
        finally:
            self.busy = False

    # ---------- 对话回合 ----------
    async def _run_chat_turn(self, text: str) -> None:
        intent = detect_tool_intent(text)
        if intent:
            await self._tool_flow(text, *intent)
        else:
            await self._plain_flow(text)

    async def _tool_flow(self, user_text: str, tool: str, args: dict[str, Any]) -> None:
        request_id = uuid.uuid4().hex[:12]
        preview = tool_preview(tool, args)
        await self.ws.send_json(
            {
                "type": "tool_call",
                "request_id": request_id,
                "tool": tool,
                "args": args,
                "preview": preview,
            }
        )
        approved = True
        if tool in SENSITIVE_TOOLS:
            await self.ws.send_json({"type": "await_approval", "request_id": request_id})
            approved = await self._wait_approval(request_id)
            if self._should_abort():
                return
            if not approved:
                await self._stream_and_done("好的，已取消该操作。")
                return
        try:
            result = await asyncio.to_thread(execute_tool, self.session_id, tool, args)
        except ValueError as e:
            await self.ws.send_json({"type": "error", "detail": str(e)})
            return
        db.add_message(self.session_id, "tool", f"[{tool}] {result}")
        await self._stream_and_done(f"✅ 已完成：{result}")

    async def _plain_flow(self, user_text: str) -> None:
        client = settings_svc.build_llm_client()
        if not client.api_key:
            await self._stream_and_done(rule_reply(user_text))
            return

        history = build_history(self.session_id)
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def run() -> None:
            try:
                for ev in client.stream_chat(history, tools=TOOL_SCHEMAS):
                    loop.call_soon_threadsafe(queue.put_nowait, ev)
            except Exception as e:  # noqa: BLE001 - 线程内兜底
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "_llm_error", "detail": str(e)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        runner = asyncio.create_task(asyncio.to_thread(run))
        reply_parts: list[str] = []
        while True:
            ev = await queue.get()
            if ev is None:
                break
            if self._should_abort():
                return
            if ev["type"] == "delta":
                reply_parts.append(ev["text"])
                await self.ws.send_json({"type": "delta", "text": ev["text"]})
            elif ev["type"] == "tool_call":
                name = ev.get("name", "")
                try:
                    args = json.loads(ev.get("arguments") or "{}")
                except ValueError:
                    args = {}
                await self._tool_flow(user_text, name, args)
                return
            elif ev["type"] == "_llm_error":
                await self.ws.send_json({"type": "error", "detail": f"模型调用失败：{ev['detail']}"})
                return
        await runner
        reply = "".join(reply_parts).strip() or "（模型未返回内容）"
        if self._should_abort():
            return
        await self._finish_reply(reply)

    # ---------- 输出 ----------
    async def _stream_and_done(self, reply: str) -> None:
        for i in range(0, len(reply), STREAM_CHUNK):
            if self._should_abort():
                return
            await self.ws.send_json({"type": "delta", "text": reply[i : i + STREAM_CHUNK]})
            await asyncio.sleep(STREAM_INTERVAL)
        await self._finish_reply(reply)

    async def _finish_reply(self, reply: str) -> None:
        if self._should_abort():
            return
        message = db.add_message(self.session_id, "assistant", reply)
        tts_ev = synthesize(reply)
        await self.ws.send_json(tts_ev)
        await self.ws.send_json(
            {
                "type": "done",
                "message_id": message["id"],
                "reply": reply,
                "tts_engine": tts_ev.get("engine", "browser"),
            }
        )

    # ---------- 审批 ----------
    async def _wait_approval(self, request_id: str) -> bool:
        self._approval_evt = asyncio.Event()
        self._approval_request_id = request_id
        self._approval = None
        try:
            await asyncio.wait_for(self._approval_evt.wait(), timeout=APPROVAL_TIMEOUT)
        except asyncio.TimeoutError:
            return False
        return bool((self._approval or {}).get("approved"))

    async def _resolve_approval(self, msg: dict[str, Any]) -> None:
        if self._approval_evt is None or self._approval_request_id is None:
            return
        if msg.get("request_id") != self._approval_request_id:
            return
        self._approval = {"approved": bool(msg.get("approved"))}
        self._approval_evt.set()


@router.websocket("/chat")
async def chat_ws(ws: WebSocket) -> None:
    """实时语音对话 WebSocket（VAD 分段 + 增量 ASR + 流式回复 + TTS 帧）。"""
    handler = RealtimeHandler(ws)
    await handler.run()

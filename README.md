# VoicePilot 语音实时助手

浏览器录音 → 流式 ASR → LLM 流式回复 → 流式 TTS 的实时语音对话闭环，支持语音触发工具调用。

> 求职作品集项目（AI 应用开发工程师）· 需求文档见 [docs/需求开发文档.md](docs/需求开发文档.md)

## 核心能力（规划）

- 实时语音对话闭环：MediaRecorder 录音 → ASR → LLM → TTS 流式播放
- 多引擎适配层：ASR = 规则回声（演示）→ Web Speech / FunASR / 厂商 API；TTS = speechSynthesis / edge-tts / 厂商 API
- 语音 Agent：意图 → 工具注册表（日程/提醒/天气），敏感操作二次确认
- 实时工程：WebSocket 双向流、静音检测、打断（barge-in）、自动重试
- 无 Key 可演示：浏览器原生能力 + 规则降级，开箱即用

## 里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M1 | 骨架与语音管道：录音上传 → ASR 适配层 → 文本回显 | 进行中 |
| M2 | 对话引擎：LLM 流式 + 规则降级 + 工具调用 | 待开发 |
| M3 | 实时链路：WebSocket、静音检测、打断、TTS | 待开发 |
| M4 | 前端：波形、回听、设置页、暗色模式 | 待开发 |
| M5 | 演示与部署：Docker Compose、README、GHA | 待开发 |
| M6 | 质量门禁与代码审查 | 待开发 |

## 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev   # http://localhost:5173
```

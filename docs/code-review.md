# VoicePilot v1.0.0 代码审查报告

> 审查日期：2026-07-31 · 审查范围：backend/ + frontend/ 全部源码 · 结论：**无 P1 缺陷**，M6 修复 2 个 P2，P2/P3 详见 docs/known-issues.md
> 审查方式：逐文件通读 + 全量回归（pytest 49 用例 / ruff 0 告警 / vitest 9 文件 43 用例 / vite build）+ 手工冒烟（Docker Compose、Playwright 回放页）

## 一、结论摘要

| 维度 | 结论 |
|---|---|
| 架构 | 分层清晰（API → 服务适配层 → 存储），Provider 抽象（ASR/TTS/LLM）便于替换引擎，符合求职作品「工程化 AI 应用」定位 |
| 安全 | SQL 全参数化、上传扩展名白名单 + 大小限制、音频路径穿越防护、API Key 脱敏存储与回显、敏感工具二次确认 |
| 可靠性 | 断线指数退避重连、SSE 兜底错误帧、LLM 失败降级规则回复、TTS 异常降级浏览器、VAD 自动分段/打断 |
| 可维护性 | ruff 0 告警、组件化前端、测试覆盖核心链路（ASR/工具/回放/设置/录音降级） |
| 遗留问题 | 无 P1；P2 2 项（历史数据路径分隔符、回放缺少 LLM 耗时/token）；P3 11 项（详见 known-issues.md） |

## 二、M6 审查中修复的问题

| # | 问题 | 级别 | 修复 |
|---|---|---|---|
| FIX-1 | POST /api/settings/test 直接合并前端传入的 api_key：设置页把脱敏串原样回传，导致「测试模型连接」用掩码串当真实 Key，未配置时必失败 | P2 | services/settings.py::test_connection 增加掩码/空值守卫（与 _save 一致），并补测试 test_test_connection_ignores_masked_key |
| FIX-2 | GET /api/health 能力探测硬编码 {asr:True, llm:False, tts:False}，与 settings.get_capabilities() 实际结果矛盾，误导前端降级判断 | P2 | api/health.py 改用 settings_svc.get_capabilities()，语义与设置页一致 |

## 三、逐文件审查

### 后端入口与配置

| 文件 | 结论 |
|---|---|
| app/main.py | ✅ 简洁：lifespan 初始化目录与 DB；CORS 仅允许本地开发端口；路由按域拆分。注意：CORS 白名单只有 5173（开发用 Vite proxy 同源，直连 5174 会被拦，见 KN-12） |
| app/config.py | ✅ 环境变量可覆盖数据目录/引擎，上传限制与时长上限合理；版本号集中管理 |
| app/models.py | ✅ Pydantic 模型字段与响应一一对应；ErrorOut/ChatRequest 语义清楚 |
| app/utils/logging.py | ✅ loguru 单例 + 控制台格式化，测试可 monkeypatch |

### 后端 API 层

| 文件 | 结论 |
|---|---|
| app/api/health.py | ✅（M6 已修复 FIX-2）版本/引擎/能力探测齐全 |
| app/api/audio.py | ✅ 格式校验 → 存储 → 会话归属 → ASR → 落库链路完整；404/422/502 语义正确。注意：ASR 失败时已上传文件成为孤儿文件（KN-10）；文件回放固定 audio/wav 内容类型（KN-11） |
| app/api/chat.py | ✅ SSE 边界兜底（异常转 error 帧），会话不存在 404；save_user 机制避免语音转录重复落库 |
| app/api/sessions.py | ✅ 列表/详情/删除/回放/示例会话齐全；回放时间线 stage 归类清晰（asr/input/llm/tool + assistant 附带 tts 信息）；demo 音频幂等生成 |
| app/api/reminders.py | ✅ 简单 CRUD，limit 钳制 1~200 |
| app/api/realtime.py | ✅ 协议文档完整；VAD 分段 → 增量 ASR → LLM 流 → TTS 帧闭环；barge-in、审批超时（60s）、5MB 分段保护、连接清理齐全。边界：超长音频丢片后 VAD 可能不再触发 speech_end（KN-09）；LLM 流中 tool_call 分支未 await runner 任务（线程会自行结束，影响小，见 KN-13） |

### 后端服务层

| 文件 | 结论 |
|---|---|
| app/services/asr.py | ✅ Provider 抽象 + RuleEcho 演示兜底 + 未知引擎回退；wav 时长读取容错 |
| app/services/tts.py | ✅ 浏览器帧透传；edge 占位异常统一降级浏览器并附 note（KN-06） |
| app/services/chat.py | ✅ 工具二次确认闭环（tool_call → await_approval → 确认后执行）；规则意图检测与 LLM 工具调用共用执行器；LLM 异常降级规则回复 |
| app/services/tools.py | ✅ 工具注册表 schema 完整（提醒/时间/天气/搜索）；SENSITIVE_TOOLS 仅提醒需确认；规则正则覆盖常见中文表达 |
| app/services/settings.py | ✅（M6 已修复 FIX-1）默认值合并、白名单字段、掩码守卫、能力探测一致 |
| app/llm/client.py | ✅ OpenAI 兼容流式解析（delta/tool_call 分片累积）；错误归一化为 LLMError；test() 探活。注意：同步 httpx 阻塞调用，由 to_thread/线程池承载（KN-13） |

### 后端存储与音频

| 文件 | 结论 |
|---|---|
| app/storage/db.py | ✅ WAL + 外键 + 全参数化 SQL；消息级联删除；设置 JSON 读写容错；工具调用以 role=tool 落库（schema 已修正） |
| app/storage/files.py | ✅ uuid 存储名 + 扩展名白名单 + 大小限制 + 路径穿越防护（resolve 后校验父子关系） |
| app/audio/vad.py | ✅ RMS 能量检测，min_speech_ms 防瞬态误触发，speech_continue 每 250ms 节流，force_end 供手动停止 |
| app/audio/pcm.py | ✅ WAV 封装正确（16bit mono 小端），时长估算按字节 |

### 前端

| 文件 | 结论 |
|---|---|
| src/main.js + App.vue | ✅ 哈希路由 + Element Plus 中文 locale；主题持久化（localStorage）与暗色默认；品牌栏版本号展示 |
| src/api/http.js | ✅ fetch 统一封装：网络错误/非 JSON 错误体/中文提示 |
| src/api/chat.js | ✅ SSE 流解析（帧缓冲 + data 行提取 + 坏帧忽略），AbortSignal 支持 |
| src/api/audio.js / sessions.js / settings.js | ✅ 路径统一走 encodeURIComponent 分段编码；设置更新语义（空/掩码不修改） |
| src/utils/format.js | ✅ 时长/字节/时间格式化，NaN 防护 |
| src/composables/useRealtime.js | ✅ WebSocket 封装：指数退避重连、事件监听注册/注销、jsdom 降级 unsupported、断连状态机 |
| src/composables/useRecorder.js | ✅ MediaRecorder + ScriptProcessor PCM 重采样管线（16kHz 单声道 Int16Array）；状态机与清理完整（onBeforeUnmount 释放轨道）；ScriptProcessor 为废弃 API 但兼容性最佳（KN-14） |
| src/composables/useSpeech.js | ✅ speechSynthesis 封装，voice 匹配、打断、卸载清理 |
| src/components/RecorderButton.vue | ✅ 波形 Canvas + 脉冲动效 + 状态禁用 |
| src/components/MessageBubble.vue | ✅ 回听（audio 元素 + 播放态）、复制、重发；空 audioPath 不渲染按钮 |
| src/components/SessionSidebar.vue | ✅ 会话列表/新建/删除/示例入口 |
| src/views/ChatView.vue | ✅ 实时链路与 REST 兜底双模式；live ASR 提示、工具 chip、引导 dialog、兼容性检测；消息映射 snake→camel 统一 |
| src/views/SettingsView.vue | ✅ 脱敏回显（placeholder 展示掩码）、保存/测试分离、引擎切换 |
| src/views/ReplayView.vue | ✅ 五阶段徽标时间线、音频回听、TTS 引擎标签、加载/错误态 |
| src/assets/base.css | ✅ 暗色默认 + light 主题变量覆盖；Element Plus 变量微调；滚动条/背景美化 |

## 四、测试覆盖（M6 全量回归）

- 后端 pytest **49 个用例**全绿：健康检查/上传校验/ASR 回声/落库/设置脱敏与掩码守卫/工具调用/SSE/会话/回放 stage/示例会话/提醒
- 后端 ruff check **0 告警**
- 前端 vitest **9 文件 43 用例**全绿：ChatView 9 / ReplayView 4 / SettingsView 3 / MessageBubble 4 / SessionSidebar / useRealtime / useSpeech / api/chat / utils/format
- 前端 `npm run build` 成功（仅 chunk >500KB 警告，KN-05）
- Docker Compose 实测：nginx 反代 REST（health/demo/replay/audio）+ WebSocket ready 帧均通过
- Playwright 实测：示例会话加载、回放页 6 徽标/2 回听按钮、无 console error

## 五、审查建议（后续迭代方向）

1. 采集 LLM 耗时/token 落库并扩展回放（补齐需求 F8，见 KN-04）
2. 数据迁移：audio_path 统一正斜杠 + 旧数据兼容读取（KN-03）
3. 前端 code-split（路由懒加载）降低首屏体积（KN-05）
4. edge-tts 真实接入或从设置页移除占位（KN-06）

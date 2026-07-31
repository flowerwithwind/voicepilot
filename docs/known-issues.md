# VoicePilot 已知问题清单（Known Issues）

> 分级：**P1** 必须修复（阻断发布/功能不可用）｜ **P2** 建议近期修复（影响体验/数据一致性）｜ **P3** 可暂缓（边界场景/体验优化）
> 当前状态：v1.0.0 无 P1；P2 共 4 项（4 项已修复）；P3 共 11 项（6 项已修复，余 5 项）

## P2

### KN-01（已修复，M6）设置连接测试误用掩码 Key
- 现象：设置页「测试模型连接」把脱敏串（如 sk-t****abcd）原样提交，后端 test_connection 直接合并为 API Key，导致测试必失败。
- 修复：services/settings.py::test_connection 增加守卫——空值或等于当前掩码时视为不修改；补测试 test_test_connection_ignores_masked_key。
- 影响面：所有配置过 Key 的用户。

### KN-02（已修复，M6）health 能力探测与设置不一致
- 现象：GET /api/health 硬编码 capabilities={asr:True, llm:False, tts:False}，配置 Key 后仍报 llm 不可用。
- 修复：api/health.py 改调 settings_svc.get_capabilities()，与设置页口径一致。

### KN-03（已修复：C1）历史 audio_path 使用反斜杠分隔符
- 现象：M4 早期版本把实时音频路径存为 realtime\xxx.wav（Windows 风格）；M4 后期起统一存正斜杠 realtime/xxx.wav。
- 影响：Windows 本地可访问；Docker/Linux 容器中旧数据回听 404（Path 把反斜杠当文件名一部分）。
- 修复：读取侧归一化（app/utils/audio_path.py::normalize_audio_path，`\\` → `/`）覆盖文件回听（storage/files.py::safe_audio_path）、消息读取（storage/db.py::list_messages）与前端 URL 拼接（src/api/audio.js::audioUrl）；另提供一次性幂等迁移脚本 backend/scripts/migrate_audio_paths.py。

### KN-04（已修复：C2）回放未采集 LLM 耗时与 token
- 现象：需求 F8 写明「ASR 文本 / LLM 耗时 / token / 工具调用链」可观测，当前回放覆盖 ASR 文本、工具链、TTS 阶段，但 LLM 耗时/token 未落库。
- 影响：面试演示难以量化 LLM 性能指标。
- 修复：LLMClient 统一采集（app/llm/client.py 增加 stream_options.include_usage，流末记录 last_elapsed_ms / last_prompt_tokens / last_completion_tokens）；services/chat.py 与 api/realtime.py 在 LLM 流结束后随 assistant 消息落库；messages 表扩展 elapsed_ms / prompt_tokens / completion_tokens（init_db 幂等 ALTER 补列），回放 API 返回指标字段，回放页新增「LLM 3.2s · ↑120 ↓480」展示（无指标优雅隐藏）。

## P3

### KN-05 前端 bundle 体积 >500KB（1.08MB / gzip 357KB）
- 原因：Element Plus 全量引入。建议路由懒加载 + 按需引入组件/图标（unplugin-vue-components）。

### KN-06（已修复，C4）edge-tts 占位引擎已移除
- 现象：设置页可选「edge」引擎，但 EdgeTTSProvider.synthesize 抛错并降级浏览器 TTS（附 note 说明）。
- 决策：优先尝试接入真实 edge-tts，但真实合成依赖网络，且实时链路在 _finish_reply 同步调用 synthesize，引入后会导致自动化测试不稳定；故选干净移除——删除 EdgeTTSProvider 与设置页占位选项，仅保留浏览器引擎（默认），设置保存时把未知引擎（如旧数据中的 edge）归一化为 browser。

### KN-07 示例会话音频为生成的静音 WAV
- 现象：/api/sessions/demo 的回听音频是静音（演示回放链路用），不是真人录音。
- 建议：如需更真实效果，可内置一段示例人声 WAV。

### KN-08（已修复，C4）CI 未跑 Docker Compose 冒烟
- 现象：.github/workflows/ci.yml 只构建镜像，未启动 compose 验证 nginx 反代与 WebSocket。
- 修复：新增 compose job——docker compose up -d --build 后轮询后端 8010 与前端 5174（nginx 反代 /api）健康检查，结束时 down --volumes 清理；WS 握手由 nginx 的 upgrade 反代配置保障，冒烟仅校验 HTTP 健康。

### KN-09（已修复，C4）实时音频超 5MB 后 VAD 不再喂入
- 现象：单段音频超过 MAX_TURN_BYTES（5MB，约 160s 连续语音）后后续分片被丢弃，VAD 也收不到这些分片；若用户此时停止说话，静音检测无法触发 speech_end，回合悬挂（可手动 flush 恢复）。
- 修复：api/realtime.py::_on_audio 超限分支改为对当前语音段执行 vad.force_end() 并走正常 speech_end 流程，长语音自动结束回合，不再依赖后续静音分片。

### KN-10（已修复，C4）删除会话不清理磁盘音频文件
- 现象：DELETE /api/sessions/{id} 级联删 DB 记录，但 audio/ 下文件残留。
- 影响：本地 demo 影响小；长期运行磁盘增长。
- 修复：api/sessions.py::delete_session 先按消息 audio_path（经 safe_audio_path 防穿越解析）删除磁盘文件再删记录；demo/ 为多会话共享的演示音频，保留不删。

### KN-11（已修复，C4）/api/audio/files 固定返回 audio/wav
- 现象：webm/ogg/mp3 上传文件回放时 Content-Type 一律 audio/wav。
- 影响：多数播放器按字节嗅探可正常播放。
- 修复：api/audio.py 按扩展名映射 MIME（wav→audio/wav、webm→audio/webm、ogg→audio/ogg、mp3→audio/mpeg、m4a→audio/mp4）。

### KN-12（已修复，C4）CORS 白名单不含 5174
- 现象：main.py CORS 仅允许 localhost:5173/127.0.0.1:5173；开发时若 Vite 跑在 5174 且绕过 proxy 直连后端会被拦截（当前开发流程走 Vite proxy，不受影响）。
- 修复：main.py::cors_origins() 默认覆盖 5173~5179（localhost 与 127.0.0.1），并支持 VOICEPILOT_CORS_ORIGINS 环境变量覆盖。

### KN-13 LLM 同步阻塞调用
- 现象：httpx 同步客户端在服务线程池/to_thread 中执行，单用户 demo 无感知；高并发下会占满线程池。
- 建议：接入 async httpx 或限制并发。

### KN-14 ScriptProcessor 为废弃 Web API
- 现象：useRecorder 用 ScriptProcessorNode 做 PCM 重采样，功能正常但已被标准废弃。
- 建议：迁移 AudioWorklet（注意 AudioWorklet 需模块文件，SSR/测试环境降级逻辑需保留）。

### KN-15 回放页/示例数据无鉴权
- 现象：本地单用户工具，会话与音频接口无鉴权；部署到公网需加访问控制（与 KN-08 一并考虑）。

# VoicePilot 已知问题清单（Known Issues）

> 分级：**P1** 必须修复（阻断发布/功能不可用）｜ **P2** 建议近期修复（影响体验/数据一致性）｜ **P3** 可暂缓（边界场景/体验优化）
> 当前状态：v1.0.0 无 P1；P2 共 4 项（2 项已修复）；P3 共 11 项

## P2

### KN-01（已修复，M6）设置连接测试误用掩码 Key
- 现象：设置页「测试模型连接」把脱敏串（如 sk-t****abcd）原样提交，后端 test_connection 直接合并为 API Key，导致测试必失败。
- 修复：services/settings.py::test_connection 增加守卫——空值或等于当前掩码时视为不修改；补测试 test_test_connection_ignores_masked_key。
- 影响面：所有配置过 Key 的用户。

### KN-02（已修复，M6）health 能力探测与设置不一致
- 现象：GET /api/health 硬编码 capabilities={asr:True, llm:False, tts:False}，配置 Key 后仍报 llm 不可用。
- 修复：api/health.py 改调 settings_svc.get_capabilities()，与设置页口径一致。

### KN-03（待处理）历史 audio_path 使用反斜杠分隔符
- 现象：M4 早期版本把实时音频路径存为 realtime\xxx.wav（Windows 风格）；M4 后期起统一存正斜杠 realtime/xxx.wav。
- 影响：Windows 本地可访问；Docker/Linux 容器中旧数据回听 404（Path 把反斜杠当文件名一部分）。
- 建议：读取侧做归一化（audio_path.replace(/\\/g, '/')）或提供一次性数据迁移脚本。

### KN-04（待处理）回放未采集 LLM 耗时与 token
- 现象：需求 F8 写明「ASR 文本 / LLM 耗时 / token / 工具调用链」可观测，当前回放覆盖 ASR 文本、工具链、TTS 阶段，但 LLM 耗时/token 未落库。
- 影响：面试演示难以量化 LLM 性能指标。
- 建议：services/chat.py 与 realtime.py 在 LLM 流结束后记录 elapsed_ms + usage（DeepSeek 响应含 usage），存入 messages 扩展列或独立 metrics 表，回放页新增 LLM 阶段耗时展示。

## P3

### KN-05 前端 bundle 体积 >500KB（1.08MB / gzip 357KB）
- 原因：Element Plus 全量引入。建议路由懒加载 + 按需引入组件/图标（unplugin-vue-components）。

### KN-06 edge-tts 为占位引擎
- 现象：设置页可选「edge」引擎，但 EdgeTTSProvider.synthesize 抛错并降级浏览器 TTS（附 note 说明）。
- 建议：正式接入 edge-tts（Python 侧合成 base64 音频帧）或从设置页移除该选项。

### KN-07 示例会话音频为生成的静音 WAV
- 现象：/api/sessions/demo 的回听音频是静音（演示回放链路用），不是真人录音。
- 建议：如需更真实效果，可内置一段示例人声 WAV。

### KN-08 CI 未跑 Docker Compose 冒烟
- 现象：.github/workflows/ci.yml 只构建镜像，未启动 compose 验证 nginx 反代与 WebSocket。
- 建议：增加 compose up + curl health + ws ready 帧校验步骤。

### KN-09 实时音频超 5MB 后 VAD 不再喂入
- 现象：单段音频超过 MAX_TURN_BYTES（5MB，约 160s 连续语音）后后续分片被丢弃，VAD 也收不到这些分片；若用户此时停止说话，静音检测无法触发 speech_end，回合悬挂（可手动 flush 恢复）。
- 建议：丢弃分片时仍把分片喂给 VAD 或直接 force_end。

### KN-10 删除会话不清理磁盘音频文件
- 现象：DELETE /api/sessions/{id} 级联删 DB 记录，但 audio/ 下文件残留。
- 影响：本地 demo 影响小；长期运行磁盘增长。建议删除时按消息 audio_path 清理。

### KN-11 /api/audio/files 固定返回 audio/wav
- 现象：webm/ogg/mp3 上传文件回放时 Content-Type 一律 audio/wav。
- 影响：多数播放器按字节嗅探可正常播放；建议按扩展名映射 MIME。

### KN-12 CORS 白名单不含 5174
- 现象：main.py CORS 仅允许 localhost:5173/127.0.0.1:5173；开发时若 Vite 跑在 5174 且绕过 proxy 直连后端会被拦截（当前开发流程走 Vite proxy，不受影响）。
- 建议：允许来源改为配置项或覆盖 5173~5179。

### KN-13 LLM 同步阻塞调用
- 现象：httpx 同步客户端在服务线程池/to_thread 中执行，单用户 demo 无感知；高并发下会占满线程池。
- 建议：接入 async httpx 或限制并发。

### KN-14 ScriptProcessor 为废弃 Web API
- 现象：useRecorder 用 ScriptProcessorNode 做 PCM 重采样，功能正常但已被标准废弃。
- 建议：迁移 AudioWorklet（注意 AudioWorklet 需模块文件，SSR/测试环境降级逻辑需保留）。

### KN-15 回放页/示例数据无鉴权
- 现象：本地单用户工具，会话与音频接口无鉴权；部署到公网需加访问控制（与 KN-08 一并考虑）。

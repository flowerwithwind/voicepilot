<template>
  <div class="chat">
    <!-- 会话侧栏 -->
    <SessionSidebar
      :sessions="sessions"
      :active-id="activeSessionId"
      :loading="sessionsLoading"
      @select="selectSession"
      @create="createSession"
      @remove="removeSession"
    />

    <div class="chat-body">
      <!-- 会话头 -->
      <div class="chat-head">
        <div class="session-info">
          <span class="session-dot" />
          <span class="session-title">{{ currentTitle }}</span>
          <span class="engine-tag" :title="'引擎：' + engine">{{ engine }}</span>
        </div>
        <span v-if="rt.supported.value" class="rt-badge" :class="'rt-' + rt.status.value">
          <span class="rt-dot" />
          {{ rtLabel }}
        </span>
      </div>

      <!-- 不支持录音提示 -->
      <div v-if="!recorder.isSupported.value" class="warn-banner">
        <el-icon><WarningFilled /></el-icon>
        当前浏览器不支持录音（MediaRecorder），请使用 Chrome / Edge 最新版；文本输入可正常对话。
      </div>

      <!-- 消息区 -->
      <div ref="listEl" class="msg-list">
        <MessageBubble
          v-for="m in messages"
          :key="m.key"
          :role="m.role"
          :content="m.content"
          :engine="m.engine"
          :via-voice="!!m.viaVoice"
          :streaming="!!m.streaming"
          :audio-path="m.audioPath || ''"
          :duration-ms="m.durationMs || 0"
          @resend="resendMessage"
        />
        <div v-if="uploading" class="typing">
          <span class="dot" /><span class="dot" /><span class="dot" />
          正在识别语音…
        </div>
        <div v-if="waitingReply" class="typing">
          <span class="dot" /><span class="dot" /><span class="dot" />
          正在生成回复…
        </div>
        <div v-if="pendingTool" class="tool-chip">
          <el-icon :size="14"><MagicStick /></el-icon>
          <span>正在调用工具：{{ pendingTool.preview }}</span>
        </div>
      </div>

      <!-- 文本输入兜底 -->
      <div class="input-zone">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="1"
          resize="none"
          maxlength="500"
          placeholder="输入文字对话：如「明天9点提醒我开会」「北京天气怎么样」"
          @keydown.enter.exact.prevent="sendText"
        />
        <el-button
          type="primary"
          class="send-btn"
          :disabled="!canSend"
          @click="sendText"
        >
          发送
        </el-button>
      </div>

      <!-- 实时识别中 -->
      <div v-if="liveAsr" class="live-asr">
        <span class="live-dot" />
        <span class="live-text">{{ liveAsr }}</span>
      </div>

      <!-- 录音区 -->
      <div class="recorder-zone">
        <RecorderButton
          :state="recorder.state.value"
          :level="recorder.level.value"
          :duration="recorder.duration.value"
          :error="recorder.error.value"
          :disabled="uploading || !recorder.isSupported.value"
          @start="handleStart"
          @stop="handleStop"
        />
        <p class="tip">点击开始说话，松开/再点停止 · 音频实时上送（PCM→VAD→增量ASR→回复→语音播报），说话可随时打断</p>
      </div>
      <!-- 录音权限引导（首次访问） -->
      <el-dialog v-model="guideVisible" title="开始使用 VoicePilot" width="min(92vw, 460px)" :show-close="false">
        <div class="guide">
          <ol>
            <li><b>点击</b>下方麦克风按钮，浏览器会弹出麦克风权限请求</li>
            <li>选择<em>允许</em>后，<b>开始说话</b>，文字会实时上屏</li>
            <li>说完后点击麦克风<em>停止</em>，回复会自动语音播报；说话可随时打断</li>
          </ol>
          <div class="guide-compat">
            <span class="compat-item" :class="compatOk.recorder ? 'ok' : 'bad'">录音：{{ compatOk.recorder ? '支持' : '不支持' }}</span>
            <span class="compat-item" :class="compatOk.speech ? 'ok' : 'bad'">语音播报：{{ compatOk.speech ? '支持' : '不支持' }}</span>
            <span class="compat-item" :class="compatOk.websocket ? 'ok' : 'bad'">实时通道：{{ compatOk.websocket ? '支持' : '不支持' }}</span>
          </div>
          <p class="guide-tip">如未弹出权限提示，请点击地址栏右侧的麦克风图标手动授权。</p>
        </div>
        <template #footer>
          <el-button type="primary" @click="closeGuide">开始使用</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, WarningFilled } from '@element-plus/icons-vue'
import MessageBubble from '@/components/MessageBubble.vue'
import RecorderButton from '@/components/RecorderButton.vue'
import SessionSidebar from '@/components/SessionSidebar.vue'
import { useRecorder } from '@/composables/useRecorder'
import { useRealtime } from '@/composables/useRealtime'
import { useSpeech } from '@/composables/useSpeech'
import { transcribe } from '@/api/audio'
import { getSettings } from '@/api/settings'
import { streamChat } from '@/api/chat'
import {
  createSession as apiCreateSession,
  deleteSession as apiDeleteSession,
  listMessages,
  listSessions,
} from '@/api/sessions'

const recorder = useRecorder()
const rt = useRealtime()
const speech = useSpeech()
const sessions = ref([])
const sessionsLoading = ref(false)
const activeSessionId = ref(null)
const messages = ref([])
const inputText = ref('')
const engine = ref('rule')
const uploading = ref(false)
const streaming = ref(false)
const pendingTool = ref(null)
const liveAsr = ref('')
const listEl = ref(null)
const guideVisible = ref(false)
const GUIDE_KEY = 'voicepilot-guide-seen'
const compatOk = reactive({
  recorder: typeof MediaRecorder !== 'undefined' && !!navigator?.mediaDevices?.getUserMedia,
  speech: typeof speechSynthesis !== 'undefined' && typeof SpeechSynthesisUtterance !== 'undefined',
  websocket: typeof WebSocket !== 'undefined',
})
let ttsOptions = { rate: 1, pitch: 1, voiceName: '' }

let msgSeq = 0
let draft = null
let draftStarted = false
let realtimeMode = true // 当前录音使用实时链路（false = REST 录音识别兜底）

const canSend = computed(() => !streaming.value && !!inputText.value.trim())
const waitingReply = computed(() => streaming.value && !messages.value.some((m) => m.streaming))
const currentTitle = computed(() => {
  const s = sessions.value.find((x) => x.id === activeSessionId.value)
  return s ? s.title : '新会话'
})
const rtLabel = computed(() => {
  const s = rt.status.value
  if (s === 'connected') return '实时连接'
  if (s === 'connecting') return '连接中'
  if (s === 'reconnecting') return '重连中 (' + rt.retries.value + ')'
  if (s === 'unsupported') return '实时不可用'
  return '未连接'
})

const WELCOME =
  '你好，我是 VoicePilot 👋 可以试试对我说：\n' +
  '· 「明天9点提醒我开会」→ 创建提醒（需确认）\n' +
  '· 「北京天气怎么样」「现在几点了」→ 直接调用工具\n' +
  '· 「搜索一下 AI 应用开发」→ 演示搜索\n' +
  '点击下方麦克风开始说话，或直接用文字输入。'

function scrollBottom() {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

function ensureDraft() {
  if (!draftStarted) {
    draftStarted = true
    draft = reactive({
      key: 'a-' + msgSeq++,
      role: 'assistant',
      content: '',
      streaming: true,
      engine: engine.value,
    })
    messages.value.push(draft)
    scrollBottom()
  }
}

async function ensureSession() {
  if (activeSessionId.value != null) return activeSessionId.value
  try {
    const s = await apiCreateSession('新会话')
    sessions.value.unshift(s)
    activeSessionId.value = s.id
    draft = null
    draftStarted = false
    messages.value = [{ key: 'welcome-' + msgSeq++, role: 'assistant', content: WELCOME, engine: 'rule' }]
    scrollBottom()
    return s.id
  } catch (e) {
    ElMessage.error(e.message || '创建会话失败')
    return null
  }
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const data = await listSessions()
    sessions.value = data.items || []
  } catch (e) {
    ElMessage.error(e.message || '加载会话失败')
  } finally {
    sessionsLoading.value = false
  }
}

async function switchSession(id) {
  activeSessionId.value = id
  messages.value = []
  draft = null
  draftStarted = false
  scrollBottom()
  if (rt.supported.value) rt.connect(id)
  try {
    const rows = await listMessages(id)
    messages.value = rows
      .filter((r) => r.role === 'user' || r.role === 'assistant')
      .map((r) => ({
        key: 'h-' + r.id,
        id: r.id,
        role: r.role,
        content: r.content,
        engine: '',
        viaVoice: false,
        audioPath: r.audio_path || '',
        durationMs: r.duration_ms || 0,
      }))
  } catch (e) {
    ElMessage.error(e.message || '加载消息失败')
  }
  scrollBottom()
}

async function selectSession(id) {
  if (streaming.value) {
    ElMessage.warning('回复生成中，请稍候再切换')
    return
  }
  if (id === activeSessionId.value) return
  await switchSession(id)
}

async function createSession() {
  if (streaming.value) {
    ElMessage.warning('回复生成中，请稍候再新建')
    return
  }
  try {
    const s = await apiCreateSession('新会话')
    sessions.value.unshift(s)
    activeSessionId.value = s.id
    draft = null
    draftStarted = false
    messages.value = [{ key: 'welcome-' + msgSeq++, role: 'assistant', content: WELCOME, engine: 'rule' }]
    if (rt.supported.value) rt.connect(s.id)
    scrollBottom()
  } catch (e) {
    ElMessage.error(e.message || '新建会话失败')
  }
}

async function removeSession(id) {
  try {
    await ElMessageBox.confirm('删除后该会话的历史消息将不可恢复，确定删除？', '删除会话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiDeleteSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (activeSessionId.value === id) {
      activeSessionId.value = null
      messages.value = []
      if (sessions.value.length) {
        await switchSession(sessions.value[0].id)
      } else {
        await createSession()
      }
    }
    ElMessage.success('会话已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function askApproval(info) {
  return ElMessageBox.confirm('将执行：' + info.preview + '\n是否继续？', '工具调用确认', {
    type: 'warning',
    confirmButtonText: '确认执行',
    cancelButtonText: '取消',
  })
    .then(() => true)
    .catch(() => false)
}

async function runChat(text, approval, opts = {}) {
  if (streaming.value) return
  const sid = await ensureSession()
  if (sid == null) return
  streaming.value = true
  pendingTool.value = null
  draft = null
  draftStarted = false

  try {
    const events = streamChat({
      sessionId: sid,
      content: text,
      approval: approval || null,
      saveUser: opts.saveUser !== false,
    })
    for await (const ev of events) {
      if (ev.type === 'delta') {
        pendingTool.value = null
        ensureDraft()
        draft.content += ev.text
        scrollBottom()
      } else if (ev.type === 'tool_call') {
        pendingTool.value = {
          requestId: ev.request_id,
          tool: ev.tool,
          args: ev.args,
          preview: ev.preview,
        }
      } else if (ev.type === 'await_approval') {
        const info = pendingTool.value || { preview: '执行工具' }
        pendingTool.value = null
        streaming.value = false
        const ok = await askApproval(info)
        if (draftStarted) {
          messages.value = messages.value.filter((m) => m !== draft)
          draftStarted = false
          draft = null
        }
        await runChat(text, { request_id: ev.request_id, approved: ok }, { saveUser: false })
        return
      } else if (ev.type === 'done') {
        ensureDraft()
        draft.streaming = false
        if (ev.message_id) draft.id = ev.message_id
        await loadSessions()
      } else if (ev.type === 'error') {
        ensureDraft()
        draft.streaming = false
        ElMessage.error(ev.detail || '对话出错')
      }
    }
    if (draft) draft.streaming = false
  } catch (e) {
    if (draftStarted && draft) {
      draft.streaming = false
      draft.content += '\n（请求中断：' + (e.message || '网络异常') + '）'
    }
    ElMessage.error(e.message || '对话失败')
  } finally {
    if (draft) draft.streaming = false
    streaming.value = false
    pendingTool.value = null
    scrollBottom()
  }
}

async function sendText() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return
  inputText.value = ''
  messages.value.push({ key: 'u-' + msgSeq++, role: 'user', content: text, viaVoice: false })
  scrollBottom()
  await runChat(text, null, { saveUser: true })
}

/** 等待实时通道就绪（最多 2s），失败时回退普通录音。 */
async function ensureRealtimeConnected() {
  if (rt.status.value === 'connected') return true
  if (!rt.supported.value) return false
  const sid = await ensureSession()
  if (sid == null) return false
  rt.connect(sid)
  for (let i = 0; i < 20; i += 1) {
    if (rt.status.value === 'connected') return true
    if (rt.status.value === 'unsupported') return false
    await new Promise((r) => setTimeout(r, 100))
  }
  return rt.status.value === 'connected'
}

async function resendMessage(text) {
  if (!text || streaming.value) return
  messages.value.push({ key: 'u-' + msgSeq++, role: 'user', content: text, viaVoice: false })
  scrollBottom()
  if (rt.supported.value && rt.status.value === 'connected') {
    rt.sendUtterance(text)
  } else {
    await runChat(text, null, { saveUser: true })
  }
}

async function handleStart() {
  if (rt.supported.value) {
    realtimeMode = await ensureRealtimeConnected()
    if (!realtimeMode) {
      ElMessage.warning('实时通道不可用，已切换为普通录音识别')
    }
  } else {
    realtimeMode = false
  }
  await recorder.start(
    realtimeMode ? { onPcm: (chunk) => rt.sendAudio(chunk) } : {},
  )
  if (recorder.state.value === 'error') {
    ElMessage.error(recorder.error.value || '无法开始录音')
  }
}

async function handleStop() {
  if (realtimeMode) {
    await recorder.stop()
    rt.sendFlush() // 强制结束语音段，立即进入识别
    return
  }
  const blob = await recorder.stop()
  if (!blob) return
  uploading.value = true
  try {
    const result = await transcribe(blob, {
      sessionId: activeSessionId.value,
      duration: recorder.duration.value,
    })
    if (activeSessionId.value == null) {
      activeSessionId.value = result.session_id
    }
    if (!sessions.value.some((s) => s.id === result.session_id)) {
      sessions.value.unshift({
        id: result.session_id,
        title: '语音会话',
        message_count: 1,
        updated_at: new Date().toISOString(),
      })
    }
    engine.value = result.engine
    messages.value.push({
      key: 'u-' + msgSeq++,
      role: 'user',
      content: result.text,
      viaVoice: true,
      engine: result.engine,
      audioPath: result.audio_path || '',
      durationMs: result.duration ? Math.round(result.duration * 1000) : 0,
    })
    scrollBottom()
    await runChat(result.text, null, { saveUser: false })
  } catch (e) {
    ElMessage.error(e.message || '语音识别失败')
  } finally {
    uploading.value = false
  }
}

/** 订阅 WebSocket 实时事件，驱动 UI（一次注册，随连接生命周期复用）。 */
function wireRealtime() {
  rt.on('ready', (ev) => {
    const sid = ev.session_id
    if (sid == null) return
    if (!sessions.value.some((s) => s.id === sid)) {
      sessions.value.unshift({
        id: sid,
        title: '实时语音会话',
        message_count: 0,
        updated_at: new Date().toISOString(),
      })
    }
    if (activeSessionId.value == null || activeSessionId.value !== sid) {
      activeSessionId.value = sid
      draft = null
      draftStarted = false
      messages.value = messages.value.filter((m) => m.key && m.key.indexOf('welcome-') === 0)
      scrollBottom()
    }
    loadSessions()
  })
  rt.on('vad', (ev) => {
    if (ev.event === 'speech_start' && speech.speaking.value) {
      speech.cancel() // 客户端先行停掉 TTS，服务端随后确认 interrupt
    }
  })
  rt.on('asr.partial', (ev) => {
    liveAsr.value = ev.text || ''
  })
  rt.on('asr.final', (ev) => {
    liveAsr.value = ''
    engine.value = ev.engine || engine.value
    messages.value.push({
      key: 'u-' + msgSeq++,
      role: 'user',
      content: ev.text,
      viaVoice: true,
      engine: ev.engine,
      audioPath: ev.audio_path || '',
      durationMs: ev.duration ? Math.round(ev.duration * 1000) : 0,
    })
    streaming.value = true
    scrollBottom()
    loadSessions()
  })
  rt.on('delta', (ev) => {
    pendingTool.value = null
    ensureDraft()
    draft.content += ev.text
    scrollBottom()
  })
  rt.on('tool_call', (ev) => {
    pendingTool.value = {
      requestId: ev.request_id,
      tool: ev.tool,
      args: ev.args,
      preview: ev.preview,
    }
  })
  rt.on('await_approval', (ev) => {
    const info = pendingTool.value || { preview: '执行工具' }
    askApproval(info).then((ok) => rt.sendApproval(ev.request_id, ok))
  })
  rt.on('tts', (ev) => {
    if (ev && ev.engine === 'browser' && ev.text) speech.speak(ev.text, ttsOptions)
  })
  rt.on('done', (ev) => {
    ensureDraft()
    if (draft) {
      draft.streaming = false
      if (ev.message_id) draft.id = ev.message_id
    }
    streaming.value = false
    pendingTool.value = null
    loadSessions()
    scrollBottom()
  })
  rt.on('interrupt', () => {
    speech.cancel()
    liveAsr.value = ''
    pendingTool.value = null
    streaming.value = false
    if (draftStarted && draft) draft.streaming = false
    draft = null
    draftStarted = false
    scrollBottom()
  })
  rt.on('error', (ev) => {
    speech.cancel()
    liveAsr.value = ''
    pendingTool.value = null
    streaming.value = false
    if (draftStarted && draft) draft.streaming = false
    ElMessage.error(ev.detail || '实时对话出错')
    scrollBottom()
  })
}

function closeGuide() {
  guideVisible.value = false
  try {
    localStorage.setItem(GUIDE_KEY, '1')
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  wireRealtime()
  try {
    const st = await getSettings()
    if (st && st.tts) {
      ttsOptions = {
        rate: Number(st.tts.rate) || 1,
        pitch: Number(st.tts.pitch) || 1,
        voiceName: st.tts.voice || '',
      }
    }
  } catch {
    /* 设置加载失败不影响主流程 */
  }
  let seen = false
  try {
    seen = localStorage.getItem(GUIDE_KEY) === '1'
  } catch {
    /* ignore */
  }
  guideVisible.value = !seen && recorder.isSupported.value
  await loadSessions()
  if (sessions.value.length) {
    await switchSession(sessions.value[0].id)
  } else {
    await createSession()
  }
})
</script>

<style scoped>
.chat {
  display: flex;
  height: 100%;
  min-height: 0;
  width: 100%;
}
.chat-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  max-width: 920px;
  margin: 0 auto;
  padding: 0 28px;
}
.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.session-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #e6e9f5;
}
.session-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 8px rgba(52, 211, 153, 0.8);
}
.engine-tag {
  font-size: 11px;
  font-weight: 500;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.16);
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 999px;
  padding: 2px 10px;
}
.rt-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #6ee7b7;
  background: rgba(52, 211, 153, 0.12);
  border: 1px solid rgba(52, 211, 153, 0.35);
  border-radius: 999px;
  padding: 3px 10px;
}
.rt-badge .rt-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #34d399;
  animation: rtBlink 1.6s infinite;
}
.rt-badge.rt-connecting,
.rt-badge.rt-reconnecting {
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.35);
}
.rt-badge.rt-connecting .rt-dot,
.rt-badge.rt-reconnecting .rt-dot {
  background: #f59e0b;
}
.rt-badge.rt-unsupported,
.rt-badge.rt-idle {
  color: rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.15);
}
.rt-badge.rt-unsupported .rt-dot,
.rt-badge.rt-idle .rt-dot {
  background: rgba(255, 255, 255, 0.4);
  animation: none;
}
@keyframes rtBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.warn-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fcd34d;
  font-size: 13px;
}
.msg-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 6px;
  scroll-behavior: smooth;
}
.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  padding: 10px 2px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #a5b4fc;
  animation: blink 1.2s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 1; }
}
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 10px 0;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  color: #c7d2fe;
  background: rgba(99, 102, 241, 0.14);
  border: 1px solid rgba(99, 102, 241, 0.3);
}
.input-zone {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 0 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}
.input-zone :deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  color: #e6e9f5;
}
.send-btn {
  flex-shrink: 0;
  border-radius: 10px;
}
.live-asr {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 12px;
  background: rgba(34, 211, 238, 0.08);
  border: 1px solid rgba(34, 211, 238, 0.25);
  color: #a5f3fc;
  font-size: 13px;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22d3ee;
  flex-shrink: 0;
  animation: rtBlink 1s infinite;
}
.live-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recorder-zone {
  padding: 14px 0 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  text-align: center;
}
.tip {
  margin: 8px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}
@media (max-width: 768px) {
  .chat-body {
    padding: 0 14px;
  }
}

.guide ol {
  margin: 0 0 14px;
  padding-left: 20px;
  line-height: 2;
  font-size: 14px;
  color: #c4c9e0;
}
.guide em {
  color: #22d3ee;
  font-style: normal;
}
.guide-compat {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.compat-item {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.5);
}
.compat-item.ok {
  color: #6ee7b7;
  border-color: rgba(52, 211, 153, 0.4);
}
.compat-item.bad {
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.4);
}
.guide-tip {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
</style>

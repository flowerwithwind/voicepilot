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

      <!-- 录音区 -->
      <div class="recorder-zone">
        <RecorderButton
          :state="recorder.state.value"
          :level="recorder.level.value"
          :duration="recorder.duration.value"
          :error="recorder.error.value"
          :disabled="uploading || streaming || !recorder.isSupported.value"
          @start="handleStart"
          @stop="handleStop"
        />
        <p class="tip">点击开始说话，松开/再点停止 · 语音将实时转写并触发智能回复</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, WarningFilled } from '@element-plus/icons-vue'
import MessageBubble from '@/components/MessageBubble.vue'
import RecorderButton from '@/components/RecorderButton.vue'
import SessionSidebar from '@/components/SessionSidebar.vue'
import { useRecorder } from '@/composables/useRecorder'
import { transcribe } from '@/api/audio'
import { streamChat } from '@/api/chat'
import {
  createSession as apiCreateSession,
  deleteSession as apiDeleteSession,
  listMessages,
  listSessions,
} from '@/api/sessions'

const recorder = useRecorder()
const sessions = ref([])
const sessionsLoading = ref(false)
const activeSessionId = ref(null)
const messages = ref([])
const inputText = ref('')
const engine = ref('rule')
const uploading = ref(false)
const streaming = ref(false)
const pendingTool = ref(null)
const listEl = ref(null)

let msgSeq = 0
let draft = null
let draftStarted = false

const canSend = computed(() => !streaming.value && !!inputText.value.trim())
const waitingReply = computed(() => streaming.value && !messages.value.some((m) => m.streaming))
const currentTitle = computed(() => {
  const s = sessions.value.find((x) => x.id === activeSessionId.value)
  return s ? s.title : '新会话'
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
  if (activeSessionId.value == null) {
    try {
      const s = await apiCreateSession('新会话')
      activeSessionId.value = s.id
      sessions.value.unshift(s)
    } catch (e) {
      ElMessage.error(e.message || '创建会话失败')
      return
    }
  }
  streaming.value = true
  pendingTool.value = null
  draft = null
  draftStarted = false

  const ensureDraft = () => {
    if (!draftStarted) {
      draftStarted = true
      draft = { key: 'a-' + msgSeq++, role: 'assistant', content: '', streaming: true, engine: engine.value }
      messages.value.push(draft)
      scrollBottom()
    }
  }

  try {
    const events = streamChat({
      sessionId: activeSessionId.value,
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

async function handleStart() {
  await recorder.start()
  if (recorder.state.value === 'error') {
    ElMessage.error(recorder.error.value || '无法开始录音')
  }
}

async function handleStop() {
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
    })
    scrollBottom()
    await runChat(result.text, null, { saveUser: false })
  } catch (e) {
    ElMessage.error(e.message || '语音识别失败')
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
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
</style>

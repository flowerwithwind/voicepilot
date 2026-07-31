<template>
  <div class="chat">
    <!-- 会话栏 -->
    <div class="chat-head">
      <div class="session-info">
        <span class="session-dot" />
        <span class="session-title">{{ sessionId ? '语音会话 #' + sessionId : '新会话' }}</span>
        <span class="engine-tag" :title="'ASR 引擎：' + engine">{{ engine }}</span>
      </div>
      <el-button size="small" text bg class="new-btn" @click="newSession">
        <el-icon><Plus /></el-icon>&nbsp;新会话
      </el-button>
    </div>

    <!-- 不支持提示 -->
    <div v-if="!recorder.isSupported.value" class="warn-banner">
      <el-icon><WarningFilled /></el-icon>
      当前浏览器不支持录音（MediaRecorder），请使用 Chrome / Edge 最新版；文本输入将在 M2 提供。
    </div>

    <!-- 消息区 -->
    <div ref="listEl" class="msg-list">
      <MessageBubble
        v-for="m in messages"
        :key="m.id"
        :role="m.role"
        :content="m.content"
        :engine="m.engine"
      />
      <div v-if="uploading" class="typing">
        <span class="dot" /><span class="dot" /><span class="dot" />
        正在识别语音…
      </div>
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
      <p class="tip">点击开始说话，松开/再点停止 · 录音将实时转写为文本</p>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, WarningFilled } from '@element-plus/icons-vue'
import RecorderButton from '@/components/RecorderButton.vue'
import MessageBubble from '@/components/MessageBubble.vue'
import { useRecorder } from '@/composables/useRecorder'
import { transcribe } from '@/api/audio'

const recorder = useRecorder()
const messages = ref([])
const sessionId = ref(null)
const engine = ref('rule')
const uploading = ref(false)
const listEl = ref(null)

let msgSeq = 0

const WELCOME = {
  id: 'welcome',
  role: 'assistant',
  content:
    '你好，我是 VoicePilot 👋 点击下方麦克风开始说话，我会把语音实时转成文字。\\n当前为演示模式（规则回声引擎），配置 ASR/LLM 后即可获得真实转写与智能回复。',
}

function scrollBottom() {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

function newSession() {
  sessionId.value = null
  engine.value = 'rule'
  messages.value = [{ ...WELCOME, id: 'welcome-' + msgSeq++ }]
  scrollBottom()
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
      sessionId: sessionId.value,
      duration: recorder.duration.value,
    })
    sessionId.value = result.session_id
    engine.value = result.engine
    messages.value.push({
      id: 'msg-' + msgSeq++,
      role: 'user',
      content: result.text,
      engine: result.engine,
    })
    scrollBottom()
  } catch (e) {
    ElMessage.error(e.message || '语音识别失败')
  } finally {
    uploading.value = false
  }
}

onMounted(newSession)
</script>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
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
.new-btn {
  color: #c7d2fe !important;
  background: rgba(99, 102, 241, 0.12) !important;
  border: none !important;
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
</style>

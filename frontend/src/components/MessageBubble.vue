<template>
  <div class="bubble-row" :class="roleClass">
    <div v-if="role === 'assistant'" class="avatar">VP</div>
    <div class="bubble" :class="roleClass">
      <div v-if="role === 'user'" class="voice-tag">
        <el-icon :size="12"><Microphone v-if="viaVoice" /><EditPen v-else /></el-icon>
        {{ viaVoice ? '语音' : '文本' }}
        <template v-if="durationText">· {{ durationText }}</template>
      </div>
      <p class="content">{{ content }}<span v-if="streaming" class="cursor" /></p>
      <div class="actions">
        <span v-if="engine" class="meta">· {{ engine }}</span>
        <button v-if="audioUrl" class="act-btn" :class="{ playing }" :title="playing ? '停止播放' : '回听语音'" @click="togglePlay">
          <el-icon :size="13"><VideoPlay v-if="!playing" /><VideoPause v-else /></el-icon>
          {{ playing ? '停止' : '回听' }}
        </button>
        <button class="act-btn" title="复制文本" @click="copy">
          <el-icon :size="13"><CopyDocument /></el-icon>
          复制
        </button>
        <button v-if="role === 'user'" class="act-btn" title="重新发送" @click="$emit('resend', content)">
          <el-icon :size="13"><RefreshRight /></el-icon>
          重发
        </button>
      </div>
    </div>
    <audio ref="audioEl" :src="audioUrl" @ended="playing = false" @error="playing = false" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CopyDocument,
  EditPen,
  Microphone,
  RefreshRight,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import { audioUrl as makeAudioUrl } from '@/api/audio'
import { formatDuration } from '@/utils/format'

const props = defineProps({
  role: { type: String, default: 'user' }, // user | assistant
  content: { type: String, default: '' },
  engine: { type: String, default: '' },
  viaVoice: { type: Boolean, default: false },
  streaming: { type: Boolean, default: false },
  audioPath: { type: String, default: '' },
  durationMs: { type: Number, default: 0 },
})
defineEmits(['resend'])

const roleClass = computed(() => (props.role === 'assistant' ? 'assistant' : 'user'))
const audioUrl = computed(() => makeAudioUrl(props.audioPath))
const durationText = computed(() => (props.durationMs > 0 ? formatDuration(props.durationMs / 1000) : ''))
const audioEl = ref(null)
const playing = ref(false)

async function togglePlay() {
  const el = audioEl.value
  if (!el) return
  if (playing.value) {
    el.pause()
    playing.value = false
    return
  }
  try {
    await el.play()
    playing.value = true
  } catch {
    ElMessage.warning('音频播放失败')
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(props.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本')
  }
}
</script>

<style scoped>
.bubble-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  margin: 14px 0;
}
.bubble-row.user {
  justify-content: flex-end;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.bubble {
  max-width: 76%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}
.bubble.assistant {
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e6e9f5;
  border-bottom-left-radius: 6px;
}
.bubble.user {
  background: linear-gradient(135deg, #6366f1, #7c6cf0);
  color: #fff;
  border-bottom-right-radius: 6px;
}
html.light .bubble.assistant {
  background: #ffffff;
  border-color: rgba(28, 34, 55, 0.1);
  color: #1c2237;
}
.voice-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  opacity: 0.85;
  margin-bottom: 4px;
}
.content {
  margin: 0;
  white-space: pre-wrap;
}
.cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  margin-left: 2px;
  vertical-align: -2px;
  background: #a5b4fc;
  animation: blink 1s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.1; }
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.meta {
  font-size: 11px;
  opacity: 0.6;
  margin-right: auto;
}
.act-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
  color: inherit;
  font-size: 11px;
  cursor: pointer;
  opacity: 0.85;
  transition: opacity 0.15s ease;
}
.act-btn:hover {
  opacity: 1;
}
.act-btn.playing {
  background: rgba(34, 211, 238, 0.22);
  border-color: rgba(34, 211, 238, 0.5);
}
</style>

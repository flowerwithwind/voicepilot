<template>
  <div class="replay">
    <div class="replay-head">
      <a href="#/" class="back-btn">← 返回对话</a>
      <div class="head-main">
        <h2 class="page-title">{{ session.title || '会话回放' }}</h2>
        <p class="page-sub">{{ timeline.length }} 条记录 · 创建于 {{ formatDateTime(session.created_at) }}</p>
      </div>
      <div class="legend">
        <span v-for="meta in legend" :key="meta.stage" class="legend-item">
          <i class="legend-dot" :class="'dot-' + meta.stage" />{{ meta.label }}
        </span>
      </div>
    </div>

    <div v-if="loading" class="replay-empty">正在加载时间线…</div>
    <div v-else-if="error" class="replay-empty error">{{ error }}</div>
    <div v-else-if="!timeline.length" class="replay-empty">该会话暂无消息，先回去说一句吧。</div>
    <div v-else class="timeline">
      <div v-for="(item, idx) in timeline" :key="item.id" class="tl-item">
        <div class="tl-rail">
          <span class="tl-dot" :class="'dot-' + item.stage" />
          <span v-if="idx < timeline.length - 1" class="tl-line" />
        </div>
        <div class="tl-card">
          <div class="tl-head">
            <span class="stage-badge" :class="'badge-' + item.stage">
              <el-icon :size="12"><component :is="stageMeta[item.stage].icon" /></el-icon>
              {{ stageMeta[item.stage].label }}
            </span>
            <span class="tl-role">{{ roleLabel(item.role) }}</span>
            <span class="tl-time">{{ formatClock(item.created_at) }}</span>
            <span v-if="item.durationMs" class="tl-duration">音频 {{ formatDuration(item.durationMs / 1000) }}</span>
          </div>
          <p class="tl-text">{{ item.text }}</p>
          <div class="tl-actions">
            <button
              v-if="item.audioPath"
              class="act-btn"
              :class="{ playing: playingId === item.id }"
              :title="playingId === item.id ? '停止播放' : '回听语音'"
              @click="togglePlay(item)"
            >
              <el-icon :size="13"><VideoPause v-if="playingId === item.id" /><VideoPlay v-else /></el-icon>
              {{ playingId === item.id ? '停止' : '回听' }}
            </button>
            <span v-if="item.tts" class="tts-tag">
              <el-icon :size="12"><Headset /></el-icon>
              TTS 播报 · {{ item.tts.engine }}
            </span>
          </div>
        </div>
      </div>
    </div>
    <audio ref="audioEl" @ended="playingId = null" @error="playingId = null" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatLineRound,
  EditPen,
  Headset,
  Microphone,
  Tools,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import { audioUrl as makeAudioUrl } from '@/api/audio'
import { fetchReplay } from '@/api/sessions'
import { formatClock, formatDateTime, formatDuration } from '@/utils/format'

const route = useRoute()
const sessionId = ref(route.params.sessionId)
const session = ref({})
const timeline = ref([])
const loading = ref(true)
const error = ref('')
const audioEl = ref(null)
const playingId = ref(null)

const stageMeta = {
  asr: { label: 'ASR 语音识别', icon: Microphone },
  input: { label: '文本输入', icon: EditPen },
  llm: { label: 'LLM 回复', icon: ChatLineRound },
  tool: { label: '工具调用', icon: Tools },
  tts: { label: 'TTS 播报', icon: Headset },
}
const legend = computed(() => Object.keys(stageMeta).map((stage) => ({ stage, label: stageMeta[stage].label })))

function roleLabel(role) {
  if (role === 'user') return '用户'
  if (role === 'tool') return '系统'
  return '助手'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchReplay(sessionId.value)
    session.value = data.session || {}
    // 后端返回 snake_case 字段，统一为组件内驼峰命名
    timeline.value = (data.timeline || []).map((t) => ({
      ...t,
      audioPath: t.audio_path || '',
      durationMs: t.duration_ms || 0,
    }))
  } catch (e) {
    error.value = e.message || '加载回放失败'
  } finally {
    loading.value = false
  }
}

async function togglePlay(item) {
  const el = audioEl.value
  if (!el) return
  if (playingId.value === item.id) {
    el.pause()
    el.currentTime = 0
    playingId.value = null
    return
  }
  el.src = makeAudioUrl(item.audioPath)
  try {
    await el.play()
    playingId.value = item.id
  } catch {
    ElMessage.warning('音频播放失败')
  }
}

watch(
  () => route.params.sessionId,
  (v) => {
    sessionId.value = v
    playingId.value = null
    load()
  },
)

onMounted(load)
</script>

<style scoped>
.replay {
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 28px 48px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.replay-head {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.back-btn {
  flex-shrink: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  transition: all 0.15s ease;
}
.back-btn:hover {
  color: #e6e9f5;
  background: rgba(255, 255, 255, 0.08);
}
.head-main {
  flex: 1;
  min-width: 0;
}
.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  color: #e6e9f5;
}
.page-sub {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
.legend {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.timeline {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 6px 0;
}
.tl-item {
  display: flex;
  gap: 14px;
}
.tl-rail {
  width: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.tl-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 16px;
  box-shadow: 0 0 10px currentColor;
}
.tl-line {
  flex: 1;
  width: 2px;
  background: rgba(255, 255, 255, 0.1);
  margin: 4px 0;
}
.tl-card {
  flex: 1;
  min-width: 0;
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.tl-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.stage-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
}
.badge-asr { color: #a5f3fc; background: rgba(34, 211, 238, 0.14); border: 1px solid rgba(34, 211, 238, 0.4); }
.badge-input { color: #bfdbfe; background: rgba(96, 165, 250, 0.14); border: 1px solid rgba(96, 165, 250, 0.4); }
.badge-llm { color: #c7d2fe; background: rgba(129, 140, 248, 0.16); border: 1px solid rgba(129, 140, 248, 0.4); }
.badge-tool { color: #fde68a; background: rgba(251, 191, 36, 0.13); border: 1px solid rgba(251, 191, 36, 0.4); }
.badge-tts { color: #e9d5ff; background: rgba(192, 132, 252, 0.14); border: 1px solid rgba(192, 132, 252, 0.4); }
.dot-asr { color: #22d3ee; background: #22d3ee; }
.dot-input { color: #60a5fa; background: #60a5fa; }
.dot-llm { color: #818cf8; background: #818cf8; }
.dot-tool { color: #fbbf24; background: #fbbf24; }
.dot-tts { color: #c084fc; background: #c084fc; }
.tl-role {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}
.tl-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}
.tl-duration {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}
.tl-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #e6e9f5;
  white-space: pre-wrap;
  word-break: break-word;
}
.tl-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.act-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
  font-size: 11px;
  cursor: pointer;
}
.act-btn:hover { background: rgba(255, 255, 255, 0.14); }
.act-btn.playing {
  background: rgba(34, 211, 238, 0.22);
  border-color: rgba(34, 211, 238, 0.5);
  color: #a5f3fc;
}
.tts-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #d8b4fe;
}
.replay-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
}
.replay-empty.error {
  color: #fca5a5;
}
html.light .page-title { color: #1c2237; }
html.light .page-sub { color: rgba(28, 34, 55, 0.55); }
html.light .back-btn { color: rgba(28, 34, 55, 0.7); border-color: rgba(28, 34, 55, 0.2); }
html.light .back-btn:hover { background: rgba(28, 34, 55, 0.06); }
html.light .tl-card { background: #ffffff; border-color: rgba(28, 34, 55, 0.1); }
html.light .tl-text { color: #1c2237; }
html.light .tl-role, html.light .tl-time, html.light .tl-duration { color: rgba(28, 34, 55, 0.5); }
html.light .act-btn { color: #1c2237; border-color: rgba(28, 34, 55, 0.2); background: rgba(28, 34, 55, 0.05); }
html.light .legend-item { color: rgba(28, 34, 55, 0.6); }
@media (max-width: 768px) {
  .replay { padding: 16px 14px 32px; }
  .legend { display: none; }
}
</style>

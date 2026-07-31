<template>
  <div class="recorder" :class="state">
    <!-- 实时波形（Canvas，录音中动画） -->
    <div class="wave-wrap" :class="{ hidden: state !== 'recording' }">
      <canvas ref="canvasEl" width="240" height="56" class="wave-canvas" />
    </div>

    <!-- 主按钮 -->
    <button
      class="mic-btn"
      :class="{ recording: state === 'recording', stopping: state === 'stopping' }"
      :disabled="state === 'stopping' || disabled"
      @click="onClick"
    >
      <el-icon :size="34"><Microphone /></el-icon>
    </button>

    <div class="recorder-hint">
      <template v-if="state === 'idle'">点击开始说话</template>
      <template v-else-if="state === 'recording'">正在聆听 · {{ durationText }}</template>
      <template v-else-if="state === 'stopping'">正在识别…</template>
      <template v-else>{{ error || '录音失败' }}</template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Microphone } from '@element-plus/icons-vue'
import { formatDuration } from '@/utils/format'

const props = defineProps({
  state: { type: String, default: 'idle' }, // idle | recording | stopping | error
  level: { type: Number, default: 0 },
  duration: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['start', 'stop'])

const durationText = computed(() => formatDuration(props.duration, false))
const canvasEl = ref(null)
const history = [] // 最近 60 个电平采样（条形波形）
let rafId = 0

function draw() {
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height
  ctx.clearRect(0, 0, w, h)
  const n = history.length
  if (!n) return
  const barW = w / 60
  for (let i = 0; i < 60; i += 1) {
    const v = history[Math.max(0, n - 60 + i)] || 0
    const bh = Math.max(3, v * (h - 8))
    const x = i * barW + barW * 0.25
    const y = (h - bh) / 2
    const grad = ctx.createLinearGradient(0, y, 0, y + bh)
    grad.addColorStop(0, '#22d3ee')
    grad.addColorStop(1, '#6366f1')
    ctx.fillStyle = grad
    ctx.beginPath()
    if (typeof ctx.roundRect === 'function') {
      ctx.roundRect(x, y, barW * 0.5, bh, 3)
    } else {
      ctx.rect(x, y, barW * 0.5, bh)
    }
    ctx.fill()
  }
}

function loop() {
  draw()
  rafId = requestAnimationFrame(loop)
}

watch(
  () => props.state,
  (st) => {
    if (st === 'recording') {
      history.length = 0
      rafId = requestAnimationFrame(loop)
    } else if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = 0
      draw()
    }
  },
)

watch(
  () => props.level,
  (lv) => {
    if (props.state === 'recording') {
      history.push(Math.max(0.02, Math.min(1, lv || 0)))
      if (history.length > 120) history.shift()
    }
  },
)

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId)
})

function onClick() {
  if (props.state === 'recording') emit('stop')
  else if (props.state === 'idle') emit('start')
}
</script>

<style scoped>
.recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.wave-wrap {
  height: 56px;
  border-radius: 14px;
  background: rgba(34, 211, 238, 0.06);
  border: 1px solid rgba(34, 211, 238, 0.18);
  overflow: hidden;
}
.wave-wrap.hidden {
  display: none;
}
.wave-canvas {
  display: block;
}
.mic-btn {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 8px 28px rgba(99, 102, 241, 0.45);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.mic-btn:hover {
  transform: translateY(-2px) scale(1.04);
  box-shadow: 0 12px 34px rgba(99, 102, 241, 0.55);
}
.mic-btn:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}
.mic-btn.recording {
  background: linear-gradient(135deg, #ef4444, #f97316);
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6);
  animation: pulse 1.4s infinite;
}
.mic-btn.stopping {
  background: linear-gradient(135deg, #f59e0b, #ef4444);
  animation: none;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.55); }
  70% { box-shadow: 0 0 0 22px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
.recorder-hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  min-height: 18px;
}
html.light .recorder-hint {
  color: rgba(28, 34, 55, 0.55);
}
</style>

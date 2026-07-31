<template>
  <div class="recorder" :class="state">
    <!-- 电平条 -->
    <div v-if="state === 'recording' || state === 'stopping'" class="level-bar">
      <div class="level-fill" :style="{ width: (level * 100).toFixed(0) + '%' }" />
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
import { computed } from 'vue'
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
  gap: 14px;
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
.level-bar {
  width: 120px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
}
.level-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #34d399, #22d3ee);
  transition: width 80ms linear;
}
.recorder-hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  min-height: 18px;
}
</style>

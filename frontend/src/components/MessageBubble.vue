<template>
  <div class="bubble-row" :class="roleClass">
    <div v-if="role === 'assistant'" class="avatar">VP</div>
    <div class="bubble" :class="roleClass">
      <div v-if="role === 'user'" class="voice-tag">
        <el-icon :size="12"><Microphone /></el-icon>
        语音
      </div>
      <p class="content">{{ content }}</p>
      <span class="meta">
        <template v-if="engine">· {{ engine }}</template>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Microphone } from '@element-plus/icons-vue'

const props = defineProps({
  role: { type: String, default: 'user' }, // user | assistant
  content: { type: String, default: '' },
  engine: { type: String, default: '' },
})
const roleClass = computed(() => (props.role === 'assistant' ? 'assistant' : 'user'))
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
.meta {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  opacity: 0.6;
}
</style>

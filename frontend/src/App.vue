<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="logo">
          <el-icon :size="20"><Microphone /></el-icon>
        </div>
        <div class="brand-text">
          <span class="brand-name">VoicePilot</span>
          <span class="brand-sub">语音实时助手 · v0.1.0</span>
        </div>
      </div>
      <div class="topbar-right">
        <span class="status"><i class="status-dot" /> 演示模式</span>
      </div>
    </header>

    <main class="main">
      <ChatView />
    </main>
  </div>
</template>

<script setup>
import { Microphone } from '@element-plus/icons-vue'
import ChatView from '@/views/ChatView.vue'
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(15, 20, 40, 0.55);
  backdrop-filter: blur(12px);
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 17px;
  font-weight: 700;
  color: #f0f2ff;
  letter-spacing: 0.3px;
}
.brand-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.06);
  padding: 5px 12px;
  border-radius: 999px;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.9);
}
.main {
  flex: 1;
  min-height: 0;
  display: flex;
  justify-content: center;
}
.main :deep(.chat) {
  width: 100%;
  max-width: 860px;
  padding: 0 28px;
}
@media (max-width: 640px) {
  .topbar { padding: 12px 16px; }
  .main :deep(.chat) { padding: 0 14px; }
}
</style>

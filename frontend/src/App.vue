<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="logo">
          <el-icon :size="20"><Microphone /></el-icon>
        </div>
        <div class="brand-text">
          <span class="brand-name">VoicePilot</span>
          <span class="brand-sub">语音实时助手 · v1.1.0</span>
        </div>
      </div>
      <div class="topbar-right">
        <nav class="nav">
          <RouterLink to="/" class="nav-link" :class="{ active: route.path === '/' }">对话</RouterLink>
          <RouterLink to="/settings" class="nav-link" :class="{ active: route.path.startsWith('/settings') }">设置</RouterLink>
        </nav>
        <button class="theme-btn" :title="isDark ? '切换到亮色' : '切换到暗色'" @click="toggleTheme">
          <el-icon :size="16"><Moon v-if="isDark" /><Sunny v-else /></el-icon>
        </button>
      </div>
    </header>

    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Microphone, Moon, Sunny } from '@element-plus/icons-vue'

const route = useRoute()
const THEME_KEY = 'voicepilot-theme'
const isDark = ref(true)

function applyTheme(dark) {
  document.documentElement.classList.toggle('light', !dark)
}

function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme(isDark.value)
  try {
    localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
  } catch {
    /* ignore */
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light') isDark.value = false
  } catch {
    /* ignore */
  }
  applyTheme(isDark.value)
})
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
}
.main :deep(.chat) {
  width: 100%;
}
@media (max-width: 640px) {
  .topbar { padding: 12px 16px; }
}

.nav {
  display: flex;
  gap: 6px;
  margin-right: 12px;
}
.nav-link {
  color: rgba(255, 255, 255, 0.55);
  text-decoration: none;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 999px;
  transition: all 0.15s ease;
}
.nav-link:hover {
  color: #e6e9f5;
  background: rgba(255, 255, 255, 0.08);
}
.nav-link.active {
  color: #fff;
  background: rgba(99, 102, 241, 0.35);
}
.theme-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: #e6e9f5;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.theme-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}
.topbar-right {
  display: flex;
  align-items: center;
}
</style>

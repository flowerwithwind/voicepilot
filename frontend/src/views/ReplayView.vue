<template>
  <div class="replay">
    <h2 class="page-title">会话回放</h2>
    <p class="page-sub">正在加载会话 #{{ sessionId }}…</p>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
const sessionId = route.params.sessionId
</script>

<style scoped>
.replay {
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 28px;
}
.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  color: #e6e9f5;
}
.page-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
}
</style>

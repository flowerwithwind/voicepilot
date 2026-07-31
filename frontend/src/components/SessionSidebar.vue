<template>
  <aside class="sidebar">
    <div class="sidebar-head">
      <span class="sidebar-title">会话</span>
      <div class="head-actions">
        <el-button size="small" class="demo-btn" title="加载内置示例会话（语音→工具→确认）" @click="$emit('demo')">
          <el-icon><MagicStick /></el-icon>
          <span class="demo-text">示例</span>
        </el-button>
        <el-button size="small" circle class="add-btn" title="新建会话" @click="$emit('create')">
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>
    </div>
    <div class="sidebar-list">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeId }"
        @click="$emit('select', s.id)"
      >
        <div class="item-main">
          <div class="item-title">{{ s.title }}</div>
          <div class="item-meta">{{ s.message_count }} 条 · {{ formatDateTime(s.updated_at) }}</div>
        </div>
        <el-icon class="item-del" title="删除会话" @click.stop="$emit('remove', s.id)"><Delete /></el-icon>
      </div>
      <div v-if="loading" class="sidebar-empty">加载中…</div>
      <div v-else-if="!sessions.length" class="sidebar-empty">暂无会话，点击 + 新建</div>
    </div>
  </aside>
</template>

<script setup>
import { Delete, MagicStick, Plus } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/format'

defineProps({
  sessions: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
  loading: { type: Boolean, default: false },
})
defineEmits(['select', 'create', 'remove', 'demo'])
</script>

<style scoped>
.sidebar {
  width: 250px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(13, 18, 38, 0.6);
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: #e6e9f5;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.add-btn {
  color: #c7d2fe !important;
  background: rgba(99, 102, 241, 0.18) !important;
  border: none !important;
}
.demo-btn {
  color: #fde68a !important;
  background: rgba(251, 191, 36, 0.14) !important;
  border: 1px solid rgba(251, 191, 36, 0.35) !important;
  font-size: 12px;
  height: 24px;
  padding: 0 8px;
}
.demo-btn:hover {
  background: rgba(251, 191, 36, 0.24) !important;
}
@media (max-width: 768px) {
  .demo-text { display: none; }
}
.sidebar-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}
.session-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.session-item.active {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.28), rgba(139, 92, 246, 0.22));
  border: 1px solid rgba(99, 102, 241, 0.4);
}
.item-main {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 13px;
  color: #e6e9f5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-meta {
  margin-top: 3px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.38);
}
.item-del {
  color: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.session-item:hover .item-del {
  opacity: 1;
}
.item-del:hover {
  color: #f87171;
}
.sidebar-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
}
@media (max-width: 768px) {
  .sidebar {
    width: 190px;
  }
}
</style>

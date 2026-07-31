<template>
  <div class="settings">
    <h2 class="page-title">引擎设置</h2>
    <p class="page-sub">配置后保存即时生效；API Key 仅以脱敏形式回显，输入为空表示不修改。</p>

    <el-alert v-if="saved" type="success" :closable="true" show-icon title="设置已保存" class="mb" @close="saved = false" />
    <el-alert v-if="error" type="error" :closable="true" show-icon :title="error" class="mb" @close="error = ''" />

    <el-form label-position="top" class="section-form">
      <h3 class="section-title">LLM 对话模型</h3>
      <div class="grid">
        <el-form-item label="Base URL">
          <el-input v-model="model.base_url" placeholder="https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="API Key（已脱敏）">
          <el-input v-model="model.api_key" type="password" show-password :placeholder="masked.model || '留空不修改'" />
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="model.model" placeholder="deepseek-chat" />
        </el-form-item>
        <el-form-item label="Temperature">
          <el-slider v-model="model.temperature" :min="0" :max="2" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="Max Tokens">
          <el-input-number v-model="model.max_tokens" :min="64" :max="8192" :step="64" />
        </el-form-item>
      </div>

      <h3 class="section-title">ASR 语音识别</h3>
      <div class="grid">
        <el-form-item label="引擎">
          <el-select v-model="asr.engine">
            <el-option label="规则回声（演示，无需 Key）" value="rule" />
            <el-option label="OpenAI 兼容 Whisper" value="openai" />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="asr.base_url" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key（已脱敏）">
          <el-input v-model="asr.api_key" type="password" show-password :placeholder="masked.asr || '留空不修改'" />
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="asr.model" placeholder="whisper-1" />
        </el-form-item>
      </div>

      <h3 class="section-title">TTS 语音合成</h3>
      <div class="grid">
        <el-form-item label="引擎">
          <el-select v-model="tts.engine">
            <el-option label="浏览器 speechSynthesis（零成本）" value="browser" />
          </el-select>
        </el-form-item>
        <el-form-item label="音色（浏览器语音名，留空自动）">
          <el-input v-model="tts.voice" placeholder="如：Microsoft Xiaoxiao Online (Natural)" />
        </el-form-item>
        <el-form-item label="语速">
          <el-slider v-model="tts.rate" :min="0.5" :max="2" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="音调">
          <el-slider v-model="tts.pitch" :min="0.5" :max="2" :step="0.1" show-input />
        </el-form-item>
      </div>

      <div class="actions">
        <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
        <el-button :loading="testing" @click="test">测试模型连接</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, testConnection, updateSettings } from '@/api/settings'

const model = reactive({ base_url: '', api_key: '', model: '', temperature: 0.7, max_tokens: 1024 })
const asr = reactive({ engine: 'rule', base_url: '', api_key: '', model: 'whisper-1' })
const tts = reactive({ engine: 'browser', voice: '', rate: 1.0, pitch: 1.0 })
const masked = reactive({ model: '', asr: '' })
const saving = ref(false)
const testing = ref(false)
const saved = ref(false)
const error = ref('')

function fill(data) {
  Object.assign(model, data.model || {})
  Object.assign(asr, data.asr || {})
  Object.assign(tts, data.tts || {})
  masked.model = (data.model && data.model.api_key) || ''
  masked.asr = (data.asr && data.asr.api_key) || ''
}

async function load() {
  try {
    fill(await getSettings())
  } catch (e) {
    error.value = e.message || '读取设置失败'
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const data = await updateSettings({
      model: { ...model },
      asr: { ...asr },
      tts: { ...tts },
    })
    fill(data)
    saved.value = true
    ElMessage.success('设置已保存')
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  error.value = ''
  try {
    const res = await testConnection({ ...model })
    if (res.ok) {
      ElMessage.success('模型连接成功')
    } else {
      error.value = '连接失败：' + (res.error || '未知错误')
    }
  } catch (e) {
    error.value = e.message || '测试失败'
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings {
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 28px 48px;
  overflow-y: auto;
}
.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  color: #e6e9f5;
}
.page-sub {
  margin: 0 0 18px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
}
.mb {
  margin-bottom: 14px;
}
.section-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.section-title {
  margin: 18px 0 6px;
  font-size: 14px;
  color: #a5b4fc;
  border-left: 3px solid #6366f1;
  padding-left: 10px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0 18px;
}
.actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}
html.light .page-title {
  color: #1c2237;
}
html.light .page-sub {
  color: rgba(28, 34, 55, 0.55);
}
</style>

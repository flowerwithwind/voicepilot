import { request } from './http'

/** 读取引擎配置（LLM/ASR/TTS），API Key 已脱敏。 */
export function getSettings() {
  return request('/api/settings')
}

/** 保存引擎配置；api_key 传空/掩码值表示不修改。 */
export function updateSettings(payload) {
  return request('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/** 用给定模型配置测试连接。 */
export function testConnection(model) {
  return request('/api/settings/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
}

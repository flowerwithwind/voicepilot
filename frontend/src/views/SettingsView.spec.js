import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SettingsView from './SettingsView.vue'

const api = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  testConnection: vi.fn(),
}))

vi.mock('@/api/settings', () => api)

async function mountView() {
  const wrapper = mount(SettingsView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getSettings.mockResolvedValue({
    model: {
      base_url: 'https://api.deepseek.com/v1',
      api_key: 'sk-a****1234',
      model: 'deepseek-chat',
      temperature: 0.7,
      max_tokens: 1024,
    },
    asr: { engine: 'rule', base_url: '', api_key: '', model: 'whisper-1' },
    tts: { engine: 'browser', voice: '', rate: 1.0, pitch: 1.0 },
    capabilities: { asr: true, llm: true, tts: true },
  })
  api.updateSettings.mockImplementation(async (p) => ({ ...p }))
  api.testConnection.mockResolvedValue({ ok: true, error: null })
})

describe('SettingsView', () => {
  it('loads and renders sections with masked key', async () => {
    const w = await mountView()
    expect(w.text()).toContain('引擎设置')
    expect(w.text()).toContain('LLM 对话模型')
    expect(w.text()).toContain('ASR 语音识别')
    expect(w.text()).toContain('TTS 语音合成')
    expect(w.find('input[placeholder="sk-a****1234"]').exists()).toBe(true)
  })

  it('saves settings on button click', async () => {
    const w = await mountView()
    const saveBtn = w.findAll('button').find((b) => b.text().includes('保存设置'))
    await saveBtn.trigger('click')
    await flushPromises()
    expect(api.updateSettings).toHaveBeenCalledTimes(1)
    const payload = api.updateSettings.mock.calls[0][0]
    expect(payload.model.model).toBe('deepseek-chat')
    expect(payload.tts.engine).toBe('browser')
    expect(w.text()).toContain('设置已保存')
  })

  it('tests model connection', async () => {
    const w = await mountView()
    const testBtn = w.findAll('button').find((b) => b.text().includes('测试模型连接'))
    await testBtn.trigger('click')
    await flushPromises()
    expect(api.testConnection).toHaveBeenCalledTimes(1)
    expect(api.testConnection.mock.calls[0][0].base_url).toContain('deepseek')
  })
})

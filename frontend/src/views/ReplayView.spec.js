import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ReplayView from './ReplayView.vue'

const mocks = vi.hoisted(() => ({
  fetchReplay: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { sessionId: '7' } }),
}))
vi.mock('@/api/sessions', () => ({ fetchReplay: mocks.fetchReplay }))
vi.mock('@/api/audio', () => ({ audioUrl: (p) => (p ? '/api/audio/files/' + p : '') }))

function replayPayload() {
  return {
    session: {
      id: 7,
      title: '示例会话：语音工具调用',
      created_at: '2026-07-31T10:00:00',
      updated_at: '2026-07-31T10:01:00',
    },
    timeline: [
      { id: 1, role: 'user', stage: 'asr', text: '明天早上 9 点提醒我开周会', audio_path: 'demo/demo_16.wav', duration_ms: 1600, created_at: '2026-07-31T10:00:00' },
      { id: 2, role: 'assistant', stage: 'llm', text: '好的，需要确认后才会创建', audio_path: null, duration_ms: null, elapsed_ms: 3200, prompt_tokens: 120, completion_tokens: 480, created_at: '2026-07-31T10:00:02', tts: { engine: 'browser' } },
      { id: 3, role: 'tool', stage: 'tool', text: '工具调用：set_reminder(...) → 等待用户确认', audio_path: null, duration_ms: null, created_at: '2026-07-31T10:00:03' },
      { id: 4, role: 'user', stage: 'asr', text: '确认执行', audio_path: 'demo/demo_12.wav', duration_ms: 1200, created_at: '2026-07-31T10:00:05' },
      { id: 5, role: 'tool', stage: 'tool', text: '✅ 提醒已创建', audio_path: null, duration_ms: null, created_at: '2026-07-31T10:00:06' },
      { id: 6, role: 'assistant', stage: 'llm', text: '提醒已经设置好啦', audio_path: null, duration_ms: null, created_at: '2026-07-31T10:00:07', tts: { engine: 'browser' } },
    ],
  }
}

async function mountView() {
  const wrapper = mount(ReplayView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fetchReplay.mockResolvedValue(replayPayload())
})

describe('ReplayView', () => {
  it('renders session title and stage timeline', async () => {
    const w = await mountView()
    expect(mocks.fetchReplay).toHaveBeenCalledWith('7')
    expect(w.text()).toContain('示例会话：语音工具调用')
    expect(w.text()).toContain('ASR 语音识别')
    expect(w.text()).toContain('LLM 回复')
    expect(w.text()).toContain('工具调用')
    expect(w.text()).toContain('TTS 播报')
    expect(w.text()).toContain('6 条记录')
  })

  it('shows audio replay buttons only for voice messages', async () => {
    const w = await mountView()
    const playBtns = w.findAll('.act-btn')
    expect(playBtns).toHaveLength(2)
    expect(playBtns[0].text()).toContain('回听')
    expect(w.text()).toContain('音频 1.6 秒')
  })

  it('renders TTS tag on assistant messages', async () => {
    const w = await mountView()
    const ttsTags = w.findAll('.tts-tag')
    expect(ttsTags).toHaveLength(2)
    expect(ttsTags[0].text()).toContain('browser')
  })

  it('shows LLM metrics on llm messages', async () => {
    const w = await mountView()
    const metrics = w.findAll('.tl-metrics')
    expect(metrics).toHaveLength(1)
    expect(metrics[0].text()).toContain('LLM 3.2 秒 · ↑120 ↓480')
  })

  it('hides LLM metrics when metrics absent', async () => {
    const payload = replayPayload()
    payload.timeline = payload.timeline.map((t) => ({
      ...t,
      elapsed_ms: null,
      prompt_tokens: null,
      completion_tokens: null,
    }))
    mocks.fetchReplay.mockResolvedValue(payload)
    const w = await mountView()
    expect(w.findAll('.tl-metrics')).toHaveLength(0)
    expect(w.text()).not.toContain('· ↑')
  })

  it('shows error state when replay fails', async () => {
    mocks.fetchReplay.mockRejectedValue(new Error('会话不存在'))
    const w = await mountView()
    expect(w.text()).toContain('会话不存在')
  })
})

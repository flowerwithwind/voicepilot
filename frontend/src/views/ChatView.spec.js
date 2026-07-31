import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import RecorderButton from '@/components/RecorderButton.vue'
import ChatView from './ChatView.vue'

const mocks = vi.hoisted(() => ({
  streamChat: vi.fn(),
  listSessions: vi.fn(),
  listMessages: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  createDemoSession: vi.fn(),
  getSettings: vi.fn(),
}))

const rtMocks = vi.hoisted(() => {
  const handlers = new Map()
  return {
    handlers,
    rt: {
      status: { value: 'idle' },
      retries: { value: 0 },
      supported: { value: true },
      connect: vi.fn(),
      sendAudio: vi.fn(),
      sendMessage: vi.fn(),
      sendUtterance: vi.fn(),
      sendCancel: vi.fn(),
      sendFlush: vi.fn(),
      sendApproval: vi.fn(),
      on: vi.fn((type, fn) => {
        if (!handlers.has(type)) handlers.set(type, new Set())
        handlers.get(type).add(fn)
        return () => {
          const set = handlers.get(type)
          if (set) set.delete(fn)
        }
      }),
      close: vi.fn(),
    },
    emit(type, payload) {
      const set = handlers.get(type)
      if (set) set.forEach((fn) => fn(payload))
    },
  }
})

const speechMocks = vi.hoisted(() => ({
  speaking: { value: false },
  supported: { value: true },
  speak: vi.fn(),
  cancel: vi.fn(),
}))

const recMocks = vi.hoisted(() => ({
  state: { value: 'idle' },
  level: { value: 0 },
  duration: { value: 0 },
  error: { value: '' },
  blob: { value: null },
  isSupported: { value: true },
  start: vi.fn(),
  stop: vi.fn(),
  cancel: vi.fn(),
}))

vi.mock('@/api/chat', () => ({ streamChat: mocks.streamChat }))
vi.mock('@/api/sessions', () => ({
  listSessions: mocks.listSessions,
  listMessages: mocks.listMessages,
  createSession: mocks.createSession,
  deleteSession: mocks.deleteSession,
  createDemoSession: mocks.createDemoSession,
}))
vi.mock('@/api/audio', () => ({ transcribe: vi.fn(), audioUrl: (p) => (p ? '/api/audio/files/' + p : '') }))
vi.mock('@/api/settings', () => ({ getSettings: mocks.getSettings }))
vi.mock('@/composables/useRealtime', () => ({ useRealtime: () => rtMocks.rt }))
vi.mock('@/composables/useSpeech', () => ({ useSpeech: () => speechMocks }))
vi.mock('@/composables/useRecorder', () => ({ useRecorder: () => recMocks }))

function makeStream(events) {
  return async function* gen() {
    for (const e of events) yield e
  }
}

function sendButton(wrapper) {
  return wrapper.findAll('button').find((b) => b.text().includes('发送'))
}

function micButton(wrapper) {
  return wrapper.find('.mic-btn')
}

async function mountView() {
  const wrapper = mount(ChatView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getSettings.mockResolvedValue({
    model: { base_url: '', api_key: '', model: '', temperature: 0.7, max_tokens: 1024 },
    asr: { engine: 'rule' },
    tts: { rate: 1, pitch: 1, voice: '' },
    capabilities: { asr: true, llm: false, tts: true },
  })
  mocks.listSessions.mockResolvedValue({
    total: 1,
    items: [
      { id: 1, title: '会话一', message_count: 0, updated_at: '2026-07-31T10:00:00' },
    ],
  })
  mocks.listMessages.mockResolvedValue([])
  mocks.createSession.mockResolvedValue({ id: 2, title: '新会话', message_count: 0 })
  mocks.createDemoSession.mockResolvedValue({ id: 42, title: '示例会话：语音工具调用', message_count: 6 })
  recMocks.start.mockResolvedValue()
  recMocks.stop.mockResolvedValue(null)
  recMocks.state.value = 'idle'
  rtMocks.rt.status.value = 'idle'
  rtMocks.rt.retries.value = 0
  rtMocks.rt.supported.value = true
  speechMocks.speaking.value = false
  rtMocks.handlers.clear()
})

describe('ChatView', () => {
  it('loads existing session on mount', async () => {
    const wrapper = await mountView()
    expect(mocks.listSessions).toHaveBeenCalled()
    expect(mocks.listMessages).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('会话一')
    expect(rtMocks.rt.connect).toHaveBeenCalledWith(1)
  })

  it('sends text and renders streamed assistant reply', async () => {
    mocks.streamChat.mockImplementation(
      makeStream([
        { type: 'delta', text: '你好' },
        { type: 'delta', text: '，我是 VoicePilot' },
        { type: 'done', message_id: 9, reply: '你好，我是 VoicePilot' },
      ]),
    )
    const wrapper = await mountView()
    await wrapper.find('textarea').setValue('你好')
    await sendButton(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()
    expect(mocks.streamChat).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: 1, content: '你好', saveUser: true }),
    )
    expect(wrapper.text()).toContain('你好，我是 VoicePilot')
  })

  it('executes non-sensitive tool without confirmation', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm')
    mocks.streamChat.mockImplementation(
      makeStream([
        { type: 'tool_call', request_id: 'w1', tool: 'query_weather', args: { city: '北京' }, preview: '查询天气：北京' },
        { type: 'delta', text: '✅ 已完成：北京今日天气' },
        { type: 'done', message_id: 11, reply: '✅ 已完成：北京今日天气' },
      ]),
    )
    const wrapper = await mountView()
    await wrapper.find('textarea').setValue('北京天气怎么样')
    await sendButton(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('北京今日天气')
  })

  it('asks confirmation for sensitive tools and re-sends with approval', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    mocks.streamChat
      .mockImplementationOnce(
        makeStream([
          { type: 'tool_call', request_id: 'abc', tool: 'set_reminder', args: { content: '开会', remind_at: '2026-08-01T09:00' }, preview: '设置提醒：开会（2026-08-01T09:00）' },
          { type: 'await_approval', request_id: 'abc' },
        ]),
      )
      .mockImplementationOnce(
        makeStream([
          { type: 'delta', text: '✅ 已创建提醒' },
          { type: 'done', message_id: 12, reply: '✅ 已创建提醒' },
        ]),
      )
    const wrapper = await mountView()
    await wrapper.find('textarea').setValue('明天9点提醒我开会')
    await sendButton(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalled()
    expect(mocks.streamChat).toHaveBeenCalledTimes(2)
    expect(mocks.streamChat.mock.calls[1][0].approval).toEqual({
      request_id: 'abc',
      approved: true,
    })
    expect(wrapper.text()).toContain('已创建提醒')
  })

  it('streams microphone PCM over websocket and renders partial/final/tts', async () => {
    rtMocks.rt.status.value = 'connected'
    const wrapper = await mountView()
    await micButton(wrapper).trigger('click')
    await flushPromises()
    expect(recMocks.start).toHaveBeenCalledWith(expect.objectContaining({ onPcm: expect.any(Function) }))
    expect(rtMocks.rt.connect).toHaveBeenCalledWith(1)
    // PCM 分片直接上送
    const { onPcm } = recMocks.start.mock.calls[0][0]
    onPcm(new Int16Array([100, -200, 300]))
    expect(rtMocks.rt.sendAudio).toHaveBeenCalledWith(expect.any(Int16Array))
    // 增量识别
    rtMocks.emit('asr.partial', { text: '（演示转写）正在识别… 0.5 秒', duration: 0.5 })
    await flushPromises()
    expect(wrapper.text()).toContain('正在识别')
    // 最终识别 + 流式回复 + TTS 帧
    rtMocks.emit('asr.final', { text: '（演示转写）已识别 1.0 秒语音', engine: 'rule', message_id: 5 })
    rtMocks.emit('delta', { text: '好的' })
    rtMocks.emit('tts', { text: '好的', engine: 'browser', audio: null })
    await flushPromises()
    expect(wrapper.text()).toContain('（演示转写）已识别')
    expect(wrapper.text()).toContain('好的')
    expect(speechMocks.speak).toHaveBeenCalledWith('好的', expect.objectContaining({ rate: 1, pitch: 1 }))
    rtMocks.emit('done', { message_id: 9, reply: '好的' })
    await flushPromises()
    // 停止录音 → flush
    wrapper.findComponent(RecorderButton).vm.$emit('stop')
    await flushPromises()
    expect(recMocks.stop).toHaveBeenCalled()
    expect(rtMocks.rt.sendFlush).toHaveBeenCalled()
  })

  it('loads built-in demo session via sidebar demo button', async () => {
    mocks.listMessages.mockResolvedValue([
      { id: 1, role: 'user', content: '明天早上 9 点提醒我开周会', audio_path: 'demo/demo_16.wav', duration_ms: 1600 },
      { id: 2, role: 'assistant', content: '好的，我来帮你设置提醒', audio_path: null, duration_ms: null },
    ])
    const wrapper = await mountView()
    await wrapper.find('.demo-btn').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(mocks.createDemoSession).toHaveBeenCalledTimes(1)
    expect(mocks.listMessages).toHaveBeenCalledWith(42)
    expect(wrapper.text()).toContain('示例会话：语音工具调用')
    expect(wrapper.find('.replay-link').attributes('href')).toBe('#/replay/42')
  })

  it('asks realtime approval over websocket for sensitive tools', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    const wrapper = await mountView()
    rtMocks.emit('tool_call', { request_id: 'abc', tool: 'set_reminder', args: {}, preview: '设置提醒：开会' })
    rtMocks.emit('await_approval', { request_id: 'abc' })
    await flushPromises()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalled()
    expect(rtMocks.rt.sendApproval).toHaveBeenCalledWith('abc', true)
    expect(wrapper.text()).toContain('设置提醒：开会')
  })

  it('barge-in: speaking cancels TTS and interrupt clears the turn', async () => {
    const wrapper = await mountView()
    speechMocks.speaking.value = true
    rtMocks.emit('vad', { event: 'speech_start' })
    expect(speechMocks.cancel).toHaveBeenCalled()
    rtMocks.emit('delta', { text: '正在回复' })
    await flushPromises()
    expect(wrapper.text()).toContain('正在回复')
    expect(wrapper.find('.cursor').exists()).toBe(true) // 流式光标在
    rtMocks.emit('interrupt')
    await flushPromises()
    expect(speechMocks.cancel).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.cursor').exists()).toBe(false) // 打断后不再流式
    expect(rtMocks.rt.sendFlush).not.toHaveBeenCalled()
  })

  it('falls back to legacy recording when realtime is unsupported', async () => {
    rtMocks.rt.supported.value = false
    const wrapper = await mountView()
    await micButton(wrapper).trigger('click')
    await flushPromises()
    expect(recMocks.start).toHaveBeenCalledWith({})
    expect(rtMocks.rt.connect).not.toHaveBeenCalledWith(1)
  })
})

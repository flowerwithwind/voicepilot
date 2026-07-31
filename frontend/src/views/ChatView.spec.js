import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import ChatView from './ChatView.vue'

const mocks = vi.hoisted(() => ({
  streamChat: vi.fn(),
  listSessions: vi.fn(),
  listMessages: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
}))

vi.mock('@/api/chat', () => ({ streamChat: mocks.streamChat }))
vi.mock('@/api/sessions', () => ({
  listSessions: mocks.listSessions,
  listMessages: mocks.listMessages,
  createSession: mocks.createSession,
  deleteSession: mocks.deleteSession,
}))
vi.mock('@/api/audio', () => ({ transcribe: vi.fn() }))

function makeStream(events) {
  return async function* gen() {
    for (const e of events) yield e
  }
}

function sendButton(wrapper) {
  return wrapper.findAll('button').find((b) => b.text().includes('发送'))
}

async function mountView() {
  const wrapper = mount(ChatView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listSessions.mockResolvedValue({
    total: 1,
    items: [
      { id: 1, title: '会话一', message_count: 0, updated_at: '2026-07-31T10:00:00' },
    ],
  })
  mocks.listMessages.mockResolvedValue([])
  mocks.createSession.mockResolvedValue({ id: 2, title: '新会话', message_count: 0 })
})

describe('ChatView', () => {
  it('loads existing session on mount', async () => {
    const wrapper = await mountView()
    expect(mocks.listSessions).toHaveBeenCalled()
    expect(mocks.listMessages).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('会话一')
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
})

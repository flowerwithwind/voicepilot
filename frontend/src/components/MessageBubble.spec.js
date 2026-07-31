import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import MessageBubble from './MessageBubble.vue'

vi.mock('@/api/audio', () => ({
  audioUrl: (p) => (p ? '/api/audio/files/' + p : ''),
}))

describe('MessageBubble', () => {
  it('renders content, engine and voice tag', () => {
    const w = mount(MessageBubble, {
      props: { role: 'user', content: '你好', engine: 'rule', viaVoice: true },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('你好')
    expect(w.text()).toContain('语音')
    expect(w.text()).toContain('rule')
  })

  it('shows replay button with audio path and plays audio', async () => {
    const w = mount(MessageBubble, {
      props: { role: 'user', content: 'x', audioPath: 'realtime/abc.wav', durationMs: 1200 },
      global: { plugins: [ElementPlus] },
    })
    const btn = w.findAll('button').find((b) => b.text().includes('回听'))
    expect(btn).toBeTruthy()
    const audio = w.find('audio')
    expect(audio.attributes('src')).toBe('/api/audio/files/realtime/abc.wav')
    // jsdom 无真实播放：play 返回 reject，状态应保持未播放且不抛异常
    audio.element.play = vi.fn().mockRejectedValue(new Error('jsdom no media'))
    await btn.trigger('click')
    expect(w.vm.playing).toBe(false)
  })

  it('emits resend for user messages', async () => {
    const w = mount(MessageBubble, {
      props: { role: 'user', content: '重发我' },
      global: { plugins: [ElementPlus] },
    })
    const btn = w.findAll('button').find((b) => b.text().includes('重发'))
    await btn.trigger('click')
    expect(w.emitted('resend')).toEqual([['重发我']])
  })

  it('does not show resend for assistant messages', () => {
    const w = mount(MessageBubble, {
      props: { role: 'assistant', content: '回复' },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).not.toContain('重发')
  })
})

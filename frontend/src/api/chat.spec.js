import { beforeEach, describe, expect, it, vi } from 'vitest'
import { streamChat } from './chat'

function sseStream(frames) {
  const encoder = new TextEncoder()
  const chunks = frames.map((f) => encoder.encode('data: ' + JSON.stringify(f) + '\n\n'))
  return new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(c))
      controller.close()
    },
  })
}

describe('streamChat', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('parses SSE frames into events', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: sseStream([
        { type: 'delta', text: '你好' },
        { type: 'done', message_id: 3, reply: '你好' },
      ]),
    })
    const events = []
    for await (const ev of streamChat({ sessionId: 1, content: 'hi' })) events.push(ev)
    expect(events).toEqual([
      { type: 'delta', text: '你好' },
      { type: 'done', message_id: 3, reply: '你好' },
    ])
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/chat/messages',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.stringContaining('"save_user":true'),
      }),
    )
  })

  it('passes approval and saveUser=false', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, body: sseStream([]) })
    const it = streamChat({ sessionId: 2, content: 'x', approval: { request_id: 'a1', approved: true }, saveUser: false })
    await it.next()
    const body = JSON.parse(global.fetch.mock.calls[0][1].body)
    expect(body.approval).toEqual({ request_id: 'a1', approved: true })
    expect(body.save_user).toBe(false)
  })

  it('throws ApiError with detail on http error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: '会话不存在' }),
    })
    const gen = streamChat({ sessionId: 9, content: 'hi' })
    await expect(gen.next()).rejects.toThrow('会话不存在')
  })
})

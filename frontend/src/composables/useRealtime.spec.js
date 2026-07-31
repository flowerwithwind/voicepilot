import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRealtime } from './useRealtime'

class FakeWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = FakeWebSocket.CONNECTING
    this.sent = []
    this.binaryType = ''
    FakeWebSocket.instances.push(this)
  }

  send(data) {
    this.sent.push(data)
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED
    if (this.onclose) this.onclose({})
  }

  // ---- 测试辅助 ----
  serverOpen() {
    this.readyState = FakeWebSocket.OPEN
    if (this.onopen) this.onopen()
  }

  serverSend(obj) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(obj) })
  }

  serverClose() {
    this.readyState = FakeWebSocket.CLOSED
    if (this.onclose) this.onclose({})
  }
}

function lastWs() {
  return FakeWebSocket.instances[FakeWebSocket.instances.length - 1]
}

beforeEach(() => {
  vi.stubGlobal('WebSocket', FakeWebSocket)
  FakeWebSocket.instances = []
  vi.useFakeTimers()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('useRealtime', () => {
  it('connects and sends hello with session id', () => {
    const rt = useRealtime()
    expect(rt.supported.value).toBe(true)
    rt.connect(42)
    expect(rt.status.value).toBe('connecting')
    lastWs().serverOpen()
    expect(rt.status.value).toBe('connected')
    expect(lastWs().sent).toEqual([JSON.stringify({ type: 'hello', session_id: 42 })])
    rt.close()
  })

  it('re-sends hello when switching session on live connection', () => {
    const rt = useRealtime()
    rt.connect(1)
    lastWs().serverOpen()
    rt.connect(2)
    expect(lastWs().sent).toContain(JSON.stringify({ type: 'hello', session_id: 2 }))
    rt.close()
  })

  it('emits server events to registered handlers and supports unsubscribe', () => {
    const rt = useRealtime()
    const handler = vi.fn()
    const off = rt.on('delta', handler)
    rt.connect(1)
    lastWs().serverOpen()
    lastWs().serverSend({ type: 'delta', text: '你好' })
    expect(handler).toHaveBeenCalledWith({ type: 'delta', text: '你好' })
    off()
    lastWs().serverSend({ type: 'delta', text: '再见' })
    expect(handler).toHaveBeenCalledTimes(1)
    rt.close()
  })

  it('sends control messages and raw audio bytes', () => {
    const rt = useRealtime()
    rt.connect(1)
    lastWs().serverOpen()
    rt.sendUtterance('你好')
    rt.sendCancel()
    rt.sendFlush()
    rt.sendApproval('r1', true)
    rt.sendAudio(new Uint8Array([1, 2, 3]))
    expect(lastWs().sent[1]).toBe(JSON.stringify({ type: 'utterance', text: '你好' }))
    expect(lastWs().sent[2]).toBe(JSON.stringify({ type: 'cancel' }))
    expect(lastWs().sent[3]).toBe(JSON.stringify({ type: 'flush' }))
    expect(lastWs().sent[4]).toBe(JSON.stringify({ type: 'approval', request_id: 'r1', approved: true }))
    expect(lastWs().sent[5]).toBeInstanceOf(Uint8Array)
    rt.close()
  })

  it('drops sends while not connected', () => {
    const rt = useRealtime()
    rt.sendUtterance('你好')
    rt.sendAudio(new Uint8Array([1]))
    expect(FakeWebSocket.instances).toHaveLength(0)
  })

  it('reconnects with exponential backoff and resets retries', () => {
    const rt = useRealtime()
    rt.connect(1)
    lastWs().serverOpen()
    lastWs().serverClose()
    expect(rt.status.value).toBe('reconnecting')
    expect(rt.retries.value).toBe(1)
    vi.advanceTimersByTime(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)
    lastWs().serverOpen()
    expect(rt.status.value).toBe('connected')
    expect(rt.retries.value).toBe(0)
    rt.close()
  })

  it('does not reconnect after manual close', () => {
    const rt = useRealtime()
    rt.connect(1)
    lastWs().serverOpen()
    rt.close()
    expect(rt.status.value).toBe('idle')
    vi.advanceTimersByTime(60000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('falls back to unsupported when WebSocket is unavailable', () => {
    vi.stubGlobal('WebSocket', undefined)
    const rt = useRealtime()
    expect(rt.supported.value).toBe(false)
    rt.connect(1)
    expect(rt.status.value).toBe('unsupported')
  })
})

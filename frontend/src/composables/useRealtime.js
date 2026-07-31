/**
 * WebSocket 实时链路封装：连接 / 指数退避重连 / 事件分发 / 会话切换。
 *
 * 协议见 backend/app/api/realtime.py。浏览器不支持 WebSocket（如 jsdom 测试环境）
 * 时自动降级为 unsupported，不抛错。
 */
import { computed, getCurrentInstance, onBeforeUnmount, ref } from 'vue'

const BASE_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 10000

export function useRealtime() {
  const status = ref('idle') // idle | connecting | connected | reconnecting | unsupported
  const retries = ref(0)

  let ws = null
  let sessionId = null
  let manualClose = false
  let reconnectTimer = null
  let reconnectDelay = BASE_BACKOFF_MS
  const listeners = new Map()

  const supported = computed(() => typeof WebSocket !== 'undefined')

  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss://' : 'ws://'
    return proto + location.host + '/ws/chat'
  }

  function emit(type, payload) {
    const set = listeners.get(type)
    if (!set) return
    set.forEach((fn) => {
      try {
        fn(payload)
      } catch (e) {
        console.error('[useRealtime] handler error', e)
      }
    })
  }

  function clearTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function sendHello() {
    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify({ type: 'hello', session_id: sessionId }))
    }
  }

  function open() {
    if (!supported.value) {
      status.value = 'unsupported'
      return
    }
    status.value = 'connecting'
    try {
      ws = new WebSocket(wsUrl())
    } catch {
      status.value = 'unsupported'
      return
    }
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      status.value = 'connected'
      retries.value = 0
      reconnectDelay = BASE_BACKOFF_MS
      sendHello()
    }
    ws.onmessage = (event) => {
      if (typeof event.data !== 'string') return
      let msg = null
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }
      if (msg && msg.type) emit(msg.type, msg)
    }
    ws.onclose = () => {
      ws = null
      if (manualClose) {
        status.value = 'idle'
        return
      }
      if (!supported.value) return
      status.value = 'reconnecting'
      retries.value += 1
      clearTimer()
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        open()
      }, reconnectDelay)
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_BACKOFF_MS)
    }
    ws.onerror = () => {
      // onclose 会随后触发，统一走重连逻辑
      try {
        if (ws) ws.close()
      } catch {
        /* ignore */
      }
    }
  }

  function connect(sid) {
    sessionId = sid ?? null
    if (!supported.value) {
      status.value = 'unsupported'
      return
    }
    if (ws && ws.readyState === 1) {
      sendHello() // 已连接：仅更新会话
      return
    }
    if (ws && (ws.readyState === 0 || ws.readyState === 2)) {
      // 连接中 / 关闭中：等 onclose 后自动重连（新 sessionId 已记录）
      manualClose = false
      return
    }
    open()
  }

  function sendAudio(bytes) {
    if (ws && ws.readyState === 1 && bytes && bytes.byteLength) {
      ws.send(bytes)
    }
  }

  function sendMessage(obj) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj))
  }

  function sendUtterance(text) {
    sendMessage({ type: 'utterance', text })
  }

  function sendCancel() {
    sendMessage({ type: 'cancel' })
  }

  function sendFlush() {
    sendMessage({ type: 'flush' })
  }

  function sendApproval(requestId, approved) {
    sendMessage({ type: 'approval', request_id: requestId, approved: !!approved })
  }

  function on(type, fn) {
    if (!listeners.has(type)) listeners.set(type, new Set())
    listeners.get(type).add(fn)
    return () => {
      const set = listeners.get(type)
      if (set) set.delete(fn)
    }
  }

  function close() {
    manualClose = true
    clearTimer()
    retries.value = 0
    if (ws) {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      ws = null
    }
    status.value = 'idle'
  }

  if (getCurrentInstance()) onBeforeUnmount(close)

  return {
    status,
    retries,
    supported,
    connect,
    sendAudio,
    sendMessage,
    sendUtterance,
    sendCancel,
    sendFlush,
    sendApproval,
    on,
    close,
  }
}

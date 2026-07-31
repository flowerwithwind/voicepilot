/** SSE 对话流：解析 /api/chat/messages 的 data 事件。 */
import { ApiError } from './http'

export async function* streamChat({ sessionId, content, approval, saveUser = true, signal } = {}) {
  let resp
  try {
    resp = await fetch('/api/chat/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        content,
        approval: approval || null,
        save_user: saveUser,
      }),
      signal,
    })
  } catch {
    throw new ApiError('网络连接失败，请确认后端服务已启动', 0)
  }
  if (!resp.ok) {
    let detail = ''
    try {
      const body = await resp.json()
      detail = body.detail || body.message || ''
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(detail || '请求失败（' + resp.status + '）', resp.status)
  }
  if (!resp.body) throw new ApiError('当前浏览器不支持流式响应', 0)

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let sep
      while ((sep = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, sep)
        buf = buf.slice(sep + 2)
        for (const line of frame.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const raw = trimmed.slice(5).trim()
          if (!raw) continue
          try {
            yield JSON.parse(raw)
          } catch {
            /* 忽略坏帧 */
          }
        }
      }
    }
  } finally {
    reader.releaseLock?.()
  }
}

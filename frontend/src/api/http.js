/** fetch 封装：统一 JSON 解析与中文错误提示。 */
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function request(url, options = {}) {
  let resp
  try {
    resp = await fetch(url, options)
  } catch {
    throw new ApiError('网络连接失败，请确认后端服务已启动', 0)
  }
  const contentType = resp.headers.get('content-type') || ''
  const body = contentType.includes('application/json') ? await resp.json() : null
  if (!resp.ok) {
    const detail = body && (body.detail || body.message)
    throw new ApiError(detail || `请求失败（${resp.status}）`, resp.status)
  }
  return body
}

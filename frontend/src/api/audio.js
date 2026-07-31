import { request } from './http'

/** 上传录音并返回转写结果。 */
export function transcribe(blob, { sessionId, duration } = {}) {
  const form = new FormData()
  const ext = blob.type.includes('ogg') ? 'ogg' : 'webm'
  form.append('file', blob, `recording.${ext}`)
  if (sessionId != null) form.append('session_id', String(sessionId))
  if (duration != null) form.append('duration', String(duration))
  return request('/api/audio/transcribe', { method: 'POST', body: form })
}

/** 拼接回听音频 URL（audio_path 相对 AUDIO_DIR）。 */
export function audioUrl(audioPath) {
  if (!audioPath) return ''
  return '/api/audio/files/' + audioPath.split('/').map(encodeURIComponent).join('/')
}

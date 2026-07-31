import { request } from './http'

export function listSessions(limit = 50) {
  return request('/api/sessions?limit=' + limit)
}

export function listMessages(sessionId) {
  return request('/api/sessions/' + sessionId + '/messages')
}

export function createSession(title = '新会话') {
  return request('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export function deleteSession(sessionId) {
  return request('/api/sessions/' + sessionId, { method: 'DELETE' })
}

export function fetchReplay(sessionId) {
  return request('/api/sessions/' + sessionId + '/replay')
}

export function createDemoSession() {
  return request('/api/sessions/demo', { method: 'POST' })
}

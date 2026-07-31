import { request } from './http'

export function listSessions(limit = 50) {
  return request('/api/sessions?limit=' + limit)
}

export function listMessages(sessionId) {
  return request('/api/sessions/' + sessionId + '/messages')
}

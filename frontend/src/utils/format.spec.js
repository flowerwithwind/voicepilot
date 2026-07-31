import { describe, expect, it } from 'vitest'
import { formatBytes, formatClock, formatDateTime, formatDuration } from './format'

describe('formatDuration', () => {
  it('formats seconds under a minute', () => {
    expect(formatDuration(3.5)).toBe('3.5 秒')
    expect(formatDuration(0)).toBe('0.0 秒')
  })
  it('formats minutes as mm:ss', () => {
    expect(formatDuration(65)).toBe('01:05')
    expect(formatDuration(125.4)).toBe('02:05')
  })
})

describe('formatBytes', () => {
  it('formats kb and mb', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(3 * 1024 * 1024)).toBe('3.0 MB')
  })
})

describe('formatClock', () => {
  it('formats iso time', () => {
    expect(formatClock('2026-07-31T12:05:00')).toBe('12:05')
    expect(formatClock('')).toBe('')
    expect(formatClock('bad')).toBe('')
  })
})

describe('formatDateTime', () => {
  it('formats iso to MM-DD HH:mm', () => {
    expect(formatDateTime('2026-07-31T12:05:00')).toBe('07-31 12:05')
    expect(formatDateTime('')).toBe('')
    expect(formatDateTime('bad')).toBe('')
  })
})

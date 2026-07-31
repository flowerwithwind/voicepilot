import { describe, expect, it } from 'vitest'
import { audioUrl } from './audio'

describe('audioUrl', () => {
  it('normalizes Windows backslash paths (KN-03)', () => {
    expect(audioUrl('realtime\\legacy.wav')).toBe('/api/audio/files/realtime/legacy.wav')
    expect(audioUrl('realtime\\\\double.wav')).toBe('/api/audio/files/realtime//double.wav')
  })

  it('keeps posix paths unchanged', () => {
    expect(audioUrl('realtime/abc.wav')).toBe('/api/audio/files/realtime/abc.wav')
  })

  it('encodes each path segment', () => {
    expect(audioUrl('demo/a b.wav')).toBe('/api/audio/files/demo/a%20b.wav')
  })

  it('returns empty string for falsy input', () => {
    expect(audioUrl('')).toBe('')
    expect(audioUrl(null)).toBe('')
    expect(audioUrl(undefined)).toBe('')
  })
})

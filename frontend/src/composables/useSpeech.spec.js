import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSpeech } from './useSpeech'

class FakeUtterance {
  constructor(text) {
    this.text = text
  }
}

const synth = vi.hoisted(() => ({
  speak: vi.fn(),
  cancel: vi.fn(),
  getVoices: vi.fn(() => []),
}))

beforeEach(() => {
  synth.speak.mockReset()
  synth.cancel.mockReset()
  synth.getVoices.mockReset()
  synth.getVoices.mockReturnValue([])
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  vi.stubGlobal('speechSynthesis', synth)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useSpeech', () => {
  it('speaks text and tracks speaking state', () => {
    const speech = useSpeech()
    expect(speech.supported.value).toBe(true)
    speech.speak('你好，VoicePilot')
    expect(synth.speak).toHaveBeenCalledTimes(1)
    expect(speech.speaking.value).toBe(true)
    const u = synth.speak.mock.calls[0][0]
    expect(u).toBeInstanceOf(FakeUtterance)
    expect(u.lang).toBe('zh-CN')
    expect(u.rate).toBe(1)
    u.onend()
    expect(speech.speaking.value).toBe(false)
  })

  it('cancels current playback', () => {
    const speech = useSpeech()
    speech.speak('测试')
    speech.cancel()
    expect(synth.cancel).toHaveBeenCalled()
    expect(speech.speaking.value).toBe(false)
  })

  it('speak() cancels previous utterance first', () => {
    const speech = useSpeech()
    speech.speak('第一句')
    speech.speak('第二句')
    expect(synth.cancel).toHaveBeenCalledTimes(2) // speak() 每次先打断
    expect(synth.speak).toHaveBeenCalledTimes(2)
  })

  it('no-ops safely when speechSynthesis is unavailable', () => {
    vi.stubGlobal('speechSynthesis', undefined)
    vi.stubGlobal('SpeechSynthesisUtterance', undefined)
    const speech = useSpeech()
    expect(speech.supported.value).toBe(false)
    expect(() => speech.speak('你好')).not.toThrow()
    expect(() => speech.cancel()).not.toThrow()
    expect(speech.speaking.value).toBe(false)
  })
})

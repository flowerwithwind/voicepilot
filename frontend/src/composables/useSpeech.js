/** 浏览器 TTS 封装（speechSynthesis）：播报 / 打断（barge-in）。 */
import { computed, getCurrentInstance, onBeforeUnmount, ref } from 'vue'

export function useSpeech() {
  const speaking = ref(false)
  const supported = computed(
    () =>
      typeof speechSynthesis !== 'undefined' &&
      typeof SpeechSynthesisUtterance !== 'undefined',
  )

  function speak(text, { rate = 1, pitch = 1, voiceName = '', lang = 'zh-CN' } = {}) {
    if (!supported.value || !text) return
    cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.rate = rate
    utterance.pitch = pitch
    if (voiceName) {
      const voices = speechSynthesis.getVoices()
      const hit = voices.find((v) => v.name === voiceName || v.voiceURI === voiceName)
      if (hit) utterance.voice = hit
    }
    utterance.onend = () => {
      speaking.value = false
    }
    utterance.onerror = () => {
      speaking.value = false
    }
    speaking.value = true
    speechSynthesis.speak(utterance)
  }

  function cancel() {
    if (supported.value) {
      speechSynthesis.cancel()
      speaking.value = false
    }
  }

  if (getCurrentInstance()) onBeforeUnmount(cancel)

  return { speaking, supported, speak, cancel }
}

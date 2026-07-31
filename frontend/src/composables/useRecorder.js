/**
 * MediaRecorder + WebAudio 录音封装。
 * 状态机：idle → recording → stopping → idle（成功产出 blob）
 * 输出：实时电平（0~1）与录音时长，供波形/按钮动画使用。
 */
import { computed, onBeforeUnmount, ref } from 'vue'

export function useRecorder() {
  const state = ref('idle') // idle | recording | stopping | error
  const level = ref(0)
  const duration = ref(0)
  const error = ref('')
  const blob = ref(null)

  let mediaRecorder = null
  let stream = null
  let audioCtx = null
  let analyser = null
  let rafId = 0
  let chunks = []
  let startAt = 0
  let timerId = 0
  let resolveStop = null
  let discarded = false

  const isSupported = computed(
    () => typeof MediaRecorder !== 'undefined' && !!navigator?.mediaDevices?.getUserMedia,
  )

  function pickMimeType() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
    return candidates.find((t) => MediaRecorder.isTypeSupported(t)) || ''
  }

  function sampleLevel() {
    if (!analyser) return
    const buf = new Uint8Array(analyser.fftSize)
    analyser.getByteTimeDomainData(buf)
    let sum = 0
    for (let i = 0; i < buf.length; i += 1) {
      const v = (buf[i] - 128) / 128
      sum += v * v
    }
    level.value = Math.min(1, Math.sqrt(sum / buf.length) * 4)
    rafId = requestAnimationFrame(sampleLevel)
  }

  async function start() {
    if (state.value === 'recording') return
    error.value = ''
    blob.value = null
    discarded = false
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      state.value = 'error'
      error.value = '无法访问麦克风：请检查浏览器权限设置'
      return
    }
    try {
      audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)

      mediaRecorder = new MediaRecorder(stream, pickMimeType() ? { mimeType: pickMimeType() } : undefined)
      chunks = []
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data)
      }
      mediaRecorder.onstop = () => {
        const result = discarded ? null : new Blob(chunks, { type: mediaRecorder.mimeType || 'audio/webm' })
        cleanupTracks()
        if (discarded) {
          state.value = 'idle'
          resolveStop?.(null)
        } else {
          blob.value = result
          state.value = 'idle'
          resolveStop?.(result)
        }
      }
      mediaRecorder.onerror = () => {
        state.value = 'error'
        error.value = '录音出错，请重试'
      }

      mediaRecorder.start()
      state.value = 'recording'
      startAt = performance.now()
      level.value = 0
      duration.value = 0
      timerId = setInterval(() => {
        duration.value = (performance.now() - startAt) / 1000
      }, 100)
      rafId = requestAnimationFrame(sampleLevel)
    } catch {
      state.value = 'error'
      error.value = '录音初始化失败：' + (audioCtx?.state || '未知原因')
      cleanupTracks()
    }
  }

  function stop() {
    if (state.value !== 'recording' || !mediaRecorder) return Promise.resolve(null)
    state.value = 'stopping'
    stopMeters()
    return new Promise((resolve, reject) => {
      resolveStop = resolve
      try {
        mediaRecorder.stop()
      } catch (e) {
        reject(e)
      }
    })
  }

  function cancel() {
    if (!mediaRecorder || state.value === 'idle') return
    discarded = true
    stopMeters()
    try {
      mediaRecorder.stop()
    } catch {
      /* 已停止则忽略 */
    }
    level.value = 0
    duration.value = 0
  }

  function stopMeters() {
    cancelAnimationFrame(rafId)
    clearInterval(timerId)
  }

  function cleanupTracks() {
    stopMeters()
    stream?.getTracks().forEach((t) => t.stop())
    audioCtx?.close().catch(() => {})
    stream = null
    audioCtx = null
    analyser = null
    mediaRecorder = null
    level.value = 0
  }

  onBeforeUnmount(() => {
    stopMeters()
    stream?.getTracks().forEach((t) => t.stop())
    audioCtx?.close().catch(() => {})
  })

  return { state, level, duration, error, blob, isSupported, start, stop, cancel }
}

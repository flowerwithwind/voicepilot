/**
 * MediaRecorder + WebAudio 录音封装。
 * 状态机：idle → recording → stopping → idle（成功产出 blob）。
 *
 * M3 实时模式：start({ onPcm }) 时额外启动 ScriptProcessor 管线，
 * 把麦克风重采样为 16kHz 单声道 PCM16 分片（Int16Array），
 * 通过 onPcm 回调喂给 WebSocket（服务端 VAD / 增量 ASR）。
 * 输出：实时电平（0~1）与录音时长，供波形/按钮动效使用。
 */
import { computed, getCurrentInstance, onBeforeUnmount, ref } from 'vue'

const PCM_TARGET_RATE = 16000
const PCM_BUFFER_SIZE = 4096

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
  let processor = null
  let silentGain = null
  let pcmCb = null
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

  /** 麦克风 → 16kHz 单声道 PCM16：线性重采样，静音增益路由避免回声。 */
  function setupPcmPipeline(source) {
    if (!pcmCb || !audioCtx) return
    const ratio = audioCtx.sampleRate / PCM_TARGET_RATE
    processor = audioCtx.createScriptProcessor(PCM_BUFFER_SIZE, 1, 1)
    silentGain = audioCtx.createGain()
    silentGain.gain.value = 0
    processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0)
      const outLen = Math.max(1, Math.floor(input.length / ratio))
      const out = new Int16Array(outLen)
      for (let i = 0; i < outLen; i += 1) {
        const s = input[Math.floor(i * ratio)] || 0
        const c = Math.max(-1, Math.min(1, s))
        out[i] = c < 0 ? Math.round(c * 0x8000) : Math.round(c * 0x7fff)
      }
      if (pcmCb) pcmCb(out)
    }
    source.connect(processor)
    processor.connect(silentGain)
    silentGain.connect(audioCtx.destination)
  }

  function teardownPcm() {
    if (processor) {
      processor.onaudioprocess = null
      try {
        processor.disconnect()
      } catch {
        /* ignore */
      }
      processor = null
    }
    if (silentGain) {
      try {
        silentGain.disconnect()
      } catch {
        /* ignore */
      }
      silentGain = null
    }
    pcmCb = null
  }

  async function start(options = {}) {
    if (state.value === 'recording') return
    error.value = ''
    blob.value = null
    discarded = false
    pcmCb = typeof options.onPcm === 'function' ? options.onPcm : null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      state.value = 'error'
      error.value = '无法访问麦克风：请检查浏览器权限设置'
      return
    }
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext
      audioCtx = new Ctx()
      if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
      const source = audioCtx.createMediaStreamSource(stream)
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      setupPcmPipeline(source)

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
    teardownPcm()
    stream?.getTracks().forEach((t) => t.stop())
    audioCtx?.close().catch(() => {})
    stream = null
    audioCtx = null
    analyser = null
    mediaRecorder = null
    level.value = 0
  }

  if (getCurrentInstance()) {
    onBeforeUnmount(() => {
      stopMeters()
      teardownPcm()
      stream?.getTracks().forEach((t) => t.stop())
      audioCtx?.close().catch(() => {})
    })
  }

  return { state, level, duration, error, blob, isSupported, start, stop, cancel }
}

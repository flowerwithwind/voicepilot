/** 时长格式化：秒 → "mm:ss" 或 "x.x 秒"。 */
export function formatDuration(seconds, withUnit = true) {
  const s = Math.max(0, Number(seconds) || 0)
  if (s < 60) return withUnit ? s.toFixed(1) + ' 秒' : s.toFixed(1)
  const m = Math.floor(s / 60)
  const rest = Math.floor(s % 60)
  const mm = String(m).padStart(2, '0')
  const ss = String(rest).padStart(2, '0')
  return withUnit ? mm + ':' + ss : mm + ':' + ss
}

/** 字节格式化 → KB / MB。 */
export function formatBytes(bytes) {
  const n = Math.max(0, Number(bytes) || 0)
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}

/** 时间戳 → "HH:mm"。 */
export function formatClock(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return h + ':' + m
}

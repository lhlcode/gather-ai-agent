const beijingFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})

export function formatBeijing(utcText) {
  if (!utcText) return '时间未设置'

  const browserUtc = utcText.replace(/\.(\d{3})\d*Z$/, '.$1Z')
  const date = new Date(browserUtc)

  if (Number.isNaN(date.getTime())) return '时间格式错误'
  return beijingFormatter.format(date)
}
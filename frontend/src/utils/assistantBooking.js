const command = /^(?:请帮我|帮我|请)?\s*(重新报名|重试报名|报名)\s*活动\s*([1-9][0-9]{0,18})[。！!]?$/u
const hexId = /^[0-9a-f]{32}$/u

export function parseBooking(message) {
  const text = message.trim()
  const match = command.exec(text)
  if (!match || match[0] !== text || BigInt(match[2]) > 9223372036854775807n) return null
  return { eventId: match[2], retry: match[1] === '重试报名' }
}

export function bookingPayload(threadId, message, pending = null) {
  const booking = parseBooking(message)
  const payload = { thread_id: threadId, message: message.trim() }
  if (!booking) return payload
  if (booking.retry) {
    if (!pending || pending.thread_id !== threadId || parseBooking(pending.message)?.eventId !== booking.eventId) {
      throw new Error('没有找到这次报名的原编号，请使用待确认报名的重试按钮。')
    }
    return { ...payload, operation_id: pending.operation_id }
  }
  if (pending) throw new Error('还有一笔报名结果待确认，请先使用原编号重试或核对我的订单。')
  return { ...payload, operation_id: crypto.randomUUID().replaceAll('-', '') }
}

function storageKey(userId) {
  if (!Number.isSafeInteger(userId) || userId <= 0) throw new Error('登录身份未就绪。')
  return `ticket-assistant:pending:${userId}`
}

export function readPending(storage, userId) {
  try {
    const data = JSON.parse(storage.getItem(storageKey(userId)) || 'null')
    if (!data || !hexId.test(data.thread_id) || !hexId.test(data.operation_id) || typeof data.message !== 'string' || !parseBooking(data.message)) return null
    return { thread_id: data.thread_id, message: data.message, operation_id: data.operation_id }
  } catch {
    return null
  }
}

export function savePending(storage, userId, payload) {
  const value = { thread_id: payload.thread_id, message: payload.message, operation_id: payload.operation_id }
  try {
    storage.setItem(storageKey(userId), JSON.stringify(value))
    if (JSON.stringify(readPending(storage, userId)) !== JSON.stringify(value)) throw new Error('保存失败')
  } catch {
    throw new Error('无法保存本次报名编号，尚未提交。请允许此页面使用会话存储后重试。')
  }
}

export function clearPending(storage, userId) {
  storage.removeItem(storageKey(userId))
}

export function bookingSettled(response, payload) {
  return response.status === 'clarify' || response.tool_results?.some(result =>
    result.operation_id === payload.operation_id &&
    ['created', 'replayed', 'rejected'].includes(result.status)
  )
}

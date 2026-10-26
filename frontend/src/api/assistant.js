async function request(path, token, { method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(`/ai${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      signal: AbortSignal.timeout(120000),
    })
  } catch {
    throw new Error('连接中断或等待超时，请重试。报名结果需要使用原编号核对。')
  }

  let data
  try {
    data = await response.json()
  } catch {
    const error = new Error('助手暂时不可用，请确认服务已经启动。')
    error.status = response.status
    throw error
  }
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : `请求未通过校验（${response.status}）`
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  return data
}

export function createConversation(token) {
  return request('/conversations', token, { method: 'POST' })
}

export function getConversation(threadId, token) {
  return request(`/conversations/${encodeURIComponent(threadId)}/history?limit=100`, token)
}

export function sendMessage(body, token) {
  return request('/chat', token, { method: 'POST', body })
}

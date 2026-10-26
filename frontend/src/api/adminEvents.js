async function post(path, token, body) {
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/json',
  }

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`/api${path}`, {
    method: 'POST',
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`)
    error.status = response.status
    throw error
  }

  return response.json()
}

export function createDraft(data, token) {
  return post('/admin/events', token, data)
}

export function publishDraft(eventId, token) {
  return post(`/admin/events/${encodeURIComponent(eventId)}/publish`, token)
}
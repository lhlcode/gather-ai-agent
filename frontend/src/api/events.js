async function getJson(path) {
  const response = await fetch(`/api${path}`, {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return response.json()
}

export function listEvents() {
  return getJson('/events')
}

export function getEvent(id) {
  return getJson(`/events/${encodeURIComponent(id)}`)
}
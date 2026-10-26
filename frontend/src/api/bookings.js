export async function bookEvent(eventId, token) {
  const response = await fetch(
    `/api/events/${encodeURIComponent(eventId)}/bookings`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
      },
    },
  )

  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`)
    error.status = response.status
    throw error
  }

  return response.json()
}
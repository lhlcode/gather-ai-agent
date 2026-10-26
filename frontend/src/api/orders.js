async function request(path, token, method = 'GET') {
  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`)
    error.status = response.status
    throw error
  }

  return response.json()
}

export function listMyOrders(token) {
  return request('/orders', token)
}

export function payOrder(orderId, token) {
  return request(`/orders/${encodeURIComponent(orderId)}/pay`, token, 'POST')
}

export function cancelOrder(orderId, token) {
  return request(`/orders/${encodeURIComponent(orderId)}/cancel`, token, 'POST')
}
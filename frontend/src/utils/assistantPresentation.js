export function displayAnswer(response) {
  const data = response.tool_results?.find(item => Array.isArray(item.events) || Array.isArray(item.orders))
  if (data?.events) {
    const label = { not_ended: '报名未截止', open: '当前可报名', all: '已发布' }[data.event_filter] || '已发布'
    return data.events.length ? `找到 ${data.events.length} 场${label}的活动。` : `暂时没有${label}的活动。`
  }
  if (data?.orders) return data.total_count ? `你有 ${data.total_count} 笔订单，先看看最近的记录。` : '你还没有订单，去发现一场感兴趣的活动吧。'
  return response.answer
}

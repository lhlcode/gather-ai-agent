export function eventState(event, now = Date.now()) {
  const start = Date.parse(event.registrationStartAtUtc)
  const end = Date.parse(event.registrationEndAtUtc)
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) return 'unknown'
  if (now >= end) return 'ended'
  if (now < start) return 'upcoming'
  return event.availableQuota > 0 ? 'open' : 'full'
}

export const eventStateNames = {
  open: '报名中', upcoming: '即将开始', ended: '已截止', full: '名额已满', unknown: '时间待确认',
}

export function matchesEventFilter(event, filter, now = Date.now()) {
  const state = eventState(event, now)
  if (filter === 'all') return true
  if (filter === 'not_ended') return ['open', 'full', 'upcoming'].includes(state)
  if (filter === 'upcoming') return state === 'upcoming'
  return state === 'open'
}

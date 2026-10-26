import http from 'k6/http'
import { check, fail } from 'k6'
import { Counter, Trend } from 'k6/metrics'

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:9091'
const QUOTA = 300
const VUS = 50
const READS_PER_VU = 20

const readErrors = new Counter('event_read_errors')
const readDuration = new Trend('event_read_duration_ms')

export const options = {
  scenarios: {
    event_read_burst: {
      executor: 'per-vu-iterations',
      vus: VUS,
      iterations: READS_PER_VU,
      maxDuration: '2m',
    },
  },
}

export function setup() {
  if (!__ENV.LOAD_ADMIN_USERNAME || !__ENV.LOAD_TEST_PASSWORD) {
    fail('Set LOAD_ADMIN_USERNAME and LOAD_TEST_PASSWORD before running the load test')
  }
  const login = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({
      username: __ENV.LOAD_ADMIN_USERNAME,
      password: __ENV.LOAD_TEST_PASSWORD,
    }),
    { headers: { 'Content-Type': 'application/json' } }
  )
  if (login.status !== 200) {
    fail(`管理员登录失败：HTTP ${login.status} ${login.body}`)
  }

  const token = login.json().accessToken
  const now = Date.now()

  const draft = http.post(
    `${BASE}/admin/events`,
    JSON.stringify({
      title: `Redis read baseline ${now}`,
      totalQuota: QUOTA,
      registrationStartAtUtc: new Date(now - 60_000).toISOString(),
      registrationEndAtUtc: new Date(now + 60 * 60_000).toISOString(),
    }),
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    }
  )
  if (draft.status !== 201) {
    fail(`创建活动失败：HTTP ${draft.status} ${draft.body}`)
  }

  const eventId = draft.json().eventId
  const published = http.post(
    `${BASE}/admin/events/${eventId}/publish`,
    null,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  if (published.status !== 200) {
    fail(`发布活动失败：HTTP ${published.status} ${published.body}`)
  }

  console.log(`测试活动 ID：${eventId}；名额：${QUOTA}；预计详情请求：${VUS * READS_PER_VU}`)
  return { eventId }
}

export default function (data) {
  const response = http.get(`${BASE}/events/${data.eventId}`)
  readDuration.add(response.timings.duration)

  const valid =
    response.status === 200 &&
    response.json('totalQuota') === QUOTA &&
    response.json('availableQuota') === QUOTA

  if (!valid) {
    readErrors.add(1)
    console.error(`活动 ${data.eventId}：HTTP ${response.status} ${response.body}`)
  }

  check(response, {
    '返回 300 名额的活动详情': () => valid,
  })
}
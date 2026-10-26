import http from 'k6/http'
import { check, fail } from 'k6'
import { Counter, Trend } from 'k6/metrics'

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:9091'
const USERS = 50
const QUOTA = 20
const PASSWORD = __ENV.LOAD_TEST_PASSWORD

const created = new Counter('booking_created')
const conflict = new Counter('booking_conflict')
const unexpected = new Counter('booking_unexpected')
const bookingDuration = new Trend('booking_duration_ms')

export const options = {
  setupTimeout: '5m',
  scenarios: {
    booking_burst: {
      executor: 'per-vu-iterations',
      vus: USERS,
      iterations: 1,
      maxDuration: '2m',
    },
  },
}

function postJson(path, body, token) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  return http.post(`${BASE}${path}`, JSON.stringify(body), { headers })
}

export function setup() {
  if (!__ENV.LOAD_ADMIN_USERNAME || !__ENV.LOAD_TEST_PASSWORD) {
    fail('Set LOAD_ADMIN_USERNAME and LOAD_TEST_PASSWORD before running the load test')
  }
  const adminLogin = postJson('/auth/login', {
    username: __ENV.LOAD_ADMIN_USERNAME,
    password: PASSWORD,
  })
  if (adminLogin.status !== 200) {
    fail(`管理员登录失败：HTTP ${adminLogin.status}`)
  }
  const adminToken = adminLogin.json().accessToken

  const now = Date.now()
  const draft = postJson('/admin/events', {
    title: `Perf baseline ${now}`,
    totalQuota: QUOTA,
    registrationStartAtUtc: new Date(now - 60_000).toISOString(),
    registrationEndAtUtc: new Date(now + 60 * 60_000).toISOString(),
  }, adminToken)
  if (draft.status !== 201) {
    fail(`创建活动失败：HTTP ${draft.status} ${draft.body}`)
  }

  const eventId = draft.json().eventId
  const published = http.post(
    `${BASE}/admin/events/${eventId}/publish`,
    null,
    { headers: { Authorization: `Bearer ${adminToken}` } }
  )
  if (published.status !== 200) {
    fail(`发布活动失败：HTTP ${published.status}`)
  }

  const tokens = []
  for (let i = 0; i < USERS; i++) {
    const username = `perf_${now}_${i}`

    const registration = postJson('/users/register', {
      username,
      password: PASSWORD,
    })
    if (registration.status !== 201) {
      fail(`注册 ${username} 失败：HTTP ${registration.status}`)
    }

    const login = postJson('/auth/login', {
      username,
      password: PASSWORD,
    })
    if (login.status !== 200) {
      fail(`登录 ${username} 失败：HTTP ${login.status}`)
    }
    tokens.push(login.json().accessToken)
  }

  console.log(`测试活动 ID：${eventId}；名额：${QUOTA}；用户：${USERS}`)
  return { eventId, tokens }
}

export default function (data) {
  // 对这个限量活动，201 和售罄时的 409 都是预期业务结果。
  http.setResponseCallback(http.expectedStatuses(201, 409))

  const token = data.tokens[__VU - 1]
  const response = http.post(
    `${BASE}/events/${data.eventId}/bookings`,
    null,
    { headers: { Authorization: `Bearer ${token}` } }
  )

  bookingDuration.add(response.timings.duration)

  if (response.status === 201) {
    created.add(1)
  } else if (response.status === 409) {
    conflict.add(1)
  } else {
    unexpected.add(1)
    console.error(`用户 ${__VU}：HTTP ${response.status} ${response.body}`)
  }

  check(response, {
    '报名结果为 201 或 409': r => r.status === 201 || r.status === 409,
  })
}
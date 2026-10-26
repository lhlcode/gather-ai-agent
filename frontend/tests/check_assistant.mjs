import assert from 'node:assert/strict'
import { bookingPayload, bookingSettled, clearPending, parseBooking, readPending, savePending } from '../src/utils/assistantBooking.js'
import { createConversation, getConversation, sendMessage } from '../src/api/assistant.js'
import { eventState, matchesEventFilter } from '../src/utils/eventStatus.js'
import { displayAnswer } from '../src/utils/assistantPresentation.js'

const current = Date.parse('2026-10-26T08:00:00Z')
const activity = { registrationStartAtUtc: '2026-10-25T08:00:00Z', registrationEndAtUtc: '2026-10-26T08:00:00Z', availableQuota: 3 }
assert.equal(eventState(activity, current), 'ended')
assert.equal(matchesEventFilter(activity, 'not_ended', current), false)
const future = { ...activity, registrationStartAtUtc: '2026-10-27T08:00:00Z', registrationEndAtUtc: '2026-10-28T08:00:00Z' }
assert.equal(matchesEventFilter(future, 'not_ended', current), true)
assert.equal(matchesEventFilter(future, 'open', current), false)
const full = { ...activity, registrationEndAtUtc: '2026-10-28T08:00:00Z', availableQuota: 0 }
assert.equal(matchesEventFilter(full, 'not_ended', current), true)
assert.equal(matchesEventFilter(full, 'open', current), false)
assert.equal(eventState({ ...activity, registrationEndAtUtc: 'invalid' }, current), 'unknown')
assert.equal(displayAnswer({ answer: 'long list', tool_results: [{ events: [{ id: 1 }], event_filter: 'not_ended' }] }), '找到 1 场报名未截止的活动。')
assert.equal(displayAnswer({ answer: '原始回答', tool_results: [] }), '原始回答')
console.log('PASS: frontend time boundary matches backend semantics; business replies use compact summaries')

for (const text of ['帮我报名活动49', '请帮我报名活动49。', '重新报名活动49', '重试报名活动49']) assert.ok(parseBooking(text))
for (const text of ['不要报名活动49', '他说：报名活动49', '活动49能报名吗？', '报名活动0', '报名活动9223372036854775808']) assert.equal(parseBooking(text), null)
assert.equal(parseBooking('报名活动9223372036854775807').eventId, '9223372036854775807')
const thread = 'a'.repeat(32)
const first = bookingPayload(thread, '帮我报名活动49')
assert.match(first.operation_id, /^[0-9a-f]{32}$/)
assert.equal(bookingPayload(thread, '重试报名活动49', first).operation_id, first.operation_id)
assert.throws(() => bookingPayload(thread, '重试报名活动50', first))
assert.throws(() => bookingPayload(thread, '重试报名活动49'))
assert.throws(() => bookingPayload(thread, '帮我报名活动49', first))
assert.deepEqual(bookingPayload(thread, '活动49能报名吗？'), { thread_id: thread, message: '活动49能报名吗？' })

const data = new Map()
const storage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) }
savePending(storage, 7, { ...first, token: 'must-not-persist' })
assert.deepEqual(readPending(storage, 7), first)
assert.equal(readPending(storage, 8), null)
assert.ok(![...data.values()].join('').includes('must-not-persist'))
assert.equal(bookingSettled({ status: 'unknown', tool_results: [{ status: 'unknown', operation_id: first.operation_id }] }, first), false)
assert.equal(bookingSettled({ status: 'answered', tool_results: [{ status: 'replayed', operation_id: first.operation_id }] }, first), true)
assert.equal(bookingSettled({ status: 'answered', tool_results: [{ status: 'created', operation_id: 'b'.repeat(32) }] }, first), false)
assert.equal(bookingSettled({ status: 'clarify' }, first), true)
assert.throws(() => savePending(null, 7, first), /尚未提交/)
clearPending(storage, 7)
assert.equal(readPending(storage, 7), null)
storage.setItem('ticket-assistant:pending:7', '{bad json')
assert.equal(readPending(storage, 7), null)
console.log('PASS: raw command parsing, exact integer IDs, stable retry, pending recovery, user isolation, no token storage')

const originalFetch = globalThis.fetch
const calls = []
try {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return new Response(JSON.stringify({ thread_id: thread }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
  await createConversation('test-token')
  await getConversation(thread, 'test-token')
  await sendMessage(first, 'test-token')
  assert.equal(calls[0].url, '/ai/conversations')
  assert.equal(calls[1].url, `/ai/conversations/${thread}/history?limit=100`)
  assert.equal(calls[2].options.headers.Authorization, 'Bearer test-token')
  assert.deepEqual(JSON.parse(calls[2].options.body), first)
  assert.equal(calls.length, 3)
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: '会话不可访问' }), { status: 404 })
  await assert.rejects(() => sendMessage(first, 'test-token'), error => error.status === 404 && error.message === '会话不可访问')
  globalThis.fetch = async () => new Response('<html>unavailable</html>', { status: 502 })
  await assert.rejects(() => sendMessage(first, 'test-token'), error => error.status === 502)
  let failures = 0
  globalThis.fetch = async () => { failures++; throw new TypeError('network') }
  await assert.rejects(() => sendMessage(first, 'test-token'), /原编号/)
  assert.equal(failures, 1)
} finally { globalThis.fetch = originalFetch }
console.log('PASS: API path, per-request bearer, body preservation, HTTP/invalid JSON/network failure; no automatic retry')

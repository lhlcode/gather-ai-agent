<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import BusinessResults from './BusinessResults.vue'
import { displayAnswer } from '../utils/assistantPresentation'
import { createConversation, getConversation, sendMessage } from '../api/assistant'
import { bookingPayload, bookingSettled, clearPending, readPending, savePending } from '../utils/assistantBooking'

const props = defineProps({
  token: { type: String, required: true },
  userId: { type: Number, required: true },
})
const emit = defineEmits(['unauthorized', 'changed', 'open-event', 'open-orders'])
const threadId = ref('')
const restoreId = ref('')
const message = ref('')
const entries = ref([])
const busy = ref(false)
const error = ref('')
const pending = ref(null)
const failed = ref(null)
const transcript = ref(null)
const sessionOpen = ref(false)
const input = ref(null)
let active = true
let serial = 0
let storage
try { storage = window.sessionStorage } catch { storage = null }

const statusNames = {
  answered: '已返回', insufficient: '资料不足', blocked: '未通过核验',
  clarify: '需要补充信息', partial: '部分回答', unknown: '结果待确认',
}

async function scrollToLatest() {
  await nextTick()
  if (active && transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight
}

function handleError(cause) {
  if (!active) return
  error.value = cause.message
  if (cause.status === 401) emit('unauthorized')
}

async function newConversation() {
  if (busy.value || pending.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await createConversation(props.token)
    if (!active) return
    threadId.value = result.thread_id
    restoreId.value = result.thread_id
    entries.value = []
    failed.value = null
  } catch (cause) { handleError(cause) }
  finally { if (active) busy.value = false }
}

async function restoreConversation() {
  if (busy.value) return
  const id = restoreId.value.trim()
  if (!/^[0-9a-f]{32}$/u.test(id)) { error.value = '请输入完整的会话编号。'; return }
  if (pending.value && pending.value.thread_id !== id) { error.value = '请先处理当前待确认报名。'; return }
  busy.value = true
  error.value = ''
  try {
    const result = await getConversation(id, props.token)
    if (!active) return
    threadId.value = id
    entries.value = result.turns.map(turn => ({
      id: `saved-${turn.turn_id}`, message: turn.user_message, response: turn.response,
    }))
    failed.value = null
    await scrollToLatest()
  } catch (cause) { handleError(cause) }
  finally { if (active) busy.value = false }
}

async function submit(original = null) {
  if (busy.value || !active) return
  const text = original ? original.message : message.value.trim()
  if (!text || text.length > 2000) { error.value = '请输入 1～2000 个字符。'; return }
  busy.value = true
  error.value = ''
  let entry
  let payload
  try {
    if (!threadId.value) {
      const result = await createConversation(props.token)
      if (!active) return
      threadId.value = result.thread_id
      restoreId.value = result.thread_id
    }
    payload = original || bookingPayload(threadId.value, text, pending.value)
    if (payload.operation_id) {
      // 先可靠保存，再发送；网络错误和页面刷新均复用原编号。
      savePending(storage, props.userId, payload)
      pending.value = { ...payload }
    }
    entry = { id: `local-${++serial}`, message: text, response: null }
    entries.value.push(entry)
    const position = entries.value.length - 1
    if (!original) message.value = ''
    await scrollToLatest()
    const result = await sendMessage(payload, props.token)
    if (!active) return
    entries.value[position].response = result
    failed.value = null
    if (payload.operation_id && bookingSettled(result, payload)) {
      try { clearPending(storage, props.userId) } catch { /* 旧编号重放仍然安全。 */ }
      pending.value = null
    }
    if (result.tool_results?.some(item => ['created', 'replayed'].includes(item.status))) emit('changed')
  } catch (cause) {
    if (!active) return
    if (entry) failed.value = { ...payload }
    handleError(cause)
  } finally {
    if (active) { busy.value = false; await scrollToLatest() }
  }
}

function retry() {
  const payload = pending.value || failed.value
  if (payload) submit({ ...payload })
}

function example(text) { message.value = text; nextTick(() => input.value?.focus()) }
function onComposerKey(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit() }
}

onMounted(() => {
  pending.value = readPending(storage, props.userId)
  if (pending.value) {
    threadId.value = pending.value.thread_id
    restoreId.value = pending.value.thread_id
    restoreConversation()
  }
})
onUnmounted(() => { active = false })
</script>
<template>
  <section id="assistant" :class="['assistant-panel', { 'has-messages': entries.length }]" aria-labelledby="assistant-title">
    <header class="assistant-heading">
      <div class="assistant-identity"><span class="assistant-logo"><AppIcon name="spark" :size="23" /></span><div><h2 id="assistant-title">小约</h2><p>你的活动与报名助手</p></div></div>
      <div class="assistant-head-actions"><button type="button" class="icon-button" :aria-expanded="sessionOpen" aria-label="会话管理" @click="sessionOpen = !sessionOpen"><AppIcon name="clock" :size="18" /></button><button type="button" class="new-chat-button" :disabled="busy || !!pending" @click="newConversation"><AppIcon name="plus" :size="16" /> 新会话</button></div>
    </header>
    <div v-if="sessionOpen" class="assistant-session">
      <div class="session-top"><strong>恢复之前的对话</strong><button type="button" class="icon-button" aria-label="关闭会话管理" @click="sessionOpen = false"><AppIcon name="close" :size="16" /></button></div><p>当前会话 <code>{{ threadId || '发送消息后创建' }}</code></p><p v-if="pending">待确认报名 <code>{{ pending.operation_id }}</code></p><div class="session-restore"><input v-model.trim="restoreId" :disabled="busy" aria-label="已有会话编号" placeholder="粘贴已有会话编号" autocomplete="off" maxlength="32"><button type="button" :disabled="busy || !restoreId" @click="restoreConversation">恢复会话</button></div><small>仅能恢复本人会话，显示最近 100 轮。</small>
    </div>
    <div ref="transcript" class="assistant-transcript" aria-live="polite" aria-relevant="additions text" :aria-busy="busy">
      <div v-if="!entries.length" class="assistant-welcome"><span class="welcome-orb"><AppIcon name="spark" :size="38" /></span><span class="eyebrow">A LITTLE HELP, A BETTER PLAN</span><h3>每一次期待，<br>从一句话开始。</h3><p>我是小约。发现活动、了解规则，<br>或看看你的订单，我都可以帮你。</p><div class="suggestion-grid"><button type="button" :disabled="busy" @click="example('没过期的活动发出来')"><AppIcon name="calendar" /><span>看看未截止的活动<small>找一场值得期待的相聚</small></span><AppIcon name="arrow" :size="16" /></button><button type="button" :disabled="busy" @click="example('查看我的订单')"><AppIcon name="ticket" /><span>我的报名到哪了？<small>查看订单和当前状态</small></span><AppIcon name="arrow" :size="16" /></button><button type="button" :disabled="busy" @click="example('待支付订单超过付款时间会怎样？')"><AppIcon name="clock" /><span>还没付款怎么办？<small>了解支付期限和规则</small></span><AppIcon name="arrow" :size="16" /></button><button type="button" :disabled="busy" @click="example('已支付的订单可以取消吗？')"><AppIcon name="spark" /><span>关于取消，我想问…<small>弄清不同订单的规则</small></span><AppIcon name="arrow" :size="16" /></button></div></div>
      <article v-for="entry in entries" :key="entry.id" class="assistant-turn">
        <div class="user-row"><p class="assistant-user">{{ entry.message }}</p><span class="user-bubble-avatar"><AppIcon name="user" :size="16" /></span></div>
        <div class="assistant-answer-row"><span class="answer-avatar"><AppIcon name="spark" :size="18" /></span><div v-if="entry.response" class="assistant-reply"><span v-if="entry.response.status !== 'answered'" class="assistant-status">{{ statusNames[entry.response.status] || '已返回' }}</span><p>{{ displayAnswer(entry.response) }}</p><BusinessResults :response="entry.response" @open-event="emit('open-event', $event)" @open-orders="emit('open-orders')" /><details v-if="entry.response.claims?.length" class="assistant-evidence"><summary>依据与引用 · {{ entry.response.claims.length }} 条</summary><div v-for="(claim, index) in entry.response.claims" :key="index"><p>{{ claim.text }}</p><blockquote v-for="(evidence, number) in claim.evidence" :key="number">[{{ evidence.chunk_id }}] {{ evidence.quote }}</blockquote></div></details></div><p v-else class="assistant-wait">{{ busy ? '小约正在整理信息' : '没有收到完整答复，可以重试。' }}<span v-if="busy" class="typing-dots">···</span></p></div>
      </article>
    </div>
    <div class="assistant-bottom">
      <div v-if="pending || failed || error" class="assistant-notice"><p v-if="pending">有一笔报名结果待确认，请用原编号重试。刷新后重新登录同一账号，也可继续处理。</p><p v-if="error" role="alert">{{ error }}</p><button v-if="pending || failed" type="button" :disabled="busy" @click="retry">{{ pending ? '用原编号重试报名' : '重试原请求' }} <AppIcon name="refresh" :size="14" /></button></div>
      <form class="assistant-form" @submit.prevent="submit()"><label class="sr-only" for="assistant-message">发送消息</label><textarea id="assistant-message" ref="input" v-model="message" rows="2" maxlength="2000" :disabled="busy" placeholder="想参加什么活动？或者，问问报名规则…" required @keydown="onComposerKey" /><div class="composer-actions"><span><AppIcon name="spark" :size="14" /> 小约，帮你把期待安排好</span><button class="send-button" type="submit" aria-label="发送" :disabled="busy || !message.trim()"><AppIcon name="send" :size="20" /></button></div></form><p class="composer-footnote">活动与名额以实际查询为准 · 支付和取消请前往“我的订单”</p>
    </div>
  </section>
</template>

<style scoped>
.assistant-panel { display: flex; flex-direction: column; height: calc(100dvh - 218px); min-height: 640px; border: 1px solid #e4e5ed; border-radius: 22px; background: #fff; overflow: hidden; box-shadow: 0 12px 40px #25224505; }
.assistant-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 20px 26px; border-bottom: 1px solid #f0f0f5; }
.assistant-identity, .assistant-head-actions { display: flex; gap: 12px; align-items: center; }
.assistant-logo { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 15px; color: #fff; background: linear-gradient(135deg, #7d73ed, #5d55ca); box-shadow: 0 4px 12px #6659df24; }
.assistant-identity h2 { margin: 0; font-size: 16px; }.assistant-identity p { margin: 4px 0 0; font-size: 11px; color: #90909f; }
.new-chat-button { display: flex; align-items: center; gap: 6px; border-color: #e5e5ef; font-size: 12px; padding: 8px 11px; }
.assistant-session { margin: 14px 24px 0; padding: 14px 16px; border: 1px solid #e5e3f5; border-radius: 12px; background: #faf9ff; font-size: 12px; }
.session-top { display: flex; align-items: center; justify-content: space-between; }.assistant-session p { color: #777589; overflow-wrap: anywhere; }.assistant-session code { font-size: 11px; }.session-restore { display: flex; gap: 8px; }.session-restore input { flex: 1; min-width: 0; padding: 9px; border: 1px solid #e1deee; border-radius: 8px; }.assistant-session small { display: block; margin-top: 10px; color: #8e8c9e; }
.assistant-transcript { flex: 1; min-height: 0; overflow: auto; padding: 30px clamp(20px, 5vw, 70px); scroll-behavior: smooth; }
.assistant-welcome { max-width: 660px; margin: 16px auto 20px; text-align: center; }.welcome-orb { display: grid; place-items: center; width: 78px; height: 78px; margin: 0 auto 24px; border-radius: 26px; color: #6b5edb; background: radial-gradient(circle at 25% 20%, #f6f0ff, #e9e6fc); transform: rotate(-6deg); }.welcome-orb svg { transform: rotate(6deg); }.assistant-welcome .eyebrow { font-size: 9px; letter-spacing: .15em; color: #9f98ba; }.assistant-welcome h3 { margin: 14px 0; font-size: clamp(25px, 3vw, 34px); line-height: 1.5; font-weight: 650; letter-spacing: -.04em; }.assistant-welcome > p { font-size: 13px; color: #9593a3; line-height: 1.9; }
.suggestion-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 30px; }.suggestion-grid button { display: flex; gap: 12px; align-items: center; text-align: left; padding: 15px; border-color: #ecebf2; border-radius: 12px; color: #7c73aa; background: #fff; }.suggestion-grid button:hover { background: #f9f7ff; border-color: #d8d0f3; }.suggestion-grid button > span { flex: 1; color: #444153; font-size: 12px; }.suggestion-grid small { display: block; color: #a19dad; font-size: 10px; margin-top: 5px; }
.assistant-turn { margin-bottom: 32px; }.user-row { display: flex; align-items: flex-start; justify-content: flex-end; gap: 10px; margin-bottom: 24px; }.assistant-user { max-width: 82%; margin: 0; padding: 12px 17px; border-radius: 16px 4px 16px 16px; background: #f0edfc; color: #51477b; font-size: 14px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }.user-bubble-avatar, .answer-avatar { flex-shrink: 0; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 11px; background: #f2f1f7; color: #9690a7; }.answer-avatar { color: #7464da; background: #eeebfb; }.assistant-answer-row { display: flex; align-items: flex-start; gap: 12px; }.assistant-reply { min-width: 0; flex: 1; }.assistant-reply > p { font-size: 14px; line-height: 1.9; white-space: pre-wrap; margin: 2px 0 12px; overflow-wrap: anywhere; }.assistant-status { display: inline-block; padding: 3px 8px; margin-bottom: 8px; font-size: 11px; border-radius: 5px; color: #946d37; background: #fff5e5; }.assistant-wait { color: #a4a0b1; margin: 5px 0; font-size: 13px; }.typing-dots { margin-left: 8px; letter-spacing: 3px; }
.assistant-evidence { margin-top: 14px; font-size: 12px; color: #8a849a; }.assistant-evidence summary { cursor: pointer; }.assistant-evidence blockquote { margin: 8px 0; padding: 9px 12px; border-left: 2px solid #d7cfee; background: #faf9fd; line-height: 1.8; color: #777183; }
.assistant-bottom { padding: 0 clamp(18px, 4vw, 55px) 16px; }.assistant-form { border: 1px solid #e1ddeb; border-radius: 16px; background: #fff; padding: 14px 16px 10px; box-shadow: 0 4px 18px #50407705; }.assistant-form:focus-within { border-color: #b5a4e8; box-shadow: 0 0 0 3px #f3effc; }.assistant-form textarea { width: 100%; min-height: 50px; max-height: 150px; resize: vertical; padding: 0; border: 0; background: transparent; font: inherit; font-size: 13px; line-height: 1.7; outline: none; color: #383449; }.assistant-form textarea::placeholder { color: #b0aabd; }.composer-actions { display: flex; justify-content: space-between; align-items: center; }.composer-actions > span { display: flex; gap: 6px; align-items: center; color: #b3acbf; font-size: 10px; }.send-button { width: 34px; height: 34px; display: grid; place-items: center; padding: 0; color: #fff; background: #7863d9; border: 0; border-radius: 10px; }.send-button:hover:not(:disabled) { background: #6850c7; }.send-button:disabled { opacity: .35; }.composer-footnote { text-align: center; color: #b7b1c2; font-size: 10px; margin: 10px 0 0; }
.assistant-notice { margin-bottom: 10px; border-radius: 10px; padding: 10px 13px; background: #fff8ed; font-size: 12px; color: #947446; }.assistant-notice p { margin: 0 0 5px; line-height: 1.7; }.assistant-notice [role=alert] { padding: 0; background: transparent; }.assistant-notice button { display: inline-flex; align-items: center; gap: 5px; margin-top: 4px; font-size: 11px; padding: 5px 9px; }
@media (max-width: 680px) { .assistant-panel { min-height: 600px; height: calc(100dvh - 190px); border-radius: 16px; }.assistant-heading { padding: 14px 16px; }.assistant-transcript { padding: 22px 16px; }.assistant-welcome { margin-top: 6px; }.welcome-orb { width: 60px; height: 60px; margin-bottom: 18px; border-radius: 21px; }.suggestion-grid { gap: 8px; margin-top: 22px; }.suggestion-grid button { padding: 12px 10px; gap: 8px; }.suggestion-grid button > svg:last-child { display: none; }.suggestion-grid small { line-height: 1.6; }.assistant-bottom { padding: 0 12px 12px; }.composer-actions > span { font-size: 9px; }.composer-footnote { font-size: 9px; }.new-chat-button { font-size: 11px; padding: 7px 9px; }.assistant-head-actions { gap: 5px; } }
</style>

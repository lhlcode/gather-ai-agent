<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import AdminEventsPanel from './components/AdminEventsPanel.vue'
import AssistantPanel from './components/AssistantPanel.vue'
import AppIcon from './components/AppIcon.vue'
import { eventState, eventStateNames, matchesEventFilter } from './utils/eventStatus'
import { bookEvent } from './api/bookings'
import { getEvent, listEvents } from './api/events'
import { formatBeijing } from './utils/time'
import OrdersPanel from './components/OrdersPanel.vue'
import { getMe, login, register } from './api/auth'


const activeView = ref('events')
const showLogin = ref(false)
const search = ref('')
const eventFilter = ref('not_ended')
const visibleCount = ref(6)
const now = ref(Date.now())
let clockTimer
const views = [
  { id: 'events', label: '活动广场', icon: 'grid', caption: '发现值得奔赴的相聚' },
  { id: 'assistant', label: 'AI 助手', icon: 'spark', caption: '关于活动，问一句就好' },
  { id: 'orders', label: '我的订单', icon: 'ticket', caption: '每一次期待，都有记录' },
]
const currentView = computed(() => views.find(view => view.id === activeView.value) || { label: '活动管理', caption: '让一场新的相聚发生' })
const availableCount = computed(() => events.value.filter(event => matchesEventFilter(event, 'not_ended', now.value)).length)
const filteredEvents = computed(() => events.value.filter(event =>
  matchesEventFilter(event, eventFilter.value, now.value) &&
  (event.title + ' ' + event.id).toLowerCase().includes(search.value.toLowerCase().trim())
))
const visibleEvents = computed(() => filteredEvents.value.slice(0, visibleCount.value))
const filters = [
  { id: 'not_ended', label: '未截止' }, { id: 'open', label: '报名中' },
  { id: 'upcoming', label: '即将开始' }, { id: 'all', label: '全部活动' },
]
function stateOf(event) { return eventState(event, now.value) }
function go(view) {
  activeView.value = view
  if (view === 'orders' && !accessToken.value) showLogin.value = true
}
function openAssistant() { go('assistant') }
watch([search, eventFilter], () => { visibleCount.value = 6 })

const events = ref([])
const selected = ref(null)
const loading = ref(false)
const loadingDetail = ref(false)
const error = ref('')
const detailError = ref('')

const username = ref('')
const password = ref('')
const accessToken = ref('')
const currentUsername = ref('')
const currentRole = ref('')
const currentUserId = ref(null)
const authMessage = ref('')
const authBusy = ref(false)
const authMode = ref('login')
const confirmPassword = ref('')

const bookingBusy = ref(false)
const bookingMessage = ref('')
const ordersVersion = ref(0)
let detailSerial = 0

function closeDetail() {
  detailSerial += 1
  selected.value = null
  loadingDetail.value = false
  detailError.value = ''
}

async function loadEvents() {
  loading.value = true
  error.value = ''

  try {
    events.value = await listEvents()
  } catch (cause) {
    error.value = `活动加载失败：${cause.message}`
  } finally {
    loading.value = false
  }
}

async function openEvent(id) {
  const request = ++detailSerial
  selected.value = null
  detailError.value = ''
  bookingMessage.value = ''
  loadingDetail.value = true

  try {
    const event = await getEvent(id)
    if (request === detailSerial) selected.value = event
  } catch (cause) {
    if (request === detailSerial) detailError.value = `详情加载失败：${cause.message}`
  } finally {
    if (request === detailSerial) loadingDetail.value = false
  }
}

async function submitLogin() {
  authBusy.value = true
  authMessage.value = ''

  try {
    const name = username.value.trim()
    const result = await login(name, password.value)
    const me = await getMe(result.accessToken)

    accessToken.value = result.accessToken
    currentUsername.value = me.username
    currentRole.value = me.role
    currentUserId.value = me.userId
    password.value = ''
    authMessage.value = '登录成功'
    showLogin.value = false
  } catch (cause) {
    authMessage.value =
      cause.status === 401
        ? '用户名或密码错误，或身份信息读取失败'
        : `登录失败：${cause.message}`
  } finally {
    authBusy.value = false
  }
}

function switchAuthMode() {
  authMode.value = authMode.value === 'login' ? 'register' : 'login'
  authMessage.value = ''
  password.value = ''
  confirmPassword.value = ''
}

async function submitRegister() {
  const name = username.value.trim()

  if (!/^[A-Za-z0-9_]{3,32}$/.test(name)) {
    authMessage.value = '用户名需为 3～32 位英文字母、数字或下划线'
    return
  }
  if (password.value.length < 8 || password.value.length > 64) {
    authMessage.value = '密码需为 8～64 位'
    return
  }
  if (password.value !== confirmPassword.value) {
    authMessage.value = '两次输入的密码不一致'
    return
  }

  authBusy.value = true
  authMessage.value = ''

  try {
    await register(name, password.value)
    username.value = name
    password.value = ''
    confirmPassword.value = ''
    authMode.value = 'login'
    authMessage.value = '注册成功，请输入密码登录'
  } catch (cause) {
    authMessage.value =
      cause.status === 409
        ? '用户名已被使用'
        : cause.status === 400
          ? '用户名或密码格式不符合要求'
          : `注册失败：${cause.message}`
  } finally {
    authBusy.value = false
  }
}
function logout() {
  currentUserId.value = null
  currentRole.value = ''
  accessToken.value = ''
  currentUsername.value = ''
  password.value = ''
  authMessage.value = '已退出登录'
  bookingMessage.value = ''
}

async function submitBooking() {
  if (!selected.value || !accessToken.value) return

  const eventId = selected.value.id
  bookingBusy.value = true
  bookingMessage.value = ''

  try {
    const order = await bookEvent(eventId, accessToken.value)
    bookingMessage.value =
      `报名成功！订单号 ${order.orderId}，状态 ${order.status}。请在 15 分钟内支付。`
      ordersVersion.value += 1

    // 报名已成功；随后刷新名额。刷新失败不能误报为“报名失败”。
    try {
      events.value = await listEvents()
      selected.value = await getEvent(eventId)
    } catch (cause) {
      detailError.value = `报名已成功，但刷新名额失败：${cause.message}`
    }
  } catch (cause) {
    if (cause.status === 401) {
      logout()
      bookingMessage.value = '登录已过期，请重新登录'
    } else if (cause.status === 409) {
      bookingMessage.value = '报名未成功：已有有效订单，或活动当前不可报名'
    } else {
      bookingMessage.value = `报名失败：${cause.message}`
    }
  } finally {
    bookingBusy.value = false
  }
}
function handleUnauthorized() {
  logout()
  authMessage.value = '登录已过期，请重新登录'
}

function handleAssistantChanged() {
  ordersVersion.value += 1
  refreshEventViews()
}

async function refreshEventViews() {
  await loadEvents()

  if (selected.value) {
    try {
      selected.value = await getEvent(selected.value.id)
      detailError.value = ''
    } catch (cause) {
      detailError.value = `活动刷新失败：${cause.message}`
    }
  }
}
onMounted(() => {
  loadEvents()
  clockTimer = window.setInterval(() => { now.value = Date.now() }, 30000)
})
onUnmounted(() => window.clearInterval(clockTimer))
</script>
<template>
  <div class="workspace">
    <aside class="app-rail">
      <button class="brand" type="button" @click="go('events')"><span class="brand-mark"><AppIcon name="ticket" :size="25" /></span><span><strong>赴约</strong><small>GATHER SOMETHING GOOD</small></span></button>
      <span class="nav-caption">你的活动空间</span>
      <nav aria-label="主导航">
        <button v-for="view in views" :key="view.id" type="button" :class="['nav-item', { active: activeView === view.id }]" :aria-current="activeView === view.id ? 'page' : undefined" @click="go(view.id)">
          <AppIcon :name="view.icon" /><span>{{ view.label }}</span><span v-if="view.id === 'events'" class="nav-count">{{ availableCount }}</span>
        </button>
        <button v-if="currentRole === 'ADMIN'" type="button" :class="['nav-item', { active: activeView === 'admin' }]" @click="go('admin')"><AppIcon name="plus" /><span>活动管理</span></button>
      </nav>
      <div class="rail-bottom">
        <div class="rail-note"><span class="note-icon"><AppIcon name="spark" /></span><strong>让期待更简单</strong><p>查活动、问规则，<br>把琐事交给小约。</p><button type="button" @click="openAssistant">和小约聊聊 <AppIcon name="arrow" :size="15" /></button></div>
        <div v-if="accessToken" class="rail-account"><span class="avatar">{{ currentUsername.slice(0, 1).toUpperCase() }}</span><span><strong>{{ currentUsername }}</strong><small>{{ currentRole === 'ADMIN' ? '管理员' : '已登录' }}</small></span><button type="button" class="icon-button" aria-label="退出登录" @click="logout"><AppIcon name="exit" :size="18" /></button></div>
        <button v-else class="rail-login" type="button" @click="showLogin = true"><AppIcon name="user" :size="18" /> 登录你的账户 <AppIcon name="arrow" :size="16" /></button>
      </div>
    </aside>

    <main class="main-workspace">
      <header class="workspace-header">
        <div class="breadcrumb">我的空间 <span>/</span> <strong>{{ currentView.label }}</strong></div>
        <div class="header-actions"><span class="timezone"><i /> 北京时间</span><button type="button" class="icon-button" :disabled="loading" aria-label="刷新活动" @click="loadEvents"><AppIcon name="refresh" :size="18" /></button><button v-if="!accessToken" class="small-primary" type="button" @click="showLogin = true">登录 / 注册</button><span v-else class="header-user">{{ currentUsername }}</span><button v-if="accessToken" type="button" class="icon-button mobile-logout" aria-label="退出登录" @click="logout"><AppIcon name="exit" :size="17" /></button></div>
      </header>

      <section class="page-intro"><div><p class="eyebrow">MAKE ROOM FOR GOOD MOMENTS</p><h1>{{ currentView.label }}<span class="title-dot">.</span></h1><p>{{ currentView.caption }}</p></div><button v-if="activeView === 'events'" type="button" class="quiet-button" @click="openAssistant"><AppIcon name="spark" :size="17" /> 不知道选什么？问问小约</button></section>

      <div v-show="activeView === 'events'" class="events-view">
        <section class="discovery-banner"><div><span class="banner-tag">下一场精彩，就在这里</span><h2>为喜欢的事，<br>留一个位置。</h2><p>发现活动，轻松报名。让每一次出发都有期待。</p><button type="button" @click="openAssistant">让小约帮我找 <AppIcon name="arrow" :size="17" /></button></div><div class="banner-art" aria-hidden="true"><div class="orbit orbit-one" /><div class="orbit orbit-two" /><div class="floating-ticket"><AppIcon name="ticket" :size="68" /><span>SEE YOU THERE</span></div><span class="art-star">✦</span><span class="art-dot" /></div></section>
        <div class="event-tools"><div class="filter-tabs" aria-label="活动筛选"><button v-for="filter in filters" :key="filter.id" type="button" :class="{ selected: eventFilter === filter.id }" :aria-pressed="eventFilter === filter.id" @click="eventFilter = filter.id">{{ filter.label }}</button></div><label class="search-box"><AppIcon name="search" :size="17" /><input v-model="search" type="search" aria-label="搜索活动" placeholder="搜索活动名称或编号"></label></div>
        <div class="list-caption"><span>找到 {{ filteredEvents.length }} 场活动</span><small>报名状态会随时间更新</small></div>
        <p v-if="loading" class="empty-state">正在为你寻找活动…</p><p v-else-if="error" role="alert">{{ error }}</p>
        <div v-else-if="!filteredEvents.length" class="empty-state"><AppIcon name="calendar" :size="34" /><h3>暂时没有符合条件的活动</h3><p>换个筛选，或让小约帮你看看。</p><button type="button" @click="eventFilter = 'all'; search = ''">查看全部活动</button></div>
        <div v-else class="event-grid">
          <article v-for="(event, index) in visibleEvents" :key="event.id" class="event-card">
            <button type="button" :class="['event-cover', 'tone-' + (index % 3)]" :aria-label="'查看' + event.title" @click="openEvent(event.id)"><span :class="['state-pill', stateOf(event)]"><i /> {{ eventStateNames[stateOf(event)] }}</span><AppIcon name="ticket" :size="70" /><span class="cover-word">GATHER / {{ String(event.id).padStart(3, '0') }}</span><span class="cover-ring" /></button>
            <div class="event-card-body"><span class="event-number">活动 #{{ event.id }}</span><button class="event-title" type="button" :title="event.title" @click="openEvent(event.id)">{{ event.title }}</button><p class="event-time"><AppIcon name="clock" :size="15" /> {{ formatBeijing(event.registrationStartAtUtc) }}</p><div class="event-card-footer"><span><strong>{{ event.availableQuota }}</strong> 个剩余名额</span><button type="button" class="event-link" @click="openEvent(event.id)">查看活动 <AppIcon name="arrow" :size="16" /></button></div></div>
          </article>
        </div>
        <button v-if="visibleCount < filteredEvents.length" type="button" class="load-more" @click="visibleCount += 6">再看看更多活动 <span>+{{ Math.min(6, filteredEvents.length - visibleCount) }}</span></button>
      </div>

      <div v-show="activeView === 'assistant'" class="assistant-view">
        <AssistantPanel v-if="accessToken && currentUserId" :key="currentUserId" :token="accessToken" :user-id="currentUserId" @unauthorized="handleUnauthorized" @changed="handleAssistantChanged" @open-event="openEvent" @open-orders="go('orders')" />
        <div v-else class="login-invitation"><span class="invitation-icon"><AppIcon name="spark" :size="38" /></span><h2>你好，我是小约。</h2><p>活动怎么选，订单怎么查？<br>登录后，我们慢慢聊。</p><button class="primary-button" type="button" @click="showLogin = true">登录，开始对话 <AppIcon name="arrow" :size="17" /></button><div class="invitation-tags"><span>活动查询</span><span>规则解答</span><span>报名协助</span></div></div>
      </div>

      <div v-if="activeView === 'orders'" class="orders-view"><OrdersPanel v-if="accessToken" :key="currentUserId" :token="accessToken" :refresh-version="ordersVersion" @unauthorized="handleUnauthorized" @changed="refreshEventViews" /><div v-else class="empty-state"><AppIcon name="ticket" :size="34" /><h3>把每一次期待，收在这里</h3><p>登录后查看你的报名和订单。</p><button class="primary-button" type="button" @click="showLogin = true">登录账户</button></div></div>
      <AdminEventsPanel v-if="activeView === 'admin' && accessToken && currentRole === 'ADMIN'" :token="accessToken" @unauthorized="handleUnauthorized" @published="loadEvents" />
      <footer class="page-footer"><span>赴约 · 每一次相聚，都值得期待</span><span>本项目使用模拟支付</span></footer>
    </main>

    <div v-if="selected || loadingDetail || detailError" class="modal-backdrop" @click.self="closeDetail">
      <section class="event-dialog" role="dialog" aria-modal="true" aria-labelledby="event-dialog-title" @keydown.esc="closeDetail">
        <button type="button" class="dialog-close icon-button" aria-label="关闭活动详情" @click="closeDetail"><AppIcon name="close" /></button>
        <span class="eyebrow">YOUR NEXT GATHERING</span><p v-if="loadingDetail">正在打开活动…</p>
        <template v-if="selected"><span :class="['state-pill', stateOf(selected)]">{{ eventStateNames[stateOf(selected)] }}</span><h2 id="event-dialog-title">{{ selected.title }}</h2><p class="event-number">活动 #{{ selected.id }}</p><div class="dialog-quota"><strong>{{ selected.availableQuota }}</strong><span>/ {{ selected.totalQuota }} 个名额</span></div><div class="dialog-dates"><p><span>报名开始</span>{{ formatBeijing(selected.registrationStartAtUtc) }}</p><p><span>报名截止</span>{{ formatBeijing(selected.registrationEndAtUtc) }}</p></div><p class="dialog-note">报名成功后，请在 15 分钟内完成支付。</p><button v-if="!accessToken" type="button" class="primary-button" @click="showLogin = true">登录后报名</button><button v-else type="button" class="primary-button" :disabled="bookingBusy || stateOf(selected) !== 'open'" @click="submitBooking">{{ bookingBusy ? '正在报名…' : stateOf(selected) === 'open' ? '立即报名' : eventStateNames[stateOf(selected)] }}</button></template>
        <p v-if="detailError" role="alert">{{ detailError }}</p><p v-if="bookingMessage" class="feedback" role="status">{{ bookingMessage }}</p>
      </section>
    </div>

    <div v-if="showLogin" class="modal-backdrop auth-backdrop" @click.self="showLogin = false">
      <section class="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title" @keydown.esc="showLogin = false">
        <button type="button" class="dialog-close icon-button" aria-label="关闭登录窗口" @click="showLogin = false"><AppIcon name="close" /></button><span class="auth-brand"><AppIcon name="ticket" :size="28" /></span><span class="eyebrow">GOOD TO SEE YOU</span><h2 id="auth-title">{{ authMode === 'login' ? '欢迎回来' : '开始你的下一次相聚' }}</h2><p>{{ authMode === 'login' ? '登录赴约，把期待安排好。' : '创建账户，发现值得期待的活动。' }}</p>
        <form v-if="authMode === 'login'" class="login-form" @submit.prevent="submitLogin"><label>用户名<input v-model.trim="username" autocomplete="username" required placeholder="输入用户名"></label><label>密码<input v-model="password" type="password" autocomplete="current-password" required placeholder="输入密码"></label><button type="submit" class="primary-button" :disabled="authBusy">{{ authBusy ? '登录中…' : '登录' }}<AppIcon name="arrow" :size="17" /></button></form>
        <form v-else class="login-form" @submit.prevent="submitRegister"><label>用户名<input v-model.trim="username" autocomplete="username" pattern="[A-Za-z0-9_]{3,32}" required placeholder="3～32 位字母、数字或下划线"></label><label>密码<input v-model="password" type="password" autocomplete="new-password" minlength="8" maxlength="64" required placeholder="8～64 位密码"></label><label>确认密码<input v-model="confirmPassword" type="password" autocomplete="new-password" required placeholder="再次输入密码"></label><button type="submit" class="primary-button" :disabled="authBusy">{{ authBusy ? '注册中…' : '注册' }}</button></form>
        <p v-if="authMessage" class="feedback" role="status">{{ authMessage }}</p><button type="button" class="switch-auth" :disabled="authBusy" @click="switchAuthMode">{{ authMode === 'login' ? '还没有账户？立即注册' : '已有账户？返回登录' }}</button>
      </section>
    </div>
  </div>
</template>

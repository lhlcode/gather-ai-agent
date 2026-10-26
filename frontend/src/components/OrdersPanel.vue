<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { cancelOrder, listMyOrders, payOrder } from '../api/orders'
import { formatBeijing } from '../utils/time'

const props = defineProps({
  token: { type: String, required: true },
  refreshVersion: { type: Number, default: 0 },
})

const emit = defineEmits(['unauthorized', 'changed'])

const orders = ref([])
const loading = ref(false)
const error = ref('')
const actionMessage = ref('')
const busyOrderId = ref(null)
const filter = ref('all')
const visibleCount = ref(6)
const filtered = computed(() => orders.value.filter(order => filter.value === 'all' || (filter.value === 'closed' ? ['CANCELLED', 'EXPIRED'].includes(order.status) : order.status === filter.value)))
const visible = computed(() => filtered.value.slice(0, visibleCount.value))
watch(filter, () => { visibleCount.value = 6 })

let refreshTimer = null
let requestSerial = 0

const statusNames = {
  UNPAID: '待支付',
  PAID: '已支付',
  CANCELLED: '已取消',
  EXPIRED: '已过期',
}

function statusName(status) {
  return statusNames[status] ?? status
}

async function loadOrders({ silent = false, notifyChanged = true } = {}) {
  const thisRequest = ++requestSerial
  const oldStatuses = new Map(
    orders.value.map(order => [order.id, order.status])
  )

  if (!silent) loading.value = true

  try {
    const freshOrders = await listMyOrders(props.token)

    // 后发起的请求已经完成时，不让旧响应覆盖新数据。
    if (thisRequest !== requestSerial) return

    const statusChanged = freshOrders.some(
      order =>
        oldStatuses.get(order.id) === 'UNPAID' &&
        order.status !== 'UNPAID'
    )

    orders.value = freshOrders
    error.value = ''

    if (notifyChanged && statusChanged) {
      emit('changed')
    }
  } catch (cause) {
    if (thisRequest !== requestSerial) return

    if (cause.status === 401) {
      emit('unauthorized')
    } else if (!silent) {
      error.value = `订单加载失败：${cause.message}`
    }
  } finally {
    if (thisRequest === requestSerial) {
      loading.value = false
    }
  }
}

async function changeStatus(orderId, action) {
  if (busyOrderId.value !== null) return

  busyOrderId.value = orderId
  actionMessage.value = ''

  try {
    const result = action === 'pay'
      ? await payOrder(orderId, props.token)
      : await cancelOrder(orderId, props.token)

    actionMessage.value =
      `订单 ${result.orderId} 已${action === 'pay' ? '支付' : '取消'}`

    emit('changed')
    await loadOrders({ notifyChanged: false })
  } catch (cause) {
    if (cause.status === 401) {
      emit('unauthorized')
    } else if (cause.status === 409) {
      actionMessage.value = '操作未成功：订单状态已变化，或支付期限已过'
      await loadOrders()
    } else if (cause.status === 404) {
      actionMessage.value = '订单不存在或不属于当前用户'
      await loadOrders()
    } else {
      actionMessage.value = `操作失败：${cause.message}`
    }
  } finally {
    busyOrderId.value = null
  }
}

onMounted(() => {
  loadOrders()

  refreshTimer = window.setInterval(() => {
    if (
      document.visibilityState === 'visible' &&
      busyOrderId.value === null &&
      !loading.value &&
      orders.value.some(order => order.status === 'UNPAID')
    ) {
      loadOrders({ silent: true })
    }
  }, 15000)
})

onUnmounted(() => {
  requestSerial += 1
  window.clearInterval(refreshTimer)
})

watch(() => props.refreshVersion, () => loadOrders())
</script>
<template>
  <section class="orders-panel">
    <div class="orders-heading"><div><h2>每一份期待，都在这里</h2><p>{{ orders.length }} 笔订单 · 支付与取消随时查看</p></div><button type="button" :disabled="loading" @click="loadOrders"><AppIcon name="refresh" :size="15" /> 刷新订单</button></div>
    <div class="order-tabs filter-tabs"><button v-for="tab in [{id:'all',label:'全部订单'},{id:'UNPAID',label:'待支付'},{id:'PAID',label:'已支付'},{id:'closed',label:'已结束'}]" :key="tab.id" type="button" :class="{selected:filter===tab.id}" :aria-pressed="filter === tab.id" @click="filter=tab.id">{{ tab.label }}</button></div>
    <p v-if="actionMessage" class="feedback" role="status">{{ actionMessage }}</p><p v-if="loading" class="empty-state">正在整理你的订单…</p><p v-else-if="error" role="alert">{{ error }}</p><div v-else-if="!filtered.length" class="empty-state"><AppIcon name="ticket" :size="35" /><h3>这里暂时空着</h3><p>每一次新的报名，都会为这里添一份期待。</p></div>
    <ul v-else class="orders-list"><li v-for="order in visible" :key="order.id" class="order-item"><span :class="['order-symbol', order.status]"><AppIcon name="ticket" :size="25" /></span><div class="order-copy"><span class="order-number">ORDER / {{ order.id }}</span><strong :title="order.eventTitle">{{ order.eventTitle }}</strong><p><AppIcon name="clock" :size="13" /> 支付截止 {{ formatBeijing(order.expiresAtUtc) }}</p></div><div class="order-right"><span :class="['order-state', order.status]">{{ statusName(order.status) }}</span><div v-if="order.status === 'UNPAID'" class="order-actions"><button type="button" :disabled="busyOrderId !== null" @click="changeStatus(order.id, 'cancel')">取消订单</button><button type="button" class="pay-button" :disabled="busyOrderId !== null" @click="changeStatus(order.id, 'pay')">模拟支付 <AppIcon name="arrow" :size="13" /></button></div></div></li></ul>
    <button v-if="visibleCount < filtered.length" type="button" class="load-more" @click="visibleCount += 6">查看更多订单 +{{ Math.min(6, filtered.length - visibleCount) }}</button>
  </section>
</template>
<style scoped>
.orders-panel { background: #fff; padding: 26px; border: 1px solid #e9e5ef; border-radius: 18px; }.orders-heading { display: flex; align-items: center; justify-content: space-between; gap: 15px; margin-bottom: 25px; }.orders-heading h2 { margin: 0; font-size: 17px; color: #6d607d; font-weight: 550; }.orders-heading p { color: #aa9ab9; font-size: 11px; margin: 8px 0 0; }.orders-heading button { display: inline-flex; align-items: center; gap: 6px; font-size: 10px; color: #a08ab8; }.order-tabs { width: fit-content; margin-bottom: 22px; }.orders-list { padding: 0; margin: 0; list-style: none; }.order-item { display: flex; align-items: center; gap: 16px; padding: 21px 0; border-bottom: 1px solid #f1edf5; }.order-item:last-child { border-bottom: 0; }.order-symbol { display: grid; place-items: center; flex-shrink: 0; width: 56px; height: 62px; border-radius: 12px; color: #b7a4cc; background: #f4eef9; }.order-symbol.UNPAID { background: #fff3e6; color: #cbb08a; }.order-symbol.PAID { background: #edf6f0; color: #a0b8a7; }.order-copy { flex: 1; min-width: 0; }.order-number { color: #bbadca; font-size: 8px; letter-spacing: .08em; }.order-copy strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #80708e; font-size: 12px; font-weight: 550; margin: 6px 0 8px; }.order-copy p { display: flex; align-items: center; gap: 5px; color: #b6a6c2; font-size: 10px; margin: 0; }.order-right { text-align: right; }.order-state { display: inline-block; padding: 5px 9px; background: #f5f1f8; border-radius: 6px; color: #b8a9c5; font-size: 10px; }.order-state.UNPAID { color: #b99667; background: #fff4e5; }.order-state.PAID { color: #94ac9d; background: #f0f7f2; }.order-actions { display: flex; gap: 7px; margin-top: 10px; }.order-actions button { font-size: 9px; padding: 6px 9px; }.order-actions .pay-button { display: flex; align-items: center; gap: 5px; background: #a187cf; border-color: #a187cf; color: #fff; }
@media(max-width:680px) { .orders-panel { padding: 19px 15px; }.orders-heading { align-items: flex-start; }.orders-heading h2 { font-size: 15px; }.orders-heading p { font-size: 10px; }.orders-heading button { padding: 7px 9px; font-size: 9px; white-space: nowrap; }.order-item { flex-wrap: wrap; gap: 10px; }.order-symbol { width: 42px; height: 50px; }.order-copy strong { font-size: 11px; }.order-copy p { font-size: 9px; }.order-right { margin-left: auto; }.order-actions { flex-wrap: wrap; justify-content: flex-end; }.order-state { font-size: 9px; }.order-tabs { width: 100%; }.order-tabs button { font-size: 10px; padding: 8px 6px; } }
</style>

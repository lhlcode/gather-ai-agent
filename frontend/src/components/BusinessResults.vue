<script setup>
import { computed, ref } from 'vue'
import { formatBeijing } from '../utils/time'
import AppIcon from './AppIcon.vue'
const props = defineProps({ response: { type: Object, required: true } })
const emit = defineEmits(['open-event', 'open-orders'])
const expanded = ref(false)
const data = computed(() => props.response.tool_results?.find(item => Array.isArray(item.events) || Array.isArray(item.orders)))
const items = computed(() => data.value?.events || data.value?.orders || [])
const shown = computed(() => expanded.value ? items.value : items.value.slice(0, 3))
const orderNames = { UNPAID: '待支付', PAID: '已支付', CANCELLED: '已取消', EXPIRED: '已过期' }
</script>
<template>
  <div v-if="data && items.length" class="business-results">
    <template v-if="data.events">
      <button v-for="event in shown" :key="event.id" type="button" class="result-card" @click="emit('open-event', event.id)">
        <span class="result-symbol"><AppIcon name="ticket" /></span>
        <span class="result-copy"><strong>{{ event.title }}</strong><small>活动 {{ event.id }} · 剩余 {{ event.availableQuota }} 个名额</small></span>
        <AppIcon name="arrow" :size="16" />
      </button>
    </template>
    <template v-else>
      <button v-for="order in shown" :key="order.id" type="button" class="result-card" @click="emit('open-orders')">
        <span class="result-symbol"><AppIcon name="ticket" /></span>
        <span class="result-copy"><strong>{{ order.eventTitle }}</strong><small>订单 {{ order.id }} · {{ orderNames[order.status] || order.status }}</small></span>
        <AppIcon name="arrow" :size="16" />
      </button>
    </template>
    <button v-if="items.length > 3" type="button" class="result-more" @click="expanded = !expanded">{{ expanded ? '收起列表' : `展开其余 ${items.length - 3} 项` }}</button>
    <button v-if="data.orders && data.truncated" type="button" class="result-more" @click="emit('open-orders')">还有 {{ data.total_count - data.returned_count }} 笔订单，请到我的订单查看</button>
    <small v-if="data.queried_at" class="result-time">查询快照 · {{ formatBeijing(data.queried_at) }}</small>
  </div>
</template>

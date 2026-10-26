<script setup>
import { ref } from 'vue'
import { createDraft, publishDraft } from '../api/adminEvents'

const props = defineProps({
  token: { type: String, required: true },
})

const emit = defineEmits(['published', 'unauthorized'])

const title = ref('')
const totalQuota = ref(3)
const startBeijing = ref('')
const endBeijing = ref('')
const draftId = ref(null)
const busy = ref(false)
const message = ref('')

function beijingInputToUtc(value) {
  // datetime-local 不带时区；明确把输入按北京时间（UTC+08:00）解释。
  const date = new Date(`${value}:00+08:00`)
  if (Number.isNaN(date.getTime())) {
    throw new Error('请输入有效的报名时间')
  }
  return date.toISOString()
}

async function submitCreate() {
  if (busy.value) return
  busy.value = true
  message.value = ''

  try {
    const startUtc = beijingInputToUtc(startBeijing.value)
    const endUtc = beijingInputToUtc(endBeijing.value)

    if (new Date(startUtc) >= new Date(endUtc) ||
        new Date(endUtc) <= new Date()) {
      throw new Error('结束时间必须晚于开始时间和当前时间')
    }

    const result = await createDraft({
      title: title.value.trim(),
      totalQuota: totalQuota.value,
      registrationStartAtUtc: startUtc,
      registrationEndAtUtc: endUtc,
    }, props.token)

    draftId.value = result.eventId
    message.value = `草稿创建成功，活动 ID：${result.eventId}`
  } catch (cause) {
    if (cause.status === 401) {
      emit('unauthorized')
    } else if (cause.status === 403) {
      message.value = '当前账号没有管理员权限'
    } else {
      message.value = `创建失败：${cause.message}`
    }
  } finally {
    busy.value = false
  }
}

async function submitPublish() {
  if (busy.value || draftId.value === null) return
  busy.value = true
  message.value = ''

  try {
    const result = await publishDraft(draftId.value, props.token)
    message.value = `活动 ${result.eventId} 已发布`
    emit('published')
  } catch (cause) {
    if (cause.status === 401) {
      emit('unauthorized')
    } else if (cause.status === 409) {
      message.value = '发布失败：活动已发布或报名时间已结束'
    } else {
      message.value = `发布失败：${cause.message}`
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="admin-panel">
    <h2>管理员：创建活动</h2>
    <form class="admin-form" @submit.prevent="submitCreate">
      <label>
        活动标题
        <input v-model.trim="title" maxlength="120" required>
      </label>
      <label>
        总名额
        <input v-model.number="totalQuota" type="number" min="1" required>
      </label>
      <label>
        报名开始（北京时间）
        <input v-model="startBeijing" type="datetime-local" required>
      </label>
      <label>
        报名结束（北京时间）
        <input v-model="endBeijing" type="datetime-local" required>
      </label>
      <button type="submit" :disabled="busy">创建草稿</button>
    </form>

    <div v-if="draftId !== null" class="publish-row">
      <span>当前草稿 ID：{{ draftId }}</span>
      <button type="button" :disabled="busy" @click="submitPublish">
        发布活动
      </button>
    </div>
    <p v-if="message" role="status">{{ message }}</p>
  </section>
</template>

<style scoped>
.admin-panel {
  margin: 28px 0;
  padding: 20px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 10px;
}

.admin-form {
  display: grid;
  gap: 12px;
}

.admin-form label {
  display: grid;
  gap: 6px;
}

.admin-form input {
  max-width: 360px;
  padding: 8px;
}

.admin-form button,
.publish-row button {
  width: fit-content;
  padding: 8px 14px;
}

.publish-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 20px;
}
</style>
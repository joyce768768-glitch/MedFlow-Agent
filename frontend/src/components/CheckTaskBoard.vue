<template>
  <div class="bg-white rounded-xl shadow-sm p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-slate-800">检查任务看板</h3>
      <button v-if="!readOnly && auth.isAttending" @click="labSummary"
        class="text-sm px-3 py-1.5 bg-slate-700 text-white rounded-lg hover:bg-slate-800">检验汇总 SubAgent</button>
    </div>

    <!-- 开立检查任务（仅主治） -->
    <div v-if="!readOnly && auth.permissions?.can_open_check" class="mb-4 p-3 bg-slate-50 rounded-lg">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-sm text-slate-600">勾选检查项：</span>
        <label v-for="t in taskTypes" :key="t.type" class="flex items-center gap-1 text-sm">
          <input type="checkbox" :value="t.type" v-model="selectedTypes" />
          {{ t.label }}
        </label>
        <button @click="createTasks" :disabled="!selectedTypes.length || creating"
          class="ml-auto px-3 py-1.5 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
          {{ creating ? '提交中…' : '提交 Mock 任务' }}
        </button>
      </div>
      <p v-if="msg" class="text-xs mt-2" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
    </div>

    <!-- 任务列表 -->
    <div class="space-y-2">
      <div v-for="t in tasks" :key="t.task_id" class="p-3 bg-slate-50 rounded-lg border border-slate-100 flex items-center gap-3">
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <span class="font-medium text-slate-700 text-sm">{{ t.task_label }}</span>
            <TaskStatusBadge :status="t.status" />
          </div>
          <div class="text-xs text-slate-400 mt-1">
            开立：{{ t.created_by_name }} · {{ fmt(t.created_at) }}
            <span v-if="t.completed_at"> · 完成：{{ fmt(t.completed_at) }}</span>
          </div>
          <div v-if="t.result" class="text-xs text-slate-600 mt-1">结果：{{ t.result.summary }}</div>
        </div>
        <!-- 状态流转按钮（仅主治） -->
        <div v-if="!readOnly && auth.permissions?.can_open_check" class="flex gap-1">
          <button v-if="t.status === 'ordered'" @click="transition(t.task_id, 'pending')"
            class="text-xs px-2 py-1 rounded bg-amber-100 text-amber-700 hover:bg-amber-200">推进：待执行</button>
          <button v-if="t.status === 'pending'" @click="transition(t.task_id, 'done')"
            class="text-xs px-2 py-1 rounded bg-green-100 text-green-700 hover:bg-green-200">完成并回填</button>
        </div>
      </div>
      <div v-if="!tasks.length" class="text-sm text-slate-400 text-center py-4">暂无检查任务</div>
    </div>

    <!-- 检验汇总结果（弹层） -->
    <div v-if="summary" class="mt-4 p-3 bg-brand-50 border border-brand-100 rounded-lg">
      <div class="text-sm font-medium text-brand-700 mb-1">检验汇总 SubAgent 输出</div>
      <pre class="text-sm text-slate-700 whitespace-pre-wrap">{{ summary }}</pre>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import TaskStatusBadge from './TaskStatusBadge.vue'

const props = defineProps({ patientId: String, readOnly: { type: Boolean, default: false } })
const emit = defineEmits(['updated'])
const auth = useAuthStore()
const tasks = ref([])
const selectedTypes = ref([])
const creating = ref(false); const msg = ref(''); const err = ref(false)
const summary = ref('')

const taskTypes = [
  { type: 'blood', label: '血常规' },
  { type: 'ct', label: 'CT' },
  { type: 'ultrasound', label: 'B超' },
]

async function load() {
  const { data } = await api.get(`/patients/${props.patientId}/check-tasks`)
  tasks.value = data
}
async function createTasks() {
  creating.value = true; msg.value = ''; err.value = false
  try {
    for (const ty of selectedTypes.value) {
      const label = taskTypes.find(t => t.type === ty).label
      await api.post(`/patients/${props.patientId}/check-tasks`, { task_type: ty, task_label: label })
    }
    msg.value = `已开立 ${selectedTypes.value.length} 项检查任务（Mock）`
    selectedTypes.value = []
    await load(); emit('updated')
  } catch (e) { err.value = true; msg.value = e.response?.data?.detail || '开立失败' }
  finally { creating.value = false }
}
async function transition(id, status) {
  try {
    await api.patch(`/patients/${props.patientId}/check-tasks/${id}`, { status })
    await load(); emit('updated')
  } catch (e) { alert(e.response?.data?.detail || '流转失败') }
}
async function labSummary() {
  try {
    const { data } = await api.post(`/patients/${props.patientId}/check-tasks/lab-summary`)
    summary.value = data.summary
  } catch (e) { alert(e.response?.data?.detail || '汇总失败') }
}
function fmt(t) { return t ? new Date(t).toLocaleString('zh-CN') : '' }
onMounted(load)
</script>

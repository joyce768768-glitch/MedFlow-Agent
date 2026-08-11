<template>
  <div class="bg-white rounded-xl shadow-sm p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-slate-800">诊疗方案</h3>
      <span v-if="latest" class="text-xs text-slate-400">当前版本 v{{ latest.version_no }} · {{ latest.created_by_name }} · {{ fmt(latest.created_at) }}</span>
    </div>

    <!-- 最新诊疗方案（默认展示） -->
    <div v-if="latest" class="p-3 bg-brand-50 border border-brand-100 rounded-lg text-sm text-slate-700 whitespace-pre-wrap">
      {{ latest.content }}
    </div>
    <div v-else class="p-3 bg-slate-50 rounded-lg text-sm text-slate-400">暂无诊疗方案</div>

    <!-- 新建版本（仅主治） -->
    <div v-if="auth.permissions?.can_edit_emr" class="mt-4">
      <label class="block text-sm font-medium text-slate-600 mb-1">新建诊疗方案版本（不覆盖旧版）</label>
      <textarea v-model="newContent" rows="3"
        class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"></textarea>
      <button @click="createVersion" :disabled="!newContent.trim() || creating"
        class="mt-2 px-3 py-1.5 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
        {{ creating ? '提交中…' : '新建版本' }}
      </button>
      <p v-if="msg" class="text-xs mt-1" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
    </div>

    <!-- 历史版本折叠面板（默认收起） -->
    <div v-if="auth.permissions?.can_view_history && versions.length > 1" class="mt-4 border-t border-slate-100 pt-3">
      <button @click="showHistory = !showHistory"
        class="text-sm text-slate-600 hover:text-brand-700 flex items-center gap-1">
        <span>{{ showHistory ? '▼' : '▶' }}</span>
        历史诊疗方案（{{ versions.length - 1 }} 条，默认收起）
      </button>
      <div v-show="showHistory" class="mt-3 space-y-2">
        <div v-for="v in versions.slice(1)" :key="v.version_id"
          class="p-3 bg-slate-50 rounded-lg border border-slate-100">
          <div class="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>v{{ v.version_no }} · {{ v.created_by_name }}</span>
            <span>{{ fmt(v.created_at) }}</span>
          </div>
          <div class="text-sm text-slate-600 whitespace-pre-wrap">{{ v.content }}</div>
          <div class="text-xs text-slate-400 mt-1">历史版本只读，不可编辑</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ patientId: String })
const emit = defineEmits(['updated'])
const auth = useAuthStore()
const versions = ref([])
const showHistory = ref(false)
const newContent = ref('')
const creating = ref(false)
const msg = ref('')
const err = ref(false)

const latest = computed(() => versions.value[0])

async function load() {
  const { data } = await api.get(`/patients/${props.patientId}/treatment-versions`)
  versions.value = data
}
async function createVersion() {
  creating.value = true; msg.value = ''; err.value = false
  try {
    await api.post(`/patients/${props.patientId}/treatment-versions`, { content: newContent.value.trim() })
    msg.value = '已新建版本（旧版保留）'
    newContent.value = ''
    await load()
    emit('updated')
  } catch (e) {
    err.value = true
    msg.value = e.response?.data?.detail || '新建失败'
  } finally { creating.value = false }
}
function fmt(t) { return t ? new Date(t).toLocaleString('zh-CN') : '' }
onMounted(load)
</script>

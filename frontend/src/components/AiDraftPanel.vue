<template>
  <div class="bg-white rounded-xl shadow-sm p-4 sticky top-0">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-slate-800">AI 草稿建议面板</h3>
      <span v-if="enabled" class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">SubAgent 已开启</span>
      <span v-else class="text-xs px-2 py-0.5 rounded-full bg-slate-200 text-slate-600">SubAgent 已关闭</span>
    </div>

    <!-- 仅主治可见生成按钮 -->
    <button v-if="auth.permissions?.can_generate_ai" @click="generate" :disabled="loading"
      class="w-full mb-3 px-3 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
      {{ loading ? '生成中…' : '生成 AI 病历草稿' }}
    </button>

    <div class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 mb-2">
      AI 草稿为独立建议，不会自动写入正式病历；需主治 HITL 确认后手动采纳。
    </div>

    <div v-if="draft" class="p-3 bg-slate-50 rounded-lg text-sm text-slate-700 whitespace-pre-wrap max-h-96 overflow-auto">
      {{ draft }}
    </div>
    <div v-else class="p-3 bg-slate-50 rounded-lg text-sm text-slate-400">
      暂无 AI 草稿{{ auth.permissions?.can_generate_ai ? '，点击上方按钮生成' : '' }}
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ patientId: String })
const auth = useAuthStore()
const draft = ref('')
const enabled = ref(false)
const loading = ref(false)

async function load() {
  const { data } = await api.get(`/patients/${props.patientId}/emr`)
  draft.value = data.ai_draft || ''
  enabled.value = !!data.enable_emr_subagent
}
async function generate() {
  loading.value = true
  try {
    const { data } = await api.post(`/patients/${props.patientId}/emr/ai-draft`)
    draft.value = data.ai_draft
    enabled.value = data.enabled
  } catch (e) {
    draft.value = '生成失败：' + (e.response?.data?.detail || '未知错误')
  } finally { loading.value = false }
}
onMounted(load)
</script>

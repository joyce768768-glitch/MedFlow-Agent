<template>
  <aside class="w-72 bg-white border-r border-slate-200 flex flex-col shrink-0">
    <div class="px-4 py-3 border-b border-slate-100">
      <div class="text-sm font-semibold text-slate-700">
        {{ role === 'nurse' ? '分诊排队列表' : '待接诊患者列表' }}
      </div>
      <div class="text-xs text-slate-400 mt-0.5">{{ patients.length }} 位患者</div>
    </div>
    <div class="flex-1 overflow-auto">
      <button v-for="p in patients" :key="p.patient_id" @click="$emit('select', p.patient_id)"
        class="w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-brand-50 transition">
        <div class="flex items-center justify-between">
          <span class="font-medium text-slate-800">{{ p.patient_name }}</span>
          <StatusBadge :status="p.status" />
        </div>
        <div class="text-xs text-slate-400 mt-1">
          {{ p.check_task_count }} 项检查 · {{ p.mdt_comment_count }} 条MDT
        </div>
      </button>
      <div v-if="!patients.length" class="p-6 text-center text-sm text-slate-400">暂无可见患者</div>
    </div>
  </aside>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'
import StatusBadge from './StatusBadge.vue'

defineProps({ role: { type: String, default: '' } })
defineEmits(['select'])

const patients = ref([])

async function load() {
  const { data } = await api.get('/patients')
  patients.value = data
}
onMounted(load)
defineExpose({ load })
</script>

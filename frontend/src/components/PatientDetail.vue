<template>
  <div class="max-w-6xl mx-auto">
    <!-- 患者基础信息 -->
    <div class="bg-white rounded-xl shadow-sm p-4 mb-4 flex items-center gap-4">
      <div class="w-12 h-12 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-lg">
        {{ patient?.patient_name?.[0] || '?' }}
      </div>
      <div class="flex-1">
        <div class="flex items-center gap-2">
          <span class="text-lg font-semibold text-slate-800">{{ patient?.patient_name }}</span>
          <StatusBadge :status="patient?.status" />
          <span v-if="hitlPending" class="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">HITL 待终审</span>
        </div>
        <div class="text-xs text-slate-400 mt-1">
          患者 ID：{{ patient?.patient_id }} · 主治：{{ attendingNames }}
        </div>
      </div>
    </div>

    <!-- 护士视图：仅基础信息 + 检查任务只读 -->
    <div v-if="auth.isNurse" class="space-y-4">
      <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
        护士视图：仅可查看患者基础信息与检查任务状态，病历/MDT/AI 面板已隐藏。
      </div>
      <CheckTaskBoard :patient-id="patientId" read-only @updated="reload" />
    </div>

    <!-- 其他角色：多 Tab -->
    <div v-else>
      <div class="flex gap-1 border-b border-slate-200 mb-4">
        <button v-for="t in tabs" :key="t.key" @click="tab = t.key"
          :class="['px-4 py-2 text-sm font-medium border-b-2 -mb-px',
                   tab === t.key ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-700']">
          {{ t.label }}
        </button>
      </div>

      <!-- Tab1：诊疗 & 病历区 -->
      <div v-show="tab === 'clinic'" class="grid grid-cols-3 gap-4">
        <div class="col-span-2 space-y-4">
          <TreatmentPanel :patient-id="patientId" @updated="reload" />
          <EmrEditor :patient-id="patientId" @updated="reload" />
        </div>
        <div class="col-span-1">
          <AiDraftPanel :patient-id="patientId" />
        </div>
      </div>

      <!-- MDT 讨论区 -->
      <div v-show="tab === 'mdt'">
        <MdtDiscussion :patient-id="patientId" @updated="reload" />
      </div>

      <!-- 检查任务看板 -->
      <div v-show="tab === 'check'">
        <CheckTaskBoard :patient-id="patientId" @updated="reload" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import StatusBadge from './StatusBadge.vue'
import TreatmentPanel from './TreatmentPanel.vue'
import EmrEditor from './EmrEditor.vue'
import AiDraftPanel from './AiDraftPanel.vue'
import MdtDiscussion from './MdtDiscussion.vue'
import CheckTaskBoard from './CheckTaskBoard.vue'

const props = defineProps({ patientId: String })
const auth = useAuthStore()
const patient = ref(null)
const tab = ref('clinic')

const tabs = computed(() => {
  const t = [{ key: 'clinic', label: '诊疗 & 病历区' }]
  if (auth.permissions?.can_view_mdt) t.push({ key: 'mdt', label: 'MDT 讨论区' })
  if (auth.permissions?.can_view_check) t.push({ key: 'check', label: '检查任务看板' })
  return t
})

const hitlPending = computed(() => !!patient.value?.hitl_pending)
const attendingNames = computed(() => {
  const ids = patient.value?.attending_doctor_ids || []
  return ids.join('，')
})

async function load() {
  const { data } = await api.get(`/patients/${props.patientId}`)
  patient.value = data
}
function reload() { load() }
onMounted(load)
defineExpose({ load })
</script>

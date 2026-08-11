<template>
  <div class="bg-white rounded-xl shadow-sm p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-slate-800">主病历</h3>
      <span v-if="locked" class="text-xs px-2 py-0.5 rounded-full bg-slate-200 text-slate-600">已定稿锁定</span>
      <span v-else class="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">未定稿</span>
    </div>

    <!-- 只读（非主治或已锁定） -->
    <div v-if="!canEdit" class="p-3 bg-slate-50 rounded-lg text-sm text-slate-700 whitespace-pre-wrap min-h-[80px]">
      {{ emr.content || '（暂无病历正文）' }}
    </div>
    <div v-if="!canEdit && locked" class="text-xs text-slate-400 mt-2">
      定稿人：{{ emr.locked_by_name }} · {{ fmt(emr.locked_at) }}
    </div>

    <!-- 可编辑（主治且未锁定） -->
    <div v-if="canEdit">
      <textarea v-model="emr.content" rows="5"
        class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"></textarea>
      <div class="flex items-center gap-2 mt-2">
        <button @click="save" :disabled="saving"
          class="px-3 py-1.5 bg-slate-700 text-white text-sm rounded-lg hover:bg-slate-800 disabled:opacity-50">
          {{ saving ? '保存中…' : '保存病历' }}
        </button>
        <button @click="lock(true)" :disabled="!emr.content || locking"
          class="px-3 py-1.5 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
          定稿锁定（HITL 终审）
        </button>
      </div>
      <p v-if="msg" class="text-xs mt-1" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
    </div>

    <!-- 主治且已锁定：可解锁 -->
    <div v-if="auth.isAttending && locked" class="mt-2">
      <button @click="lock(false)" :disabled="locking"
        class="px-3 py-1.5 bg-slate-200 text-slate-700 text-sm rounded-lg hover:bg-slate-300">
        解除锁定
      </button>
      <p v-if="msg" class="text-xs mt-1" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
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
const emr = ref({ content: '', locked: false, locked_by_name: '', locked_at: null })
const saving = ref(false); const locking = ref(false)
const msg = ref(''); const err = ref(false)

const locked = computed(() => !!emr.value.locked)
const canEdit = computed(() => auth.permissions?.can_edit_emr && !locked.value)

async function load() {
  const { data } = await api.get(`/patients/${props.patientId}/emr`)
  emr.value = { ...data.emr_main }
}
async function save() {
  saving.value = true; msg.value = ''; err.value = false
  try {
    const { data } = await api.put(`/patients/${props.patientId}/emr`, { content: emr.value.content })
    emr.value = { ...data }
    msg.value = '已保存（未定稿，需 HITL 终审）'
    emit('updated')
  } catch (e) { err.value = true; msg.value = e.response?.data?.detail || '保存失败' }
  finally { saving.value = false }
}
async function lock(v) {
  locking.value = true; msg.value = ''; err.value = false
  try {
    const { data } = await api.post(`/patients/${props.patientId}/emr/lock`, { locked: v })
    emr.value = { ...data }
    msg.value = v ? '已定稿锁定' : '已解除锁定'
    emit('updated')
  } catch (e) { err.value = true; msg.value = e.response?.data?.detail || '操作失败' }
  finally { locking.value = false }
}
function fmt(t) { return t ? new Date(t).toLocaleString('zh-CN') : '' }
onMounted(load)
</script>

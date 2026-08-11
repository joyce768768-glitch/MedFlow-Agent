<template>
  <div class="fixed bottom-20 right-3 z-40">
    <button
      @click="showModal = true"
      class="w-12 h-12 bg-brand-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-brand-700 transition-colors active:scale-95"
      title="呼叫护士协助"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    </button>

    <!-- 呼叫弹窗 -->
    <div v-if="showModal" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" @click.self="showModal = false">
      <div class="bg-white rounded-2xl p-5 w-full max-w-sm shadow-2xl">
        <div class="flex items-center gap-2 mb-4">
          <div class="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center">
            <span class="text-brand-600 text-xl">👩‍⚕️</span>
          </div>
          <div>
            <h3 class="font-semibold text-slate-800">呼叫护士协助</h3>
            <p class="text-xs text-slate-500">工作人员将尽快前往您所在位置</p>
          </div>
        </div>

        <div class="space-y-3">
          <div>
            <label class="text-xs text-slate-600 block mb-1">所在位置</label>
            <input v-model="form.room_name" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="如：门诊楼1层101诊室" />
          </div>
          <div>
            <label class="text-xs text-slate-600 block mb-1">协助说明</label>
            <textarea v-model="form.message" rows="3" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="请描述您需要什么协助..." />
          </div>
        </div>

        <div class="flex gap-2 mt-4">
          <button @click="showModal = false" class="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm">取消</button>
          <button @click="submit" :disabled="submitting" class="flex-1 py-2 rounded-lg bg-brand-600 text-white text-sm disabled:opacity-50">
            {{ submitting ? '提交中...' : '提交呼叫' }}
          </button>
        </div>

        <p class="text-xs text-slate-400 mt-3 text-center">
          Demo 模拟功能，生产环境将推送到护士工作台
        </p>
      </div>
    </div>

    <!-- 成功提示 -->
    <div v-if="successMsg" class="fixed bottom-24 left-1/2 -translate-x-1/2 bg-green-500 text-white px-4 py-2 rounded-lg text-sm shadow-lg">
      {{ successMsg }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { usePatientStore } from '../../stores/patient'
import { patientApi } from '../../api/patient'

const emit = defineEmits(['nurse-called'])

const patientStore = usePatientStore()
const showModal = ref(false)
const submitting = ref(false)
const successMsg = ref('')

const form = reactive({
  room_name: '',
  message: '',
})

async function submit() {
  submitting.value = true
  try {
    const res = await patientStore.fetchProfile()
    await patientApi.createNurseRequest({
      message: form.message || '患者请求协助',
      room_name: form.room_name || '待确认',
    })
    emit('nurse-called')
    showModal.value = false
    form.room_name = ''
    form.message = ''
    successMsg.value = '护士已收到呼叫，将尽快前往'
    setTimeout(() => { successMsg.value = '' }, 3000)
  } catch (e) {
    // Mock 降级：即使接口失败也显示成功（Demo 体验）
    showModal.value = false
    form.room_name = ''
    form.message = ''
    successMsg.value = '护士已收到呼叫（Mock）'
    setTimeout(() => { successMsg.value = '' }, 3000)
  } finally {
    submitting.value = false
  }
}
</script>

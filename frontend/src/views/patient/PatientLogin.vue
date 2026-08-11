<template>
  <div class="min-h-screen flex flex-col bg-gradient-to-b from-blue-50 via-white to-slate-50">
    <div class="w-full max-w-md mx-auto flex-1 flex flex-col px-5 py-8">
      <div class="text-center mb-8 mt-10">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-600 text-white text-3xl mb-4 shadow-lg shadow-brand-600/20">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-9 h-9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="2" x2="12" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-slate-800 tracking-tight">MedFlow 医院服务</h1>
        <p class="text-sm text-slate-500 mt-2">请使用就诊卡号登录</p>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 mb-4">
        <p class="text-xs font-medium text-slate-400 mb-3 uppercase tracking-wide">快速登录</p>
        <div class="space-y-2">
          <button
            v-for="a in accounts"
            :key="a.patient_id"
            type="button"
            :disabled="loading"
            @click="quickLogin(a)"
            class="w-full flex items-center justify-between px-4 py-3 rounded-xl border border-slate-200 hover:border-brand-400 hover:bg-brand-50 transition-colors disabled:opacity-60 disabled:pointer-events-none"
          >
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center text-lg font-semibold">
                {{ a.name.charAt(0) }}
              </div>
              <div class="text-left">
                <div class="text-sm font-medium text-slate-700">{{ a.name }}</div>
                <div class="text-xs text-slate-400 font-mono">{{ a.medical_card_number }}</div>
              </div>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </div>

      <div class="flex items-center gap-4 my-5">
        <div class="flex-1 h-px bg-slate-200" />
        <span class="text-xs text-slate-400">或手动输入</span>
        <div class="flex-1 h-px bg-slate-200" />
      </div>

      <form @submit.prevent="onLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-600 mb-1.5">患者ID</label>
          <input
            v-model="patientId"
            type="text"
            placeholder="请输入患者ID"
            autocomplete="username"
            class="w-full px-4 py-3 border border-slate-200 rounded-xl bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent text-sm transition-all"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-600 mb-1.5">就诊卡号</label>
          <input
            v-model="cardNumber"
            type="text"
            placeholder="请输入就诊卡号"
            autocomplete="off"
            class="w-full px-4 py-3 border border-slate-200 rounded-xl bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent text-sm transition-all font-mono"
          />
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 bg-brand-600 text-white rounded-xl font-medium hover:bg-brand-700 active:bg-brand-800 disabled:opacity-60 disabled:pointer-events-none transition-colors shadow-sm shadow-brand-600/20 mt-2"
        >
          {{ loading ? '登录中…' : '登 录' }}
        </button>

        <p v-if="error" class="text-sm text-red-500 text-center bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {{ error }}
        </p>
      </form>

      <div class="mt-auto pt-8 text-center">
        <p class="text-xs text-slate-400">Demo 模拟登录，不涉及真实电子健康卡核验</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePatientStore } from '../../stores/patient'

const router = useRouter()
const patientStore = usePatientStore()

const patientId = ref('')
const cardNumber = ref('')
const loading = ref(false)
const error = ref('')

const accounts = [
  { patient_id: 'p001', name: '张伟', medical_card_number: '622202000001' },
  { patient_id: 'p002', name: '李娜', medical_card_number: '622202000002' },
]

async function quickLogin(account) {
  loading.value = true
  error.value = ''
  try {
    await patientStore.login(account.patient_id, account.medical_card_number)
    router.push('/patient/home')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查账号信息'
  } finally {
    loading.value = false
  }
}

async function onLogin() {
  if (!patientId.value.trim() || !cardNumber.value.trim()) {
    error.value = '请填写完整的登录信息'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await patientStore.login(patientId.value.trim(), cardNumber.value.trim())
    router.push('/patient/home')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查账号信息'
  } finally {
    loading.value = false
  }
}
</script>
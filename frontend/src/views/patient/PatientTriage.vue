<template>
  <div class="min-h-screen bg-slate-50 flex flex-col" :class="fontClass">
    <div class="w-full max-w-md mx-auto flex-1 flex flex-col min-h-screen">
      <!-- Header -->
      <header class="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-slate-100">
        <div class="px-4 py-3 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="router.back()"
              class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-500"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <div>
              <h1 class="text-base font-semibold text-slate-800">AI智能分诊</h1>
              <p v-if="traceId" class="text-[10px] text-slate-400 font-mono mt-0.5">
                trace: {{ traceId }}
              </p>
            </div>
          </div>
          <span class="text-[10px] text-slate-400 bg-slate-100 px-2 py-1 rounded">Mock模拟</span>
        </div>

        <!-- Warning banner -->
        <div class="mx-4 mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
          <p class="text-[11px] text-amber-700 leading-relaxed">
            ⚠️ AI建议仅为就诊分诊参考，不构成诊断与医嘱，最终就诊方案请遵医护人员判断
          </p>
        </div>
      </header>

      <!-- Recommended departments -->
      <div v-if="recommendedDepts.length" class="px-4 py-3 space-y-2">
        <div class="flex items-center gap-2 mb-1">
          <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
          <span class="text-xs font-semibold text-slate-600">AI推荐科室</span>
        </div>
        <div
          v-for="dept in recommendedDepts"
          :key="dept.name"
          class="bg-white rounded-xl border border-slate-200 shadow-sm p-3"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-slate-800">{{ dept.name }}</span>
              <span
                :class="[
                  'text-[10px] px-2 py-0.5 rounded-full font-medium',
                  confidenceClass(dept.confidence),
                ]"
              >
                {{ confidenceLabel(dept.confidence) }}
              </span>
            </div>
          </div>
          <div class="flex gap-2">
            <button
              type="button"
              @click="bookByRecommend(dept)"
              class="flex-1 px-3 py-2 bg-brand-600 text-white text-xs font-medium rounded-lg hover:bg-brand-700 transition-colors"
            >
              基于推荐挂号
            </button>
            <button
              type="button"
              @click="askNurse(dept)"
              :disabled="nurseLoading"
              class="flex-1 px-3 py-2 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
            >
              {{ nurseLoading ? '处理中…' : '去找护士协助' }}
            </button>
          </div>
        </div>
        <button
          type="button"
          @click="goSelfBooking"
          class="w-full py-2 text-xs text-brand-600 font-medium bg-brand-50 rounded-lg hover:bg-brand-100 transition-colors"
        >
          自行选择科室 →
        </button>
      </div>

      <!-- Chat messages -->
      <div class="flex-1 overflow-y-auto px-4 py-4 space-y-3" ref="chatContainer">
        <div v-if="loading && messages.length === 0" class="flex justify-center py-8">
          <div class="flex items-center gap-2 text-slate-400 text-sm">
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:0ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:150ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:300ms" />
            <span class="ml-1">AI正在接入…</span>
          </div>
        </div>

        <template v-for="(msg, idx) in messages" :key="idx">
          <!-- AI message -->
          <div v-if="msg.role === 'agent'" class="flex justify-start">
            <div class="flex items-start gap-2 max-w-[80%]">
              <div class="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
                AI
              </div>
              <div class="bg-brand-500 text-white rounded-2xl rounded-tl-sm px-3 py-2 text-sm leading-relaxed shadow-sm">
                {{ msg.content }}
              </div>
            </div>
          </div>

          <!-- Patient message -->
          <div v-else class="flex justify-end">
            <div class="flex items-start gap-2 max-w-[80%]">
              <div class="bg-slate-100 text-slate-800 rounded-2xl rounded-tr-sm px-3 py-2 text-sm leading-relaxed shadow-sm">
                {{ msg.content }}
              </div>
              <div class="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold flex-shrink-0">
                {{ patientStore.patient?.name?.charAt(0) || '我' }}
              </div>
            </div>
          </div>
        </template>

        <!-- Typing indicator -->
        <div v-if="typing" class="flex justify-start">
          <div class="flex items-start gap-2 max-w-[80%]">
            <div class="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
              AI
            </div>
            <div class="bg-brand-500 text-white rounded-2xl rounded-tl-sm px-3 py-2.5 shadow-sm">
              <div class="flex gap-1">
                <span class="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style="animation-delay:0ms" />
                <span class="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style="animation-delay:150ms" />
                <span class="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style="animation-delay:300ms" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="sticky bottom-0 z-10 bg-white border-t border-slate-100">
        <div class="px-4 py-3 flex items-end gap-2">
          <textarea
            v-model="inputMessage"
            @keydown.enter.exact.prevent="sendMessage"
            :disabled="!sessionId || sending"
            rows="1"
            placeholder="请描述您的症状…"
            class="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all disabled:opacity-50"
          />
          <button
            type="button"
            @click="sendMessage"
            :disabled="!inputMessage.trim() || !sessionId || sending"
            class="px-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            {{ sending ? '发送中' : '发送' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Nurse transfer confirmation modal -->
    <div v-if="showNurseConfirm" class="fixed inset-0 z-30 flex items-center justify-center bg-black/40 px-6">
      <div class="bg-white rounded-2xl w-full max-w-xs p-5 shadow-xl">
        <div class="text-center">
          <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h3 class="text-base font-semibold text-slate-800 mb-1">已通知护士站</h3>
          <p class="text-xs text-slate-500 leading-relaxed">
            护士已收到您的协助请求，请在候诊区等待，护士会尽快前来协助您前往 {{ nurseDepartment }}。
          </p>
        </div>
        <button
          type="button"
          @click="showNurseConfirm = false"
          class="w-full mt-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 transition-colors"
        >
          我知道了
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { usePatientStore } from '../../stores/patient'
import { patientApi } from '../../api/patient'

const router = useRouter()
const patientStore = usePatientStore()

const fontClass = computed(() => patientStore.fontClass)

const sessionId = ref('')
const traceId = ref('')
const messages = ref([])
const recommendedDepts = ref([])
const inputMessage = ref('')
const loading = ref(false)
const sending = ref(false)
const typing = ref(false)
const nurseLoading = ref(false)
const showNurseConfirm = ref(false)
const nurseDepartment = ref('')
const chatContainer = ref(null)

function confidenceClass(level) {
  const map = {
    high: 'bg-green-100 text-green-700',
    medium: 'bg-amber-100 text-amber-700',
    low: 'bg-slate-100 text-slate-600',
  }
  return map[level] || 'bg-slate-100 text-slate-600'
}

function confidenceLabel(level) {
  const map = { high: '高置信', medium: '中置信', low: '低置信' }
  return map[level] || level || '未知'
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

async function createSession() {
  loading.value = true
  try {
    const res = await patientApi.createTriageSession()
    sessionId.value = res.session_id || res.id
    traceId.value = res.trace_id || res.traceId || ''
    if (res.welcome_message) {
      messages.value.push({ role: 'agent', content: res.welcome_message })
    } else {
      messages.value.push({
        role: 'agent',
        content: '您好！我是AI分诊助手，请描述您的症状，我将为您推荐合适的就诊科室。',
      })
    }
    scrollToBottom()
  } catch (e) {
    console.error('创建分诊会话失败', e)
    messages.value.push({
      role: 'agent',
      content: '抱歉，分诊服务暂时不可用，请直接前往挂号处或咨询护士协助。',
    })
  } finally {
    loading.value = false
  }
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || !sessionId.value || sending.value) return

  messages.value.push({ role: 'patient', content: text })
  inputMessage.value = ''
  sending.value = true
  typing.value = true
  scrollToBottom()

  try {
    const res = await patientApi.triageChat(sessionId.value, text)

    typing.value = false

    if (res.reply || res.response || res.message) {
      messages.value.push({
        role: 'agent',
        content: res.reply || res.response || res.message,
      })
    }

    if (res.recommended_departments && res.recommended_departments.length) {
      recommendedDepts.value = res.recommended_departments.map((d) => ({
        name: d.name || d.department_name || d.department,
        confidence: d.confidence || d.confidence_level || 'medium',
        ...d,
      }))
    }

    if (res.trace_id) {
      traceId.value = res.trace_id
    }

    scrollToBottom()
  } catch (e) {
    typing.value = false
    console.error('分诊对话失败', e)
    messages.value.push({
      role: 'agent',
      content: '抱歉，对话服务暂时不可用，请稍后重试或咨询护士协助。',
    })
    scrollToBottom()
  } finally {
    sending.value = false
  }
}

function bookByRecommend(dept) {
  router.push({
    path: '/patient/booking',
    query: { dept: dept.name, from: 'triage' },
  })
}

async function askNurse(dept) {
  if (!sessionId.value) return
  nurseLoading.value = true
  try {
    await patientApi.nurseTransfer(sessionId.value)
    nurseDepartment.value = dept.name
    showNurseConfirm.value = true
  } catch (e) {
    console.error('护士转接失败', e)
    nurseDepartment.value = dept.name
    showNurseConfirm.value = true
  } finally {
    nurseLoading.value = false
  }
}

function goSelfBooking() {
  router.push({ path: '/patient/booking', query: { from: 'triage' } })
}

onMounted(() => {
  createSession()
})
</script>
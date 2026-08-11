<template>
  <div class="min-h-screen bg-slate-50 pb-10" :class="fontClass">
    <div class="w-full max-w-md mx-auto">
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
            <h1 class="text-base font-semibold text-slate-800">就诊行程</h1>
          </div>
          <button
            type="button"
            @click="loadData"
            class="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            刷新
          </button>
        </div>
      </header>

      <main class="px-4 py-4 space-y-4">
        <div v-if="loading" class="flex justify-center py-12">
          <div class="flex items-center gap-2 text-slate-400 text-sm">
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:0ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:150ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:300ms" />
            <span class="ml-1">加载中…</span>
          </div>
        </div>

        <template v-else-if="timelineEvents.length">
          <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
            <div class="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
                <h2 class="text-sm font-semibold text-slate-700">就诊时间线</h2>
              </div>
              <span class="text-xs text-slate-400">{{ timelineEvents.length }} 个事件</span>
            </div>

            <div class="px-5 py-4">
              <div class="relative pl-6">
                <div class="absolute left-[7px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-brand-200 via-slate-200 to-slate-100" />

                <div
                  v-for="(event, idx) in timelineEvents"
                  :key="idx"
                  class="relative mb-6 last:mb-0"
                >
                  <div
                    :class="[
                      'absolute -left-6 top-1 w-4 h-4 rounded-full border-2 flex items-center justify-center',
                      eventDotClass(event),
                    ]"
                  >
                    <div
                      :class="[
                        'w-1.5 h-1.5 rounded-full',
                        eventStatusClass(event.status),
                      ]"
                    />
                  </div>

                  <div
                    :class="[
                      'rounded-xl border p-3 transition-all',
                      eventCardClass(event),
                    ]"
                  >
                    <div class="flex items-start justify-between gap-2 mb-1.5">
                      <div class="flex items-center gap-2 min-w-0">
                        <span
                          :class="[
                            'text-[10px] px-2 py-0.5 rounded-full font-medium flex-shrink-0',
                            eventTypeClass(event.type),
                          ]"
                        >
                          {{ eventTypeLabel(event.type) }}
                        </span>
                        <h3 class="text-sm font-semibold text-slate-800 truncate">{{ event.title }}</h3>
                      </div>
                      <span
                        :class="[
                          'text-[10px] px-2 py-0.5 rounded-full font-medium flex-shrink-0',
                          statusBadgeClass(event.status),
                        ]"
                      >
                        {{ statusLabel(event.status) }}
                      </span>
                    </div>

                    <p v-if="event.description" class="text-xs text-slate-500 leading-relaxed mb-2">
                      {{ event.description }}
                    </p>

                    <div class="flex items-center gap-2 text-[10px] text-slate-400">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                      <span>{{ event.timestamp }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </template>

        <div v-else class="bg-white rounded-2xl border border-dashed border-slate-200 p-8 text-center">
          <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
          <p class="text-sm text-slate-500">暂无就诊行程记录</p>
          <p class="text-xs text-slate-400 mt-1">挂号后将在此处显示您的就诊进度</p>
        </div>

        <section v-if="pendingChecks.length" class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              <h2 class="text-sm font-semibold text-slate-700">待检查项目</h2>
            </div>
            <span class="text-xs text-slate-400">{{ pendingChecks.length }} 项待完成</span>
          </div>

          <div class="divide-y divide-slate-50">
            <div
              v-for="(task, idx) in pendingChecks"
              :key="idx"
              class="px-5 py-3.5"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="text-sm font-medium text-slate-800">{{ task.label }}</span>
                    <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 font-medium">
                      待检查
                    </span>
                  </div>
                  <p class="text-xs text-slate-500">
                    {{ task.room_name ? `检查地点：${task.room_name}` : '请前往检查室' }}
                  </p>
                  <p v-if="task.scheduled_at" class="text-xs text-slate-400 mt-0.5">
                    预计时间：{{ task.scheduled_at }}
                  </p>
                </div>
                <button
                  type="button"
                  @click="goToCheck(task)"
                  class="px-3 py-2 bg-brand-600 text-white text-xs font-medium rounded-lg hover:bg-brand-700 transition-colors flex-shrink-0"
                >
                  前往检查
                </button>
              </div>
            </div>
          </div>
        </section>

        <div class="px-2 py-3">
          <p class="text-xs text-slate-400 text-center leading-relaxed">
            就诊行程仅为参考，实际就诊顺序请以医院叫号为准
          </p>
        </div>
      </main>
    </div>

    <div
      v-if="showCheckNotice"
      class="fixed inset-0 z-30 flex items-center justify-center bg-black/40 px-6"
      @click.self="showCheckNotice = false"
    >
      <div class="bg-white rounded-2xl w-full max-w-xs p-5 shadow-xl">
        <div class="text-center">
          <div class="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-orange-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <h3 class="text-base font-semibold text-slate-800 mb-1">检查提醒</h3>
          <p class="text-sm text-slate-600 leading-relaxed">
            请前往 <span class="font-semibold text-brand-600">{{ noticeData.room_name }}</span> 进行 <span class="font-semibold text-slate-800">{{ noticeData.task_label }}</span>
          </p>
        </div>
        <div class="mt-4 flex gap-2">
          <button
            type="button"
            @click="showCheckNotice = false"
            class="flex-1 py-2.5 bg-slate-100 text-slate-700 text-sm font-medium rounded-xl hover:bg-slate-200 transition-colors"
          >
            稍后提醒
          </button>
          <button
            type="button"
            @click="confirmCheck"
            class="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 transition-colors"
          >
            立即前往
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePatientStore } from '../../stores/patient'
import { patientApi } from '../../api/patient'

const router = useRouter()
const patientStore = usePatientStore()

const fontClass = computed(() => patientStore.fontClass)

const loading = ref(false)
const timelineEvents = ref([])
const pendingChecks = ref([])

const showCheckNotice = ref(false)
const noticeData = ref({})

const typeColorMap = {
  booking: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-600', dot: 'bg-blue-500', chip: 'bg-blue-100 text-blue-700' },
  waiting: { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-600', dot: 'bg-slate-400', chip: 'bg-slate-100 text-slate-600' },
  consultation: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', dot: 'bg-green-500', chip: 'bg-green-100 text-green-700' },
  check: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', dot: 'bg-orange-500', chip: 'bg-orange-100 text-orange-700' },
  report: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', dot: 'bg-purple-500', chip: 'bg-purple-100 text-purple-700' },
  followup: { bg: 'bg-teal-50', border: 'border-teal-200', text: 'text-teal-700', dot: 'bg-teal-500', chip: 'bg-teal-100 text-teal-700' },
}

function getTypeStyle(type) {
  return typeColorMap[type] || typeColorMap.waiting
}

function eventDotClass(event) {
  const style = getTypeStyle(event.type)
  return `${style.bg} ${style.border}`
}

function eventCardClass(event) {
  const style = getTypeStyle(event.type)
  return `${style.bg} ${style.border}`
}

function eventTypeClass(type) {
  const style = getTypeStyle(type)
  return style.chip
}

function eventTypeLabel(type) {
  const map = {
    booking: '挂号',
    waiting: '候诊',
    consultation: '问诊',
    check: '检查',
    report: '报告',
    followup: '复诊/取药',
  }
  return map[type] || '事件'
}

function eventStatusClass(status) {
  const map = {
    done: 'bg-green-500',
    current: 'bg-brand-500',
    pending: 'bg-amber-400',
  }
  return map[status] || 'bg-slate-300'
}

function statusBadgeClass(status) {
  const map = {
    done: 'bg-green-50 text-green-600',
    current: 'bg-brand-50 text-brand-600',
    pending: 'bg-amber-50 text-amber-600',
  }
  return map[status] || 'bg-slate-50 text-slate-500'
}

function statusLabel(status) {
  const map = {
    done: '已完成',
    current: '进行中',
    pending: '待处理',
  }
  return map[status] || '未知'
}

async function loadData() {
  loading.value = true
  try {
    const res = await patientApi.getTimeline()
    const events = res.events || res.data || []

    timelineEvents.value = events.map((e) => ({
      type: e.type || e.event_type || 'waiting',
      title: e.title || e.event_title || '就诊事件',
      description: e.description || e.desc || '',
      timestamp: e.timestamp || e.time || e.created_at || '',
      status: e.status || 'pending',
    }))

    const checks = (res.check_tasks || res.pending_checks || []).filter(
      (t) => t.status === 'pending' || t.status === 'scheduled'
    )
    pendingChecks.value = checks.map((t) => ({
      label: t.label || t.task_label || '检查项目',
      room_name: t.room_name || t.room || '',
      scheduled_at: t.scheduled_at || t.time || '',
      id: t.id,
    }))
  } catch (e) {
    console.warn('加载就诊行程失败', e)
    timelineEvents.value = []
    pendingChecks.value = []
  } finally {
    loading.value = false
  }
}

function goToCheck(task) {
  noticeData.value = task
  showCheckNotice.value = true
}

function confirmCheck() {
  showCheckNotice.value = false
  router.push('/patient/triage')
}

onMounted(() => {
  loadData()
})
</script>
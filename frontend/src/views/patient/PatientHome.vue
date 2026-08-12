<template>
  <div class="min-h-screen bg-slate-50 pb-20" :class="fontClass">
    <div class="w-full max-w-md mx-auto">
      <header class="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-slate-100">
        <div class="px-5 py-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs text-slate-400">{{ currentDate }}</p>
              <h1 class="text-lg font-semibold text-slate-800 mt-0.5">
                您好，{{ patientStore.patient?.name || '患者' }}
              </h1>
            </div>
            <div class="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              <button
                v-for="s in fontScales"
                :key="s.value"
                type="button"
                @click="patientStore.setFontScale(s.value)"
                :class="[
                  'px-2 py-1 rounded-md text-xs font-medium transition-colors',
                  patientStore.fontScale === s.value
                    ? 'bg-white text-brand-600 shadow-sm'
                    : 'text-slate-400 hover:text-slate-600',
                ]"
              >
                {{ s.label }}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main class="px-4 py-4 space-y-4">
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="action in quickActions"
            :key="action.path"
            type="button"
            @click="navigateTo(action.path)"
            class="flex flex-col items-start p-4 bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md hover:border-brand-200 transition-all active:scale-[0.98] text-left"
          >
            <div class="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-xl mb-2">
              {{ action.icon }}
            </div>
            <span class="text-sm font-medium text-slate-700">{{ action.label }}</span>
          </button>
        </div>

        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
              <h2 class="text-sm font-semibold text-slate-700">就诊动态</h2>
            </div>
            <span class="text-xs text-slate-400">{{ timeline.length }} 条记录</span>
          </div>
          <div v-if="timeline.length" class="divide-y divide-slate-50">
            <div
              v-for="(item, idx) in timeline"
              :key="idx"
              class="px-5 py-3 flex items-start gap-3"
            >
              <div
                :class="[
                  'w-2 h-2 rounded-full mt-1.5 flex-shrink-0',
                  item.status === 'done' ? 'bg-green-400' : item.status === 'pending' ? 'bg-amber-400' : 'bg-slate-300',
                ]"
              />
              <div class="flex-1 min-w-0">
                <p class="text-sm text-slate-700">{{ item.title }}</p>
                <p class="text-xs text-slate-400 mt-0.5">{{ item.time }}</p>
              </div>
              <span
                :class="[
                  'text-xs px-2 py-0.5 rounded-full flex-shrink-0',
                  item.status === 'done'
                    ? 'bg-green-50 text-green-600'
                    : item.status === 'pending'
                    ? 'bg-amber-50 text-amber-600'
                    : 'bg-slate-50 text-slate-500',
                ]"
              >
                {{ item.status === 'done' ? '已完成' : item.status === 'pending' ? '进行中' : '待处理' }}
              </span>
            </div>
          </div>
          <div v-else class="px-5 py-8 text-center text-sm text-slate-400">
            暂无就诊动态
          </div>
        </section>

        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-1.5 h-1.5 rounded-full bg-amber-400" />
              <h2 class="text-sm font-semibold text-slate-700">待办事项</h2>
            </div>
            <button
              v-if="pendingTasks.length"
              type="button"
              @click="navigateTo('/patient/triage')"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium"
            >
              前往处理 →
            </button>
          </div>
          <div v-if="pendingTasks.length" class="p-4 space-y-2">
            <div
              v-for="(task, idx) in pendingTasks"
              :key="idx"
              class="flex items-center gap-3 p-3 rounded-xl bg-amber-50/50 border border-amber-100"
            >
              <div class="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-sm">
                {{ task.icon }}
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">{{ task.title }}</p>
                <p class="text-xs text-slate-400 mt-0.5">{{ task.desc }}</p>
              </div>
            </div>
          </div>
          <div v-if="completedTasks.length" class="p-4 space-y-2 border-t border-slate-100">
            <p class="text-xs text-slate-400 mb-2">已完成就诊</p>
            <div
              v-for="(task, idx) in completedTasks"
              :key="'c'+idx"
              class="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100"
            >
              <div class="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-sm">
                {{ task.icon }}
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-600 truncate">{{ task.title }}</p>
                <p class="text-xs text-slate-400 mt-0.5">{{ task.desc }}</p>
              </div>
            </div>
          </div>
          <div v-if="!pendingTasks.length && !completedTasks.length" class="px-5 py-8 text-center text-sm text-slate-400">
            暂无就诊动态
          </div>
        </section>

        <div class="px-2 py-3">
          <p class="text-xs text-slate-400 text-center leading-relaxed">
            AI建议仅为就诊分诊参考，不构成诊断与医嘱
          </p>
        </div>
      </main>
    </div>

    <nav class="fixed bottom-0 left-0 right-0 z-20">
      <div class="w-full max-w-md mx-auto bg-white border-t border-slate-100">
        <div class="grid grid-cols-4">
          <button
            v-for="tab in navItems"
            :key="tab.path"
            type="button"
            @click="navigateTo(tab.path)"
            :class="[
              'flex flex-col items-center justify-center py-2.5 gap-0.5 transition-colors',
              activeNav === tab.key
                ? 'text-brand-600'
                : 'text-slate-400 hover:text-slate-600',
            ]"
          >
            <span class="text-lg leading-none">{{ tab.icon }}</span>
            <span class="text-xs">{{ tab.label }}</span>
          </button>
        </div>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { usePatientStore } from '../../stores/patient'
import { patientApi } from '../../api/patient'

const router = useRouter()
const route = useRoute()
const patientStore = usePatientStore()

const fontClass = computed(() => patientStore.fontClass)

const fontScales = [
  { label: 'A', value: 0 },
  { label: 'A', value: 1 },
  { label: 'A', value: 2 },
]

const currentDate = computed(() => {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const weeks = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${y}年${m}月${d}日 ${weeks[now.getDay()]}`
})

const quickActions = [
  { icon: '🔍', label: 'AI智能导诊', path: '/patient/triage' },
  { icon: '📅', label: '预约挂号', path: '/patient/booking' },
  { icon: '📋', label: '我的报告', path: '/patient/reports' },
  { icon: '🗺️', label: '院内导航', path: '/patient/navigation' },
]

const navItems = [
  { key: 'home', icon: '🏠', label: '首页', path: '/patient/home' },
  { key: 'booking', icon: '📅', label: '挂号', path: '/patient/booking' },
  { key: 'reports', icon: '📋', label: '报告', path: '/patient/reports' },
  { key: 'profile', icon: '👤', label: '我的', path: '/patient/profile' },
]

const activeNav = computed(() => {
  const path = router.currentRoute.value.path
  const found = navItems.find((t) => path.startsWith(t.path))
  return found ? found.key : 'home'
})

const timeline = ref([])
const pendingTasks = ref([])
const completedTasks = ref([])

function navigateTo(path) {
  router.push(path)
}

async function loadData() {
  try {
    const [bookingsRes, timelineRes] = await Promise.allSettled([
      patientApi.listBookings(),
      patientApi.getTimeline(),
    ])

    if (timelineRes.status === 'fulfilled' && Array.isArray(timelineRes.value)) {
      timeline.value = timelineRes.value.map((e) => ({
        title: e.title || e.description || '就诊事件',
        time: e.time || e.created_at || '',
        status: e.status || 'pending',
      }))
    }

    if (bookingsRes.status === 'fulfilled' && Array.isArray(bookingsRes.value)) {
      const all = bookingsRes.value
      const pending = all.filter(
        (b) => ['pending', 'scheduled', 'upcoming', 'waiting', 'in_progress', 'booked'].includes(b.status)
      )
      pendingTasks.value = pending.map((b) => ({
        icon: '📋',
        title: `${b.department || ''} ${b.statusText || '预约'}`,
        desc: `${b.slot_date || ''} ${b.slot_time || ''}`,
      }))
      // Also show completed ones as "history"
      const completed = all.filter((b) => b.status === 'completed')
      completedTasks.value = completed.map((b) => ({
        icon: '✅',
        title: `${b.department || ''} 就诊完成`,
        desc: `${b.slot_date || ''} ${b.slot_time || ''}`,
      }))
    }
  } catch (e) {
    console.warn('加载首页数据失败', e)
  }
}

onMounted(() => {
  loadData()
})

// 从其他页面返回时重新加载数据
watch(() => route.fullPath, (newPath) => {
  if (newPath === '/patient/home') {
    loadData()
  }
})
</script>
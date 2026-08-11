<template>
  <div class="min-h-screen bg-slate-50 pb-20" :class="fontClass">
    <div class="w-full max-w-md mx-auto">
      <header class="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-slate-100">
        <div class="px-4 py-3 flex items-center gap-3">
          <button
            type="button"
            @click="router.back()"
            class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-500 flex-shrink-0"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <h1 class="text-base font-semibold text-slate-800">院内导航</h1>
        </div>

        <div class="px-4 pb-3">
          <div class="relative">
            <svg xmlns="http://www.w3.org/2000/svg" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索科室名称，如：消化内科、CT室"
              class="w-full pl-9 pr-9 py-2.5 bg-slate-100 rounded-xl text-sm text-slate-700 placeholder-slate-400 border border-transparent focus:bg-white focus:border-brand-300 focus:outline-none transition-colors"
              @keyup.enter="handleSearch"
            />
            <button
              v-if="searchQuery"
              type="button"
              @click="clearSearch"
              class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-slate-400 hover:text-slate-600"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      <main class="px-4 py-4 space-y-3">
        <div v-if="loading" class="flex justify-center py-12">
          <div class="flex items-center gap-2 text-slate-400 text-sm">
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:0ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:150ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:300ms" />
            <span class="ml-1">搜索中…</span>
          </div>
        </div>

        <template v-else-if="filteredList.length">
          <div
            v-for="(dept, idx) in filteredList"
            :key="idx"
            @click="selectedDept = dept"
            class="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 cursor-pointer hover:shadow-md hover:border-brand-200 transition-all active:scale-[0.99]"
          >
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-xl flex-shrink-0">
                {{ dept.icon || '🏥' }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-semibold text-slate-800">{{ dept.name }}</h3>
                  <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">{{ dept.category }}</span>
                </div>
                <div class="mt-1.5 flex items-center gap-2 text-xs text-slate-500">
                  <span class="flex items-center gap-0.5">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M3 21h18" />
                      <path d="M5 21V7l8-4v18" />
                      <path d="M19 21V11l-6-4" />
                    </svg>
                    {{ dept.building }}
                  </span>
                  <span class="text-slate-300">›</span>
                  <span>{{ dept.floor }}楼</span>
                  <span class="text-slate-300">›</span>
                  <span>{{ dept.room }}</span>
                </div>
              </div>
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-300 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </div>
          </div>
        </template>

        <div v-else class="bg-white rounded-2xl border border-dashed border-slate-200 p-8 text-center">
          <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <p class="text-sm text-slate-500">未找到相关科室</p>
          <p class="text-xs text-slate-400 mt-1">请尝试其他关键词</p>
        </div>

        <div v-if="!searchQuery && departments.length" class="mt-4">
          <div class="flex items-center gap-2 mb-3">
            <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
            <h2 class="text-sm font-semibold text-slate-700">全部科室</h2>
          </div>
        </div>
      </main>

      <Teleport to="body">
        <transition name="slide-up">
          <div
            v-if="selectedDept"
            class="fixed inset-0 z-30 flex items-end"
            @click.self="selectedDept = null"
          >
            <div class="absolute inset-0 bg-black/40" />
            <div class="relative w-full max-w-md mx-auto bg-white rounded-t-3xl p-5 pb-8 max-h-[80vh] overflow-y-auto">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-semibold text-slate-800">{{ selectedDept.name }}</h3>
                <button
                  type="button"
                  @click="selectedDept = null"
                  class="w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>

              <div class="bg-slate-50 rounded-2xl p-4 space-y-3">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-xl">
                    {{ selectedDept.icon || '🏥' }}
                  </div>
                  <div>
                    <p class="text-sm font-medium text-slate-800">{{ selectedDept.name }}</p>
                    <p class="text-xs text-slate-500">{{ selectedDept.category }}</p>
                  </div>
                </div>

                <div class="flex items-center justify-center py-2">
                  <div class="flex flex-col items-center gap-1 text-xs text-slate-600">
                    <div class="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 21h18" />
                        <path d="M5 21V7l8-4v18" />
                        <path d="M19 21V11l-6-4" />
                      </svg>
                      <span>{{ selectedDept.building }}</span>
                    </div>
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <polyline points="19 12 12 19 5 12" />
                    </svg>
                    <div class="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
                        <line x1="8" y1="6" x2="16" y2="6" />
                        <line x1="8" y1="10" x2="16" y2="10" />
                        <line x1="8" y1="14" x2="16" y2="14" />
                      </svg>
                      <span>{{ selectedDept.floor }}楼</span>
                    </div>
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <polyline points="19 12 12 19 5 12" />
                    </svg>
                    <div class="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                        <polyline points="9 22 9 12 15 12 15 22" />
                      </svg>
                      <span>{{ selectedDept.room }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="selectedDept.hours" class="flex items-start gap-2 pt-2 border-t border-slate-100">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-400 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  <div>
                    <p class="text-xs text-slate-500">营业时间</p>
                    <p class="text-sm text-slate-700">{{ selectedDept.hours }}</p>
                  </div>
                </div>

                <div v-if="selectedDept.tip" class="flex items-start gap-2 pt-2 border-t border-slate-100">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-500 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                    <line x1="12" y1="9" x2="12" y2="13" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                  <div>
                    <p class="text-xs text-slate-500">温馨提示</p>
                    <p class="text-sm text-slate-700">{{ selectedDept.tip }}</p>
                  </div>
                </div>
              </div>

              <button
                type="button"
                @click="selectedDept = null"
                class="w-full mt-4 py-3 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-xl transition-colors"
              >
                知道了
              </button>
            </div>
          </div>
        </transition>
      </Teleport>
    </div>

    <PatientBottomNav />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePatientStore } from '../../stores/patient'
import { patientApi } from '../../api/patient'
import PatientBottomNav from './PatientBottomNav.vue'

const router = useRouter()
const patientStore = usePatientStore()

const fontClass = computed(() => patientStore.fontClass)

const searchQuery = ref('')
const loading = ref(false)
const departments = ref([])
const selectedDept = ref(null)

const mockDepartments = [
  { name: '消化内科', category: '内科', building: '门诊楼', floor: '3', room: '301-305', icon: '🩺', hours: '周一至周日 08:00-17:30', tip: '建议空腹前来检查' },
  { name: '呼吸内科', category: '内科', building: '门诊楼', floor: '3', room: '310-314', icon: '🫁', hours: '周一至周日 08:00-17:30', tip: '就诊前请准备好病史资料' },
  { name: '心血管内科', category: '内科', building: '门诊楼', floor: '4', room: '401-405', icon: '❤️', hours: '周一至周日 08:00-17:30', tip: '建议穿着宽松衣物' },
  { name: '神经内科', category: '内科', building: '门诊楼', floor: '4', room: '410-414', icon: '🧠', hours: '周一至周日 08:00-17:30' },
  { name: '骨科', category: '外科', building: '门诊楼', floor: '5', room: '501-505', icon: '🦴', hours: '周一至周日 08:00-17:30' },
  { name: '普外科', category: '外科', building: '门诊楼', floor: '5', room: '510-514', icon: '🔪', hours: '周一至周日 08:00-17:30' },
  { name: '儿科', category: '专科', building: '门诊楼', floor: '2', room: '201-208', icon: '👶', hours: '周一至周日 08:00-17:30', tip: '儿童就诊需由家长陪同' },
  { name: '妇产科', category: '专科', building: '门诊楼', floor: '3', room: '320-325', icon: '🤰', hours: '周一至周日 08:00-17:30' },
  { name: '眼科', category: '专科', building: '门诊楼', floor: '2', room: '210-212', icon: '👁️', hours: '周一至周日 08:00-17:30', tip: '检查前请不要佩戴隐形眼镜' },
  { name: '耳鼻喉科', category: '专科', building: '门诊楼', floor: '2', room: '215-218', icon: '👂', hours: '周一至周日 08:00-17:30' },
  { name: '口腔科', category: '专科', building: '门诊楼', floor: '2', room: '220-224', icon: '🦷', hours: '周一至周日 08:00-17:30' },
  { name: '皮肤科', category: '专科', building: '门诊楼', floor: '4', room: '420-422', icon: '💇', hours: '周一至周日 08:00-17:30' },
  { name: '医学影像科（CT室）', category: '检查科室', building: '医技楼', floor: '1', room: '101', icon: '🩻', hours: '周一至周日 08:00-22:00', tip: 'CT检查前请去除金属物品' },
  { name: '放射科（DR室）', category: '检查科室', building: '医技楼', floor: '1', room: '102', icon: '🩻', hours: '周一至周日 08:00-22:00' },
  { name: '检验科', category: '检查科室', building: '医技楼', floor: '1', room: '105-108', icon: '🧪', hours: '周一至周日 07:30-17:00', tip: '抽血检查需空腹' },
  { name: '超声科', category: '检查科室', building: '医技楼', floor: '2', room: '201-205', icon: '📡', hours: '周一至周日 08:00-17:30' },
  { name: '心电图室', category: '检查科室', building: '医技楼', floor: '2', room: '210', icon: '📈', hours: '周一至周日 08:00-17:30' },
  { name: '病理科', category: '检查科室', building: '医技楼', floor: '3', room: '301', icon: '🔬', hours: '周一至周五 08:00-17:00' },
  { name: '麻醉科', category: '医技科室', building: '住院楼', floor: '-1', room: '手术区', icon: '💉', hours: '24小时' },
  { name: '急诊科', category: '急诊', building: '急诊楼', floor: '1', room: '101-105', icon: '🚑', hours: '24小时', tip: '紧急情况请直接前往急诊科' },
  { name: '输液中心', category: '治疗', building: '门诊楼', floor: '1', room: '大厅', icon: '💊', hours: '周一至周日 08:00-22:00' },
  { name: '中药房', category: '药房', building: '门诊楼', floor: '1', room: '东侧', icon: '🌿', hours: '周一至周日 08:00-20:00' },
  { name: '西药房', category: '药房', building: '门诊楼', floor: '1', room: '西侧', icon: '💊', hours: '周一至周日 08:00-20:00' },
]

const filteredList = computed(() => {
  if (!searchQuery.value.trim()) return departments.value
  const q = searchQuery.value.trim().toLowerCase()
  return departments.value.filter(
    (d) =>
      d.name.toLowerCase().includes(q) ||
      d.category.toLowerCase().includes(q) ||
      d.building.toLowerCase().includes(q)
  )
})

async function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) {
    departments.value = mockDepartments
    return
  }

  loading.value = true
  try {
    const res = await patientApi.getNavByDept(q)
    const list = res.departments || res.data || res
    if (Array.isArray(list) && list.length) {
      departments.value = list.map((d) => ({
        name: d.name || d.dept_name || '',
        category: d.category || d.type || '',
        building: d.building || d.building_name || '',
        floor: d.floor || d.floor_number || '',
        room: d.room || d.room_number || '',
        icon: d.icon || '🏥',
        hours: d.hours || d.open_hours || '',
        tip: d.tip || d.notice || '',
      }))
    } else {
      departments.value = mockDepartments
    }
  } catch (e) {
    console.warn('搜索科室失败，使用本地数据', e)
    departments.value = mockDepartments.filter(
      (d) => d.name.includes(q) || d.category.includes(q)
    )
  } finally {
    loading.value = false
  }
}

function clearSearch() {
  searchQuery.value = ''
  departments.value = mockDepartments
}

onMounted(() => {
  departments.value = mockDepartments
})
</script>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease-out;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}
</style>
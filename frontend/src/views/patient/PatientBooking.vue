<template>
  <div class="min-h-screen bg-slate-50 pb-8" :class="fontClass">
    <div class="w-full max-w-md mx-auto">
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
            <h1 class="text-base font-semibold text-slate-800">预约挂号</h1>
          </div>
          <span class="text-[10px] text-slate-400 bg-slate-100 px-2 py-1 rounded">Mock模拟</span>
        </div>
      </header>

      <!-- Tabs -->
      <div class="px-4 pt-3">
        <div class="flex gap-1 bg-slate-100 rounded-xl p-0.5">
          <button
            type="button"
            @click="activeTab = 'ai'"
            :class="[
              'flex-1 py-2 text-sm font-medium rounded-lg transition-all',
              activeTab === 'ai'
                ? 'bg-white text-brand-600 shadow-sm'
                : 'text-slate-500 hover:text-slate-700',
            ]"
          >
            AI推荐挂号
          </button>
          <button
            type="button"
            @click="activeTab = 'self'"
            :class="[
              'flex-1 py-2 text-sm font-medium rounded-lg transition-all',
              activeTab === 'self'
                ? 'bg-white text-brand-600 shadow-sm'
                : 'text-slate-500 hover:text-slate-700',
            ]"
          >
            自助挂号
          </button>
        </div>
      </div>

      <!-- AI推荐挂号 Tab -->
      <div v-if="activeTab === 'ai'" class="px-4 py-4 space-y-4">
        <div v-if="recommendedDepts.length" class="space-y-3">
          <div class="flex items-center gap-2">
            <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
            <span class="text-sm font-semibold text-slate-700">为您推荐的科室</span>
          </div>

          <div
            v-for="dept in recommendedDepts"
            :key="dept.name"
            class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden"
          >
            <div class="p-4">
              <div class="flex items-center justify-between mb-3">
                <div>
                  <h3 class="text-sm font-semibold text-slate-800">{{ dept.name }}</h3>
                  <p class="text-xs text-slate-400 mt-0.5">{{ dept.desc || dept.description || 'AI智能分诊推荐' }}</p>
                </div>
                <span
                  :class="[
                    'text-[10px] px-2 py-0.5 rounded-full font-medium',
                    confidenceClass(dept.confidence),
                  ]"
                >
                  {{ confidenceLabel(dept.confidence) }}
                </span>
              </div>

              <div class="grid grid-cols-3 gap-2 mb-3">
                <div class="bg-slate-50 rounded-lg px-2 py-1.5 text-center">
                  <p class="text-[10px] text-slate-400 mb-0.5">剩余号源</p>
                  <p class="text-sm font-semibold text-slate-700">{{ dept.available || 5 }}个</p>
                </div>
                <div class="bg-slate-50 rounded-lg px-2 py-1.5 text-center">
                  <p class="text-[10px] text-slate-400 mb-0.5">预计等待</p>
                  <p class="text-sm font-semibold text-slate-700">{{ dept.wait_time || 15 }}分钟</p>
                </div>
                <div class="bg-slate-50 rounded-lg px-2 py-1.5 text-center">
                  <p class="text-[10px] text-slate-400 mb-0.5">诊室</p>
                  <p class="text-sm font-semibold text-slate-700">{{ dept.room || '待分配' }}</p>
                </div>
              </div>

              <button
                type="button"
                @click="quickBook(dept)"
                :disabled="bookingLoading"
                class="w-full py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 transition-colors disabled:opacity-50"
              >
                {{ bookingLoading ? '提交中…' : '立即预约' }}
              </button>
            </div>
          </div>
        </div>

        <div v-else class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 text-center">
          <div class="w-12 h-12 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <h3 class="text-sm font-semibold text-slate-700 mb-1">暂无AI推荐</h3>
          <p class="text-xs text-slate-400 leading-relaxed mb-4">
            您还未完成AI分诊对话，请先返回分诊页面进行症状描述，或使用自助挂号。
          </p>
          <div class="flex gap-2">
            <button
              type="button"
              @click="router.push('/patient/triage')"
              class="flex-1 py-2 bg-brand-600 text-white text-xs font-medium rounded-lg hover:bg-brand-700 transition-colors"
            >
              前往分诊
            </button>
            <button
              type="button"
              @click="activeTab = 'self'"
              class="flex-1 py-2 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg hover:bg-slate-200 transition-colors"
            >
              自助挂号
            </button>
          </div>
        </div>
      </div>

      <!-- 自助挂号 Tab -->
      <div v-if="activeTab === 'self'" class="px-4 py-4 space-y-4">
        <!-- Department -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 space-y-3">
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1.5">选择科室</label>
            <select
              v-model="selectedDept"
              @change="onDeptChange"
              class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
            >
              <option value="">请选择科室</option>
              <option v-for="d in departments" :key="d.name" :value="d.name">{{ d.name }}</option>
            </select>
          </div>

          <!-- Doctor -->
          <div v-if="selectedDept">
            <label class="block text-xs font-medium text-slate-500 mb-1.5">选择医生</label>
            <select
              v-model="selectedDoctor"
              :disabled="!filteredDoctors.length"
              class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all disabled:opacity-50"
            >
              <option value="">请选择医生</option>
              <option v-for="doc in filteredDoctors" :key="doc.id" :value="doc.id">
                {{ doc.name }} · {{ doc.title }}
              </option>
            </select>
          </div>

          <!-- Date -->
          <div v-if="selectedDept">
            <label class="block text-xs font-medium text-slate-500 mb-1.5">选择日期</label>
            <div class="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
              <button
                v-for="(d, i) in dateOptions"
                :key="i"
                type="button"
                @click="selectedDate = d.value"
                :class="[
                  'flex-shrink-0 w-16 py-2 rounded-xl text-center transition-all',
                  selectedDate === d.value
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100',
                ]"
              >
                <span class="block text-[10px] opacity-70">{{ d.label }}</span>
                <span class="block text-sm font-semibold">{{ d.day }}</span>
              </button>
            </div>
          </div>

          <!-- Time slot -->
          <div v-if="selectedDate">
            <label class="block text-xs font-medium text-slate-500 mb-1.5">选择时段</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="slot in timeSlots"
                :key="slot.value"
                type="button"
                @click="selectedTime = slot.value"
                :disabled="!slot.available"
                :class="[
                  'py-2 rounded-lg text-xs font-medium transition-all',
                  selectedTime === slot.value
                    ? 'bg-brand-600 text-white'
                    : slot.available
                    ? 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                    : 'bg-slate-100 text-slate-300 cursor-not-allowed line-through',
                ]"
              >
                {{ slot.label }}
              </button>
            </div>
          </div>
        </div>

        <!-- Booking summary -->
        <div v-if="canSubmit" class="bg-white rounded-2xl border border-brand-200 shadow-sm overflow-hidden">
          <div class="bg-brand-50 px-4 py-2.5 border-b border-brand-100">
            <span class="text-xs font-semibold text-brand-700">预约信息确认</span>
          </div>
          <div class="p-4 space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">科室</span>
              <span class="text-slate-800 font-medium">{{ selectedDept }}</span>
            </div>
            <div class="flex justify-between text-sm" v-if="selectedDoctor">
              <span class="text-slate-500">医生</span>
              <span class="text-slate-800 font-medium">{{ selectedDoctorName }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">日期</span>
              <span class="text-slate-800 font-medium">{{ selectedDateLabel }}</span>
            </div>
            <div class="flex justify-between text-sm" v-if="selectedTime">
              <span class="text-slate-500">时段</span>
              <span class="text-slate-800 font-medium">{{ selectedTimeLabel }}</span>
            </div>
            <div class="flex justify-between text-sm pt-1 border-t border-slate-100">
              <span class="text-slate-500">排队号</span>
              <span class="text-brand-600 font-semibold">A{{ queueNumber }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">预计等待</span>
              <span class="text-slate-800 font-medium">{{ estimatedWait }} 分钟</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">诊室位置</span>
              <span class="text-slate-800 font-medium">{{ roomLocation }}</span>
            </div>
          </div>
          <div class="px-4 pb-4">
            <button
              type="button"
              @click="submitBooking"
              :disabled="submitting"
              class="w-full py-3 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 transition-colors disabled:opacity-50 shadow-sm shadow-brand-600/20"
            >
              {{ submitting ? '提交中…' : '确认预约' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Existing bookings -->
      <div class="px-4 py-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <div class="w-1.5 h-1.5 rounded-full bg-slate-400" />
            <span class="text-sm font-semibold text-slate-700">我的预约</span>
          </div>
          <button
            type="button"
            @click="loadBookings"
            class="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            刷新
          </button>
        </div>

        <div v-if="bookings.length" class="space-y-2">
          <div
            v-for="b in bookings"
            :key="b.id"
            class="bg-white rounded-xl border border-slate-200 shadow-sm p-3"
          >
            <div class="flex items-start justify-between mb-2">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-slate-800">{{ b.department || b.title || '未命名预约' }}</span>
                  <span
                    :class="[
                      'text-[10px] px-2 py-0.5 rounded-full font-medium',
                      statusClass(b.status),
                    ]"
                  >
                    {{ statusLabel(b.status) }}
                  </span>
                </div>
                <p class="text-xs text-slate-400 mt-0.5">
                  {{ b.doctor ? b.doctor + ' · ' : '' }}{{ b.scheduled_at || b.time || '' }}
                </p>
              </div>
              <button
                v-if="b.status === 'pending' || b.status === 'scheduled'"
                type="button"
                @click="syncHis(b)"
                :disabled="b.syncing"
                class="text-[10px] text-brand-600 bg-brand-50 hover:bg-brand-100 px-2 py-1 rounded-lg transition-colors disabled:opacity-50 flex-shrink-0"
              >
                {{ b.syncing ? '同步中' : '线下挂号同步' }}
              </button>
            </div>
            <div class="flex items-center gap-3 text-[10px] text-slate-400">
              <span v-if="b.queue_number">排队号: {{ b.queue_number }}</span>
              <span v-if="b.room">诊室: {{ b.room }}</span>
            </div>
          </div>
        </div>

        <div v-else class="bg-white rounded-xl border border-dashed border-slate-200 p-6 text-center">
          <p class="text-xs text-slate-400">暂无预约记录</p>
        </div>

        <div class="mt-4 text-center">
          <button
            type="button"
            @click="syncAllHis"
            :disabled="hisSyncing"
            class="px-4 py-2 bg-slate-100 text-slate-600 text-xs font-medium rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
          >
            {{ hisSyncing ? '同步中…' : '🔄 线下挂号同步 (Mock HIS)' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Success modal -->
    <div v-if="showSuccess" class="fixed inset-0 z-30 flex items-center justify-center bg-black/40 px-6">
      <div class="bg-white rounded-2xl w-full max-w-xs p-5 shadow-xl">
        <div class="text-center">
          <div class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h3 class="text-base font-semibold text-slate-800 mb-1">预约成功</h3>
          <p class="text-xs text-slate-500 mb-3">请按时就诊</p>
        </div>
        <div class="bg-slate-50 rounded-xl p-3 space-y-1.5 mb-4">
          <div class="flex justify-between text-xs">
            <span class="text-slate-400">科室</span>
            <span class="text-slate-700 font-medium">{{ successBooking.department }}</span>
          </div>
          <div class="flex justify-between text-xs" v-if="successBooking.doctor">
            <span class="text-slate-400">医生</span>
            <span class="text-slate-700 font-medium">{{ successBooking.doctor }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-slate-400">时间</span>
            <span class="text-slate-700 font-medium">{{ successBooking.time }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-slate-400">排队号</span>
            <span class="text-brand-600 font-semibold">{{ successBooking.queue_number }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-slate-400">诊室</span>
            <span class="text-slate-700 font-medium">{{ successBooking.room }}</span>
          </div>
        </div>
        <button
          type="button"
          @click="closeSuccess"
          class="w-full py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 transition-colors"
        >
          完成
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { usePatientStore } from '../../stores/patient'
import { patientApi } from '../../api/patient'

const router = useRouter()
const route = useRoute()
const patientStore = usePatientStore()

const fontClass = computed(() => patientStore.fontClass)

const activeTab = ref(route.query.from === 'triage' ? 'ai' : 'self')
const bookingLoading = ref(false)
const submitting = ref(false)
const hisSyncing = ref(false)

// AI recommend tab data
const recommendedDepts = ref([])

// Self booking tab data
const departments = ref([
  { name: '内科' },
  { name: '外科' },
  { name: '儿科' },
  { name: '妇产科' },
  { name: '骨科' },
  { name: '眼科' },
  { name: '耳鼻喉科' },
  { name: '皮肤科' },
  { name: '口腔科' },
  { name: '中医科' },
])

const doctorsMap = {
  内科: [
    { id: 'n1', name: '王医生', title: '主任医师' },
    { id: 'n2', name: '李医生', title: '副主任医师' },
    { id: 'n3', name: '张医生', title: '主治医师' },
  ],
  外科: [
    { id: 'w1', name: '陈医生', title: '主任医师' },
    { id: 'w2', name: '刘医生', title: '副主任医师' },
  ],
  儿科: [
    { id: 'e1', name: '赵医生', title: '主任医师' },
    { id: 'e2', name: '孙医生', title: '主治医师' },
  ],
  妇产科: [
    { id: 'f1', name: '周医生', title: '主任医师' },
    { id: 'f2', name: '吴医生', title: '副主任医师' },
  ],
  骨科: [
    { id: 'g1', name: '郑医生', title: '主任医师' },
  ],
  眼科: [
    { id: 'y1', name: '冯医生', title: '副主任医师' },
  ],
  耳鼻喉科: [
    { id: 'r1', name: '许医生', title: '主治医师' },
  ],
  皮肤科: [
    { id: 'd1', name: '何医生', title: '副主任医师' },
  ],
  口腔科: [
    { id: 'k1', name: '吕医生', title: '主治医师' },
  ],
  中医科: [
    { id: 'z1', name: '林医生', title: '主任医师' },
    { id: 'z2', name: '黄医生', title: '副主任医师' },
  ],
}

const selectedDept = ref(route.query.dept || '')
const selectedDoctor = ref('')
const selectedDate = ref('')
const selectedTime = ref('')

const dateOptions = computed(() => {
  const options = []
  const today = new Date()
  const weekLabels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  for (let i = 0; i < 7; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() + i)
    options.push({
      value: d.toISOString().slice(0, 10),
      label: i === 0 ? '今天' : i === 1 ? '明天' : weekLabels[d.getDay()],
      day: `${d.getMonth() + 1}/${d.getDate()}`,
    })
  }
  return options
})

const timeSlots = computed(() => {
  const times = [
    { v: 'morning_08', l: '08:00' },
    { v: 'morning_09', l: '09:00' },
    { v: 'morning_10', l: '10:00' },
    { v: 'morning_11', l: '11:00' },
    { v: 'afternoon_14', l: '14:00' },
    { v: 'afternoon_15', l: '15:00' },
    { v: 'afternoon_16', l: '16:00' },
    { v: 'evening_18', l: '18:00' },
    { v: 'evening_19', l: '19:00' },
  ]
  const seed = (selectedDept.value?.length || 0) + (selectedDate.value?.length || 0)
  return times.map((t, i) => ({
    value: t.v,
    label: t.l,
    available: !((i + seed) % 4 === 0),
  }))
})

const filteredDoctors = computed(() => {
  if (!selectedDept.value) return []
  return doctorsMap[selectedDept.value] || []
})

const selectedDoctorName = computed(() => {
  const doc = filteredDoctors.value.find((d) => d.id === selectedDoctor.value)
  return doc ? `${doc.name} · ${doc.title}` : ''
})

const selectedDateLabel = computed(() => {
  const d = dateOptions.value.find((d) => d.value === selectedDate.value)
  return d ? `${d.label} ${d.day}` : ''
})

const selectedTimeLabel = computed(() => {
  const parts = selectedTime.value?.split('_') || []
  return parts.length === 2 ? `${parts[1]}:00` : ''
})

const queueNumber = computed(() => {
  const seed = (selectedDept.value?.length || 1) + (selectedDate.value?.length || 1) + (selectedTime.value?.length || 1)
  return String(10 + (seed % 40)).padStart(2, '0')
})

const estimatedWait = computed(() => {
  const seed = (selectedDept.value?.length || 1) + (selectedDate.value?.length || 1) + (selectedTime.value?.length || 1)
  return 5 + (seed % 25)
})

const roomLocation = computed(() => {
  if (!selectedDept.value) return '待分配'
  const deptRooms = {
    内科: '门诊3楼 305诊室',
    外科: '门诊3楼 312诊室',
    儿科: '门诊2楼 208诊室',
    妇产科: '门诊2楼 215诊室',
    骨科: '门诊4楼 410诊室',
    眼科: '门诊5楼 502诊室',
    耳鼻喉科: '门诊5楼 508诊室',
    皮肤科: '门诊4楼 415诊室',
    口腔科: '门诊4楼 420诊室',
    中医科: '门诊1楼 108诊室',
  }
  return deptRooms[selectedDept.value] || '待分配'
})

const canSubmit = computed(() => {
  return selectedDept.value && selectedDate.value && selectedTime.value
})

// Bookings list
const bookings = ref([])

// Success modal
const showSuccess = ref(false)
const successBooking = ref({})

// Confidence helpers
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
  return map[level] || '推荐'
}

function statusClass(status) {
  const map = {
    pending: 'bg-amber-100 text-amber-700',
    scheduled: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-slate-100 text-slate-500',
  }
  return map[status] || 'bg-slate-100 text-slate-500'
}

function statusLabel(status) {
  const map = {
    pending: '待就诊',
    scheduled: '已预约',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[status] || status || '未知'
}

function onDeptChange() {
  selectedDoctor.value = ''
}

async function loadBookings() {
  try {
    const res = await patientApi.listBookings()
    bookings.value = (res.bookings || res.data || []).map((b) => ({
      ...b,
      syncing: false,
    }))
  } catch (e) {
    console.error('加载预约列表失败', e)
    bookings.value = []
  }
}

async function loadTriageRecommendations() {
  // Mock: load from triage session if available
  try {
    const sessions = await patientApi.listTriageSessions()
    const list = sessions.sessions || sessions.data || []
    if (list.length) {
      const latest = list[0]
      if (latest.recommended_departments?.length) {
        recommendedDepts.value = latest.recommended_departments.map((d) => ({
          name: d.name || d.department_name,
          confidence: d.confidence || 'medium',
          desc: d.reason || d.description || 'AI智能分诊推荐',
          available: d.available || Math.floor(Math.random() * 8) + 2,
          wait_time: d.wait_time || Math.floor(Math.random() * 20) + 5,
          room: d.room || '待分配',
        }))
        return
      }
    }
  } catch (e) {
    console.warn('加载分诊推荐失败', e)
  }

  // Mock fallback recommendations
  recommendedDepts.value = [
    {
      name: '内科',
      confidence: 'high',
      desc: '根据您描述的症状，内科是最合适的就诊科室',
      available: 5,
      wait_time: 12,
      room: '门诊3楼 305诊室',
    },
    {
      name: '中医科',
      confidence: 'medium',
      desc: '如您希望调理身体，中医科也是不错的选择',
      available: 3,
      wait_time: 25,
      room: '门诊1楼 108诊室',
    },
  ]
}

async function quickBook(dept) {
  bookingLoading.value = true
  try {
    const res = await patientApi.createBooking({
      department: dept.name,
    })

    const booking = res.booking || res.data || {
      id: res.id || 'B' + Date.now(),
      department: dept.name,
      doctor: '待分配',
      scheduled_at: new Date().toLocaleString('zh-CN'),
      queue_number: 'A' + (10 + Math.floor(Math.random() * 40)),
      room: dept.room || '待分配',
      status: 'pending',
    }

    successBooking.value = {
      department: booking.department || dept.name,
      doctor: booking.doctor_name || booking.doctor || '待分配',
      time: `${booking.slot_date || ''} ${booking.slot_time || ''}`.trim() || new Date().toLocaleString('zh-CN'),
      queue_number: booking.queue_number || 'A--',
      room: booking.room_name || booking.room || dept.room || '待分配',
    }
    showSuccess.value = true
    loadBookings()
  } catch (e) {
    console.error('快速预约失败', e)
    // Mock fallback
    successBooking.value = {
      department: dept.name,
      doctor: '待分配',
      time: new Date().toLocaleString('zh-CN'),
      queue_number: 'A' + (10 + Math.floor(Math.random() * 40)),
      room: dept.room || '待分配',
    }
    showSuccess.value = true
    loadBookings()
  } finally {
    bookingLoading.value = false
  }
}

async function submitBooking() {
  if (!canSubmit.value) return
  submitting.value = true

  const body = {
    department: selectedDept.value,
    doctor_id: selectedDoctor.value || null,
    slot_date: selectedDate.value,
    slot_time: selectedTime.value,
  }

  try {
    const res = await patientApi.createBooking(body)
    const booking = res.booking || res.data || body

    successBooking.value = {
      department: booking.department || selectedDept.value,
      doctor: booking.doctor_name || selectedDoctorName.value || '待分配',
      time: `${booking.slot_date || selectedDateLabel.value} ${booking.slot_time || selectedTimeLabel.value}`,
      queue_number: booking.queue_number || ('A' + queueNumber.value),
      room: booking.room_name || roomLocation.value,
    }
    showSuccess.value = true
    loadBookings()

    // Reset form
    selectedDoctor.value = ''
    selectedDate.value = ''
    selectedTime.value = ''
  } catch (e) {
    console.error('预约提交失败', e)
    // Mock fallback
    successBooking.value = {
      department: selectedDept.value,
      doctor: selectedDoctorName.value || '待分配',
      time: `${selectedDateLabel.value} ${selectedTimeLabel.value}`,
      queue_number: body.queue_number,
      room: roomLocation.value,
    }
    showSuccess.value = true
    loadBookings()
  } finally {
    submitting.value = false
  }
}

async function syncHis(booking) {
  booking.syncing = true
  try {
    await patientApi.syncBookingHis(booking.id)
    alert(`挂号同步成功！预约 ${booking.department} 已同步至线下HIS系统。`)
  } catch (e) {
    console.error('HIS同步失败', e)
    alert('Mock: 线下挂号同步已完成（模拟）')
  } finally {
    booking.syncing = false
  }
}

async function syncAllHis() {
  if (!bookings.value.length) return
  hisSyncing.value = true
  try {
    const results = await Promise.allSettled(
      bookings.value.map((b) => patientApi.syncBookingHis(b.id))
    )
    const successCount = results.filter((r) => r.status === 'fulfilled').length
    alert(`Mock: 已同步 ${successCount}/${bookings.value.length} 条预约至HIS系统`)
  } catch (e) {
    console.error('批量HIS同步失败', e)
    alert(`Mock: 已同步 ${bookings.value.length} 条预约至HIS系统`)
  } finally {
    hisSyncing.value = false
  }
}

function closeSuccess() {
  showSuccess.value = false
}

onMounted(() => {
  loadBookings()
  loadTriageRecommendations()
})
</script>
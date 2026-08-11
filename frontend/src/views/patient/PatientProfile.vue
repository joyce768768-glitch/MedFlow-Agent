<template>
  <div class="min-h-screen bg-slate-50 pb-20" :class="fontClass">
    <div class="w-full max-w-md mx-auto">
      <header class="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-slate-100">
        <div class="px-4 py-3">
          <h1 class="text-base font-semibold text-slate-800">我的</h1>
        </div>
      </header>

      <main class="px-4 py-4 space-y-4">
        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-4 py-4 flex items-center gap-4">
            <div class="w-14 h-14 rounded-full bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center text-white text-xl font-semibold flex-shrink-0">
              {{ avatarText }}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-base font-semibold text-slate-800">{{ patientStore.patient?.name || '患者' }}</p>
              <p class="text-xs text-slate-400 mt-0.5">患者ID：{{ patientStore.patient?.id || patientStore.patient?.patient_id || '--' }}</p>
              <div class="mt-1.5 flex items-center gap-1.5">
                <div class="flex items-center gap-1 px-2 py-0.5 bg-brand-50 rounded-md">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
                    <line x1="1" y1="10" x2="23" y2="10" />
                  </svg>
                  <span class="text-xs font-mono text-brand-600">{{ maskedCardNumber }}</span>
                </div>
              </div>
            </div>
            <router-link
              to="/patient/reports"
              class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </router-link>
          </div>
        </section>

        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-50 flex items-center gap-2">
            <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
            <h2 class="text-sm font-semibold text-slate-700">我的服务</h2>
          </div>
          <div class="divide-y divide-slate-50">
            <router-link
              v-for="item in menuItems"
              :key="item.key"
              :to="item.path"
              class="flex items-center gap-3 px-4 py-3.5 hover:bg-slate-50 transition-colors"
            >
              <div class="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center text-brand-500 text-sm">
                {{ item.icon }}
              </div>
              <span class="flex-1 text-sm text-slate-700">{{ item.label }}</span>
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </router-link>
          </div>
        </section>

        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-50 flex items-center gap-2">
            <div class="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <h2 class="text-sm font-semibold text-slate-700">护士协助记录</h2>
            <span class="text-xs text-slate-400 ml-auto">{{ nurseRequests.length }} 条</span>
          </div>
          <div v-if="nurseRequests.length" class="divide-y divide-slate-50">
            <div
              v-for="(req, idx) in nurseRequests"
              :key="idx"
              class="px-4 py-3 flex items-start gap-3"
            >
              <div
                :class="[
                  'w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0',
                  req.status === 'done' ? 'bg-green-50 text-green-500' : req.status === 'pending' ? 'bg-amber-50 text-amber-500' : 'bg-slate-50 text-slate-400',
                ]"
              >
                {{ req.icon }}
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-slate-700">{{ req.title }}</p>
                <p class="text-xs text-slate-400 mt-0.5">{{ req.time }}</p>
              </div>
              <span
                :class="[
                  'text-[10px] px-2 py-0.5 rounded-full flex-shrink-0',
                  req.status === 'done'
                    ? 'bg-green-50 text-green-600'
                    : req.status === 'pending'
                    ? 'bg-amber-50 text-amber-600'
                    : 'bg-slate-50 text-slate-500',
                ]"
              >
                {{ req.status === 'done' ? '已完成' : req.status === 'pending' ? '处理中' : '待处理' }}
              </span>
            </div>
          </div>
          <div v-else class="px-4 py-8 text-center text-sm text-slate-400">
            暂无护士协助记录
          </div>
        </section>

        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-50 flex items-center gap-2">
            <div class="w-1.5 h-1.5 rounded-full bg-brand-500" />
            <h2 class="text-sm font-semibold text-slate-700">适老化设置</h2>
          </div>
          <div class="px-4 py-4 space-y-4">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-slate-700">字号切换</span>
                <span class="text-xs text-slate-400">{{ fontScaleLabels[patientStore.fontScale] }}</span>
              </div>
              <div class="flex items-center gap-2 bg-slate-100 rounded-xl p-0.5">
                <button
                  v-for="s in fontScaleOptions"
                  :key="s.value"
                  type="button"
                  @click="patientStore.setFontScale(s.value)"
                  :class="[
                    'flex-1 py-2 rounded-lg font-medium transition-all text-center',
                    patientStore.fontScale === s.value
                      ? 'bg-white text-brand-600 shadow-sm'
                      : 'text-slate-400 hover:text-slate-600',
                  ]"
                >
                  <span :class="[s.previewClass]">{{ s.label }}</span>
                </button>
              </div>
            </div>

            <div class="pt-2 border-t border-slate-50">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm text-slate-700">高对比度模式</p>
                  <p class="text-xs text-slate-400 mt-0.5">预计版本支持</p>
                </div>
                <div class="w-10 h-6 rounded-full bg-slate-200 flex items-center p-0.5 cursor-not-allowed opacity-60">
                  <div class="w-5 h-5 rounded-full bg-white shadow-sm" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="divide-y divide-slate-50">
            <button
              type="button"
              @click="showPrivacyModal = true"
              class="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-slate-50 transition-colors text-left"
            >
              <div class="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-sm">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <span class="flex-1 text-sm text-slate-700">隐私协议</span>
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
            <button
              type="button"
              @click="showAboutModal = true"
              class="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-slate-50 transition-colors text-left"
            >
              <div class="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-sm">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </div>
              <span class="flex-1 text-sm text-slate-700">关于 MedFlow</span>
              <span class="text-xs text-slate-400">v{{ version }}</span>
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          </div>
        </section>

        <button
          type="button"
          @click="handleLogout"
          class="w-full py-3.5 bg-white rounded-2xl border border-red-100 text-sm font-medium text-red-500 hover:bg-red-50 transition-colors shadow-sm"
        >
          退出登录
        </button>

        <div class="px-2 py-2">
          <p class="text-[10px] text-slate-400 text-center">
            MedFlow · AI 医院问诊系统
          </p>
        </div>
      </main>
    </div>

    <Teleport to="body">
      <transition name="fade">
        <div
          v-if="showPrivacyModal"
          class="fixed inset-0 z-30 flex items-center justify-center px-6"
          @click.self="showPrivacyModal = false"
        >
          <div class="absolute inset-0 bg-black/40" />
          <div class="relative w-full max-w-md bg-white rounded-2xl overflow-hidden shadow-xl">
            <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 class="text-base font-semibold text-slate-800">隐私协议</h3>
              <button
                type="button"
                @click="showPrivacyModal = false"
                class="w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div class="px-5 py-4 max-h-[60vh] overflow-y-auto text-xs text-slate-600 leading-relaxed space-y-3">
              <div>
                <p class="font-medium text-slate-800 mb-1">1. 信息收集</p>
                <p>本系统仅收集为您提供医疗服务所必需的个人信息，包括但不限于：姓名、患者ID、就诊卡信息、就诊记录等。</p>
              </div>
              <div>
                <p class="font-medium text-slate-800 mb-1">2. 信息使用</p>
                <p>收集的信息仅用于医疗服务提供、诊疗记录管理、健康档案建立等医疗相关用途，绝不用于其他商业目的。</p>
              </div>
              <div>
                <p class="font-medium text-slate-800 mb-1">3. 信息保护</p>
                <p>我们采用严格的数据加密和访问控制措施，确保您的个人健康信息安全。所有数据传输均通过加密通道。</p>
              </div>
              <div>
                <p class="font-medium text-slate-800 mb-1">4. AI辅助说明</p>
                <p>本系统提供的AI分诊和导诊建议仅作为参考，不构成医疗诊断。最终诊疗方案以医生的专业判断为准。</p>
              </div>
              <div>
                <p class="font-medium text-slate-800 mb-1">5. 您的权利</p>
                <p>您有权随时查阅、更正您的个人信息，或要求删除您的账户数据。如有任何隐私相关问题，请联系医院管理员。</p>
              </div>
            </div>
            <div class="px-5 py-3 border-t border-slate-100">
              <button
                type="button"
                @click="showPrivacyModal = false"
                class="w-full py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-xl transition-colors"
              >
                我已阅读
              </button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <Teleport to="body">
      <transition name="fade">
        <div
          v-if="showAboutModal"
          class="fixed inset-0 z-30 flex items-center justify-center px-6"
          @click.self="showAboutModal = false"
        >
          <div class="absolute inset-0 bg-black/40" />
          <div class="relative w-full max-w-sm bg-white rounded-2xl overflow-hidden shadow-xl p-6 text-center">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center mx-auto mb-4 text-white text-2xl">
              🏥
            </div>
            <h3 class="text-lg font-semibold text-slate-800">MedFlow</h3>
            <p class="text-xs text-slate-400 mt-1">AI 医院问诊系统</p>
            <div class="mt-4 space-y-1 text-xs text-slate-500">
              <p>版本：{{ version }}</p>
              <p>© 2026 MedFlow Team</p>
              <p class="mt-2">让优质医疗触手可及</p>
            </div>
            <button
              type="button"
              @click="showAboutModal = false"
              class="w-full mt-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-xl transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </transition>
    </Teleport>

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

const version = '1.0.0'

const fontScaleLabels = { 0: '标准', 1: '大', 2: '超大' }

const fontScaleOptions = [
  { label: 'A', value: 0, previewClass: 'text-sm' },
  { label: 'A+', value: 1, previewClass: 'text-base' },
  { label: 'A++', value: 2, previewClass: 'text-lg' },
]

const avatarText = computed(() => {
  const name = patientStore.patient?.name
  if (!name) return '患'
  return name.charAt(0)
})

const maskedCardNumber = computed(() => {
  const card = patientStore.patient?.medical_card_number || ''
  if (!card) return '6222******0001'
  if (card.length <= 8) return card
  return card.slice(0, 4) + '****' + card.slice(-4)
})

const menuItems = [
  { key: 'reports', icon: '📋', label: '就诊记录', path: '/patient/reports' },
]

const showPrivacyModal = ref(false)
const showAboutModal = ref(false)

const nurseRequests = ref([])

const mockNurseRequests = [
  { icon: '💉', title: '静脉输液', time: '2026-08-10 09:30', status: 'done' },
  { icon: '🌡️', title: '体温测量', time: '2026-08-10 14:00', status: 'done' },
  { icon: '🩹', title: '伤口换药', time: '2026-08-11 08:00', status: 'pending' },
]

async function loadNurseRequests() {
  try {
    const res = await patientApi.getMe()
    if (res && res.nurse_requests && res.nurse_requests.length) {
      nurseRequests.value = res.nurse_requests.map((r) => ({
        icon: r.icon || '🩺',
        title: r.title || r.type || '护士协助',
        time: r.time || r.created_at || '',
        status: r.status || 'pending',
      }))
    } else {
      nurseRequests.value = mockNurseRequests
    }
  } catch (e) {
    nurseRequests.value = mockNurseRequests
  }
}

function handleLogout() {
  patientStore.logout()
  router.push('/patient/login')
}

onMounted(() => {
  loadNurseRequests()
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
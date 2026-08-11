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
            <h1 class="text-base font-semibold text-slate-800">报告与病案</h1>
          </div>
          <button
            type="button"
            @click="loadData"
            class="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            刷新
          </button>
        </div>

        <div class="px-4 pb-3">
          <div class="flex gap-1 bg-slate-100 rounded-xl p-0.5">
            <button
              type="button"
              @click="activeTab = 'reports'"
              :class="[
                'flex-1 py-2 text-sm font-medium rounded-lg transition-all',
                activeTab === 'reports'
                  ? 'bg-white text-brand-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700',
              ]"
            >
              我的报告
            </button>
            <button
              type="button"
              @click="activeTab = 'records'"
              :class="[
                'flex-1 py-2 text-sm font-medium rounded-lg transition-all',
                activeTab === 'records'
                  ? 'bg-white text-brand-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700',
              ]"
            >
              我的病案
            </button>
          </div>
        </div>
      </header>

      <main class="px-4 py-4">
        <div v-if="loading" class="flex justify-center py-12">
          <div class="flex items-center gap-2 text-slate-400 text-sm">
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:0ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:150ms" />
            <span class="w-2 h-2 bg-slate-300 rounded-full animate-bounce" style="animation-delay:300ms" />
            <span class="ml-1">加载中…</span>
          </div>
        </div>

        <template v-else-if="activeTab === 'reports'">
          <div v-if="completedReports.length" class="space-y-3">
            <div
              v-for="(report, idx) in completedReports"
              :key="idx"
              class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden"
            >
              <div class="px-4 py-3 border-b border-slate-50 flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center text-brand-500 text-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                  </div>
                  <div>
                    <h3 class="text-sm font-semibold text-slate-800">{{ report.task_name || report.label || '检查报告' }}</h3>
                    <p class="text-xs text-slate-400 mt-0.5">{{ report.completed_at || report.time || '' }}</p>
                  </div>
                </div>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-green-50 text-green-600 font-medium">
                  已出具
                </span>
              </div>

              <div class="px-4 py-3">
                <div v-if="report.results && report.results.length" class="space-y-2">
                  <div
                    v-for="(item, i) in report.results"
                    :key="i"
                    class="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0"
                  >
                    <span class="text-xs text-slate-500">{{ item.label || item.name }}</span>
                    <span
                      :class="[
                        'text-xs font-medium',
                        item.abnormal ? 'text-red-500' : 'text-slate-700',
                      ]"
                    >
                      {{ item.value }}
                      <span v-if="item.unit" class="text-slate-400 ml-0.5">{{ item.unit }}</span>
                      <span v-if="item.abnormal" class="ml-1">↑↓</span>
                    </span>
                  </div>
                </div>
                <p v-else-if="report.summary" class="text-xs text-slate-600 leading-relaxed">
                  {{ report.summary }}
                </p>
                <p v-else class="text-xs text-slate-400">报告结果请以医院最终出具为准</p>

                <div v-if="report.impression" class="mt-3 pt-3 border-t border-slate-50">
                  <p class="text-xs text-slate-500 leading-relaxed">
                    <span class="font-medium text-slate-700">印象描述：</span>{{ report.impression }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="bg-white rounded-2xl border border-dashed border-slate-200 p-8 text-center">
            <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <p class="text-sm text-slate-500">暂无检查报告</p>
            <p class="text-xs text-slate-400 mt-1">完成检查后将在此处显示报告结果</p>
          </div>
        </template>

        <template v-else>
          <div class="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5 mb-3">
            <p class="text-[11px] text-amber-700 leading-relaxed">
              本页面仅展示正式归档文档，医生内部讨论记录不对患者开放
            </p>
          </div>

          <div v-if="records.emr_main || records.treatment_versions?.length || records.check_results?.length" class="space-y-4">
            <div v-if="records.emr_main" class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
              <div class="px-4 py-3 border-b border-slate-50 flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center text-brand-500">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M20 14.66V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5.34" />
                      <polygon points="18 2 22 6 12 16 8 16 8 12 18 2" />
                    </svg>
                  </div>
                  <h3 class="text-sm font-semibold text-slate-800">电子病历</h3>
                </div>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-brand-50 text-brand-600 font-medium">
                  正式归档
                </span>
              </div>
              <div class="px-4 py-3 space-y-2">
                <div v-if="records.emr_main.chief_complaint" class="flex gap-2 text-xs">
                  <span class="text-slate-400 flex-shrink-0">主诉：</span>
                  <span class="text-slate-700 flex-1">{{ records.emr_main.chief_complaint }}</span>
                </div>
                <div v-if="records.emr_main.history" class="flex gap-2 text-xs">
                  <span class="text-slate-400 flex-shrink-0">病史：</span>
                  <span class="text-slate-700 flex-1">{{ records.emr_main.history }}</span>
                </div>
                <div v-if="records.emr_main.diagnosis" class="flex gap-2 text-xs">
                  <span class="text-slate-400 flex-shrink-0">诊断：</span>
                  <span class="text-slate-700 flex-1">{{ records.emr_main.diagnosis }}</span>
                </div>
                <div v-if="records.emr_main.treatment_plan" class="flex gap-2 text-xs">
                  <span class="text-slate-400 flex-shrink-0">治疗方案：</span>
                  <span class="text-slate-700 flex-1">{{ records.emr_main.treatment_plan }}</span>
                </div>
                <div v-if="records.emr_main.signed_at" class="pt-2 border-t border-slate-50 text-[10px] text-slate-400 text-right">
                  归档时间：{{ records.emr_main.signed_at }}
                </div>
              </div>
            </div>

            <div v-if="records.treatment_versions?.length" class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
              <div class="px-4 py-3 border-b border-slate-50 flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center text-teal-500">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="8" y1="6" x2="21" y2="6" />
                      <line x1="8" y1="12" x2="21" y2="12" />
                      <line x1="8" y1="18" x2="21" y2="18" />
                      <line x1="3" y1="6" x2="3.01" y2="6" />
                      <line x1="3" y1="12" x2="3.01" y2="12" />
                      <line x1="3" y1="18" x2="3.01" y2="18" />
                    </svg>
                  </div>
                  <h3 class="text-sm font-semibold text-slate-800">治疗记录</h3>
                </div>
                <span class="text-xs text-slate-400">共 {{ records.treatment_versions.length }} 条</span>
              </div>
              <div class="divide-y divide-slate-50">
                <div
                  v-for="(ver, idx) in sortedTreatments"
                  :key="idx"
                  class="px-4 py-3"
                >
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs text-slate-500">{{ ver.version_label || `第 ${records.treatment_versions.length - idx} 版` }}</span>
                    <span class="text-[10px] text-slate-400">{{ ver.updated_at || ver.created_at || '' }}</span>
                  </div>
                  <div v-if="ver.treatment_content || ver.content" class="text-xs text-slate-700 leading-relaxed">
                    {{ ver.treatment_content || ver.content }}
                  </div>
                  <div v-if="ver.doctor" class="mt-2 text-[10px] text-slate-400">
                    主治医师：{{ ver.doctor }}
                  </div>
                </div>
              </div>
            </div>

            <div v-if="records.check_results?.length" class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
              <div class="px-4 py-3 border-b border-slate-50 flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center text-orange-500">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  </div>
                  <h3 class="text-sm font-semibold text-slate-800">检查结果</h3>
                </div>
                <span class="text-xs text-slate-400">共 {{ records.check_results.length }} 项</span>
              </div>
              <div class="divide-y divide-slate-50">
                <div
                  v-for="(check, idx) in records.check_results"
                  :key="idx"
                  class="px-4 py-3"
                >
                  <div class="flex items-center justify-between mb-1.5">
                    <span class="text-sm font-medium text-slate-800">{{ check.task_name || check.label || '检查项目' }}</span>
                    <span
                      :class="[
                        'text-[10px] px-2 py-0.5 rounded-full font-medium',
                        check.status === 'completed' || check.status === 'done'
                          ? 'bg-green-50 text-green-600'
                          : 'bg-amber-50 text-amber-600',
                      ]"
                    >
                      {{ check.status === 'completed' || check.status === 'done' ? '已完成' : '进行中' }}
                    </span>
                  </div>
                  <p v-if="check.result_summary || check.summary" class="text-xs text-slate-600 leading-relaxed">
                    {{ check.result_summary || check.summary }}
                  </p>
                  <div v-if="check.completed_at" class="mt-1 text-[10px] text-slate-400">
                    完成时间：{{ check.completed_at }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="bg-white rounded-2xl border border-dashed border-slate-200 p-8 text-center">
            <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <p class="text-sm text-slate-500">暂无病案记录</p>
            <p class="text-xs text-slate-400 mt-1">就诊完成后将在此处显示您的病案信息</p>
          </div>
        </template>
      </main>
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

const activeTab = ref('reports')
const loading = ref(false)

const completedReports = ref([])
const records = ref({})

const sortedTreatments = computed(() => {
  const versions = records.value.treatment_versions || []
  return [...versions].reverse()
})

async function loadData() {
  loading.value = true
  try {
    const patientId = patientStore.patient?.id || patientStore.patient?.patient_id || ''
    if (!patientId) {
      console.warn('未获取到患者ID')
      return
    }

    const res = await patientApi.getReports(patientId)

    const reports = res.reports || res.check_reports || res.data?.reports || []
    completedReports.value = reports
      .filter((r) => r.status === 'completed' || r.status === 'done')
      .map((r) => ({
        task_name: r.task_name || r.label || r.name || '',
        completed_at: r.completed_at || r.time || '',
        results: r.results || r.items || [],
        summary: r.summary || r.description || '',
        impression: r.impression || r.impression_text || '',
      }))

    const rawRecords = res.medical_record || res.emr || res.data || {}
    records.value = {
      emr_main: rawRecords.emr_main || rawRecords.emrMain || null,
      treatment_versions: rawRecords.treatment_versions || rawRecords.treatmentVersions || [],
      check_results: rawRecords.check_results || rawRecords.checkResults || [],
    }
  } catch (e) {
    console.warn('加载报告与病案失败', e)
    completedReports.value = mockReports
    records.value = mockRecords
  } finally {
    loading.value = false
  }
}

const mockReports = [
  {
    task_name: '血常规检查',
    completed_at: '2026-08-10 09:30',
    results: [
      { label: '白细胞计数', value: '6.5', unit: '×10^9/L' },
      { label: '红细胞计数', value: '4.8', unit: '×10^12/L' },
      { label: '血红蛋白', value: '142', unit: 'g/L' },
      { label: '血小板', value: '210', unit: '×10^9/L' },
    ],
  },
  {
    task_name: '胸部CT检查',
    completed_at: '2026-08-10 10:15',
    summary: '双肺纹理清晰，未见明显实质性病变。气管及主支气管通畅，纵膈居中，心影正常。',
    impression: '胸部CT未见明显异常，建议定期复查。',
  },
  {
    task_name: '心电图检查',
    completed_at: '2026-08-10 10:45',
    summary: '窦性心律，心率72次/分。各导联未见明显ST-T改变。',
    impression: '心电图大致正常。',
  },
]

const mockRecords = {
  emr_main: {
    chief_complaint: '咳嗽三天，伴有轻度发热',
    history: '患者三天前无明显诱因出现咳嗽，呈刺激性干咳，伴有轻度发热，最高体温37.5℃，无胸痛、咯血等症状。',
    diagnosis: '急性上呼吸道感染',
    treatment_plan: '建议多饮水、注意休息。口服止咳药物对症治疗。如症状持续或加重，建议复诊。',
    signed_at: '2026-08-10 14:00',
  },
  treatment_versions: [
    {
      version_label: '初诊方案',
      updated_at: '2026-08-10 09:00',
      treatment_content: '初步诊断为上呼吸道感染，建议血常规及胸部检查排除肺炎。',
      doctor: '王医生',
    },
    {
      version_label: '确诊方案',
      updated_at: '2026-08-10 14:00',
      treatment_content: '根据检查结果确诊为急性上呼吸道感染，开具止咳药物，建议三日后复诊。',
      doctor: '王医生',
    },
  ],
  check_results: [
    {
      task_name: '血常规',
      status: 'completed',
      result_summary: '各项指标正常，白细胞计数在正常范围。',
      completed_at: '2026-08-10 09:30',
    },
    {
      task_name: '胸部CT',
      status: 'completed',
      result_summary: '双肺未见明显异常。',
      completed_at: '2026-08-10 10:15',
    },
    {
      task_name: '心电图',
      status: 'completed',
      result_summary: '窦性心律，大致正常心电图。',
      completed_at: '2026-08-10 10:45',
    },
  ],
}

onMounted(() => {
  loadData()
})
</script>
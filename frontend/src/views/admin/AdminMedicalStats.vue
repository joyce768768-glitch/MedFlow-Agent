<template>
  <div>
    <!-- 顶部：说明 + 提问入口 -->
    <div class="flex items-center justify-between mb-4 gap-4">
      <p class="text-sm text-slate-500">医疗统计 Data Agent：用自然语言提问，Agent 自动拆解为多节报表（每节只走语义视图编排链路，异常由声明式规则机判）</p>
    </div>

    <!-- 提问区 -->
    <div class="bg-white rounded-xl shadow-card p-4 mb-4">
      <div class="flex gap-2">
        <input
          v-model="question"
          class="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500/20 focus:outline-none"
          placeholder="例如：本周检验周转异常的科室有哪些？"
          @keyup.enter="generate"
        />
        <button
          @click="generate"
          :disabled="loading || !question.trim()"
          class="shrink-0 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >{{ loading ? '生成中…' : '生成报表' }}</button>
      </div>
      <div class="flex flex-wrap gap-2 mt-3">
        <button
          v-for="q in PRESETS"
          :key="q"
          @click="question = q"
          class="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded-full text-xs text-slate-600 transition-colors"
        >{{ q }}</button>
      </div>
      <p v-if="loading" class="text-xs text-slate-400 mt-3">报表需要多轮 LLM 调用（规划 → 逐节查询 → 汇总），预计 10-40 秒…</p>
      <p v-if="error" class="text-sm text-red-600 mt-3">{{ error }}</p>
    </div>

    <!-- 报表 -->
    <div v-if="report" class="space-y-4">
      <!-- 报表头 -->
      <div class="bg-white rounded-xl shadow-card p-5">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold text-slate-800">{{ report.title }}</h2>
            <p class="text-sm text-slate-500 mt-1">主问题：{{ report.question }}</p>
          </div>
          <div class="text-right shrink-0 space-y-1">
            <p class="text-xs text-slate-400">{{ report.generated_at }}</p>
            <span class="inline-block px-2 py-0.5 rounded-full text-xs bg-brand-50 text-brand-700">规划：{{ plannerLabel }}</span>
          </div>
        </div>
        <div class="flex gap-4 mt-3 text-xs text-slate-400">
          <span>共 {{ report.stats.sections_total }} 节</span>
          <span class="text-emerald-600">answered {{ report.stats.sections_answered }}</span>
          <span v-if="report.stats.sections_blocked" class="text-red-500">拦截/无视图 {{ report.stats.sections_blocked }}</span>
          <span v-if="report.summary_degraded" class="text-amber-600">汇总降级（机械拼装）</span>
        </div>
      </div>

      <!-- 汇总 + 洞察 -->
      <div class="bg-white rounded-xl shadow-card p-5">
        <h3 class="text-sm font-semibold text-slate-700 mb-2">汇总</h3>
        <p class="text-sm text-slate-700 leading-relaxed">{{ report.summary }}</p>
        <ul v-if="report.insights?.length" class="mt-3 space-y-1.5">
          <li v-for="(ins, i) in report.insights" :key="'i' + i" class="flex gap-2 text-sm text-slate-600">
            <span class="text-brand-600 shrink-0">◆</span>{{ ins }}
          </li>
        </ul>
        <ul v-if="report.insights_machine?.length" class="mt-3 space-y-1.5">
          <li v-for="(ins, i) in report.insights_machine" :key="'m' + i" class="flex gap-2 text-sm text-red-700 bg-red-50 rounded px-2.5 py-1.5">
            <span class="shrink-0">⚠</span>{{ ins }}
          </li>
        </ul>
      </div>

      <!-- 各节 -->
      <div v-for="(sec, i) in report.sections" :key="'s' + i" class="bg-white rounded-xl shadow-card overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3 bg-slate-50 border-b border-slate-100">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ i + 1 }}. {{ sec.question }}</p>
            <p v-if="sec.rationale" class="text-xs text-slate-400 mt-0.5">{{ sec.rationale }}</p>
          </div>
          <div class="flex items-center gap-2 shrink-0 ml-3">
            <span v-if="sec.view_name" class="px-2 py-0.5 rounded-full text-xs bg-brand-50 text-brand-700">{{ sec.view_name }}</span>
            <span class="px-2 py-0.5 rounded-full text-xs" :class="stageClass(sec.stage)">{{ stageLabel(sec.stage) }}</span>
          </div>
        </div>

        <div class="px-5 py-4 space-y-4">
          <!-- 叙述 -->
          <p class="text-sm text-slate-700 leading-relaxed">{{ sec.reply }}</p>

          <!-- 异常标注（机判） -->
          <div v-for="(a, ai) in sec.anomalies || []" :key="'a' + ai" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
            <p class="text-sm font-semibold text-red-700">⚠ {{ a.label }}：{{ a.describe }}</p>
            <p class="text-xs text-red-600/80 mt-1">判定规则：{{ a.describe }}（{{ a.unit ? `阈值 ${a.threshold} ${a.unit}` : `阈值 ${a.threshold} ` }}，命中 {{ a.matched_count }} 行）</p>
            <p v-if="a.basis" class="text-xs text-red-600/60 mt-0.5">依据：{{ a.basis }}</p>
          </div>

          <!-- 数据表 -->
          <div v-if="sec.data?.rows?.length" class="overflow-x-auto rounded-lg border border-slate-100">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-slate-50 text-slate-500 text-xs">
                  <th v-for="c in sec.data.columns" :key="c" class="text-left font-medium px-3 py-2 whitespace-nowrap">{{ c }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, ri) in sec.data.rows"
                  :key="ri"
                  class="border-t border-slate-50"
                  :class="isFlagged(sec, row) ? 'bg-red-50/70' : ''"
                >
                  <td v-for="(c, ci) in sec.data.columns" :key="ci" class="px-3 py-1.5 text-slate-700 tabular-nums whitespace-nowrap">{{ fmt(row[ci]) }}</td>
                </tr>
              </tbody>
            </table>
            <p class="px-3 py-1.5 text-xs text-slate-400 border-t border-slate-50">共 {{ sec.data.row_count }} 行</p>
          </div>

          <!-- SQL 折叠（依据可溯） -->
          <details v-if="sec.sql" class="text-xs text-slate-400">
            <summary class="cursor-pointer hover:text-slate-600 select-none">实际执行的 SQL（provenance 可溯）</summary>
            <pre class="mt-1.5 bg-slate-50 rounded p-2.5 overflow-x-auto text-[11px] leading-relaxed">{{ sec.sql }}</pre>
          </details>
        </div>
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="!loading && !error" class="bg-white rounded-xl p-10 text-center text-slate-400 text-sm">
      输入问题生成报表——Agent 会把问题拆解为多个统计子问题，逐节查询语义视图后汇总
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '../../api'

// 预置演示问题：覆盖「异常科室识别」（命中 TAT 视图 + 声明式异常规则）与综合经营视角
const PRESETS = [
  '本周检验周转异常的科室有哪些？',
  '本周检验科运营情况怎么样？',
  '最近一周 MDT 会诊活跃度如何？',
]

const question = ref('')
const loading = ref(false)
const error = ref('')
const report = ref(null)

const plannerLabel = computed(() => {
  const map = {
    llm: 'LLM 拆节',
    llm_retry: 'LLM 拆节（重试）',
    fallback_single_section: '退化单节直查',
  }
  return map[report.value?.planner] || report.value?.planner || '-'
})

async function generate() {
  const q = question.value.trim()
  if (!q || loading.value) return
  loading.value = true
  error.value = ''
  report.value = null
  try {
    // 报表需要多轮 LLM 调用，超时放宽到 120s（axios 实例默认 15s）
    const res = await api.post('/semantic/report', { question: q }, { timeout: 120000 })
    report.value = res.data
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = typeof detail === 'string'
      ? detail
      : (detail?.blocked_by ? `查询被机器校验拦截：${JSON.stringify(detail.violations)}` : (err.response?.data?.message || err.message || '报表生成失败'))
  } finally {
    loading.value = false
  }
}

function stageLabel(stage) {
  return { answered: '已回答', blocked: '已拦截', no_view: '无对应视图' }[stage] || stage || '-'
}
function stageClass(stage) {
  return {
    answered: 'bg-emerald-50 text-emerald-700',
    blocked: 'bg-red-50 text-red-600',
    no_view: 'bg-amber-50 text-amber-700',
  }[stage] || 'bg-slate-100 text-slate-500'
}

// 命中异常规则的行标红（JSON 序列化比对，兼容跨 JSON 边界的行匹配）
const flaggedSets = computed(() => {
  const map = new Map()
  for (const sec of report.value?.sections || []) {
    const set = new Set()
    for (const a of sec.anomalies || []) {
      for (const m of a.matched || []) set.add(JSON.stringify(m.row))
    }
    map.set(sec, set)
  }
  return map
})
function isFlagged(sec, row) {
  return flaggedSets.value.get(sec)?.has(JSON.stringify(row)) || false
}

function fmt(v) {
  if (v == null) return '-'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, '')
  return String(v)
}
</script>

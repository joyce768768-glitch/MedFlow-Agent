<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">归档病案查阅</h2>
        <p class="text-sm text-slate-500">
          就诊结束冻结后的病案快照，<span class="text-red-600 font-medium">只读查阅</span>，禁止篡改原始留痕
        </p>
      </div>
      <div class="text-xs text-slate-400 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded">
        Mock 模拟：数据从 patients 内存派生，未做真实归档冷存储
      </div>
    </div>

    <!-- 筛选条 -->
    <div class="bg-white rounded-xl shadow-sm p-4 mb-4">
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block text-xs text-slate-500 mb-1">患者ID</label>
          <input v-model="filters.patient_id" @keyup.enter="load" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="如 p001" />
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">主治医生ID</label>
          <input v-model="filters.doctor_id" @keyup.enter="load" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="如 u_att_01" />
        </div>
        <div class="flex items-end gap-2">
          <button @click="load" class="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">查询</button>
          <button @click="resetFilters" class="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-50">重置</button>
        </div>
      </div>
    </div>

    <!-- 病案列表 -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden mb-4">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3 text-left">患者ID</th>
            <th class="px-4 py-3 text-left">姓名</th>
            <th class="px-4 py-3 text-left">就诊状态</th>
            <th class="px-4 py-3 text-left">病历定稿</th>
            <th class="px-4 py-3 text-left">主治医生</th>
            <th class="px-4 py-3 text-left">诊疗版本</th>
            <th class="px-4 py-3 text-left">MDT意见</th>
            <th class="px-4 py-3 text-left">检查任务</th>
            <th class="px-4 py-3 text-left">审计条数</th>
            <th class="px-4 py-3 text-right">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="c in cases" :key="c.patient_id" class="hover:bg-slate-50">
            <td class="px-4 py-3 font-mono text-slate-700">{{ c.patient_id }}</td>
            <td class="px-4 py-3">{{ c.patient_name }}</td>
            <td class="px-4 py-3">
              <span :class="statusBadge(c.status)" class="px-2 py-0.5 rounded text-xs">{{ statusLabel(c.status) }}</span>
            </td>
            <td class="px-4 py-3">
              <span :class="c.emr_locked ? 'text-green-600' : 'text-slate-400'" class="text-xs">
                {{ c.emr_locked ? '✓ 已定稿' : '未定稿' }}
              </span>
            </td>
            <td class="px-4 py-3 text-slate-600">{{ c.attending_doctor_ids.join(', ') || '-' }}</td>
            <td class="px-4 py-3 text-slate-600">{{ c.treatment_count }}</td>
            <td class="px-4 py-3 text-slate-600">{{ c.mdt_comment_count }}</td>
            <td class="px-4 py-3 text-slate-600">{{ c.check_task_count }}</td>
            <td class="px-4 py-3 text-slate-600">{{ c.audit_log_count }}</td>
            <td class="px-4 py-3 text-right">
              <button @click="viewDetail(c.patient_id)" class="text-xs text-brand-600 hover:underline">查看详情</button>
            </td>
          </tr>
          <tr v-if="!cases.length">
            <td colspan="10" class="px-4 py-8 text-center text-slate-400 text-sm">暂无病案数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 详情抽屉 -->
    <div v-if="detail" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" @click.self="detail = null">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <!-- 头部 -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h3 class="text-lg font-semibold text-slate-800">
              病案详情 · {{ detail.patient_name }}
              <span class="font-mono text-slate-400 text-sm ml-2">{{ detail.patient_id }}</span>
            </h3>
            <p class="text-xs text-red-600 mt-1">⚠ 归档病案只读，禁止编辑原始留痕</p>
          </div>
          <button @click="detail = null" class="text-slate-400 hover:text-slate-600 text-xl">×</button>
        </div>

        <!-- Tab 切换 -->
        <div class="flex border-b border-slate-100 px-6 bg-slate-50">
          <button v-for="t in tabs" :key="t.key" @click="activeTab = t.key"
            :class="activeTab === t.key ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-4 py-3 text-sm font-medium border-b-2">
            {{ t.label }}
          </button>
        </div>

        <!-- 内容区 -->
        <div class="flex-1 overflow-auto p-6">
          <!-- 主病历 -->
          <div v-if="activeTab === 'emr'">
            <div class="bg-slate-50 rounded-lg p-4 mb-3">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-sm font-semibold text-slate-700">主病历（EMR）</span>
                <span :class="detail.emr_main?.locked ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-600'" class="px-2 py-0.5 rounded text-xs">
                  {{ detail.emr_main?.locked ? '已定稿' : '未定稿' }}
                </span>
              </div>
              <p v-if="detail.emr_main?.content" class="text-sm text-slate-700 whitespace-pre-wrap">{{ detail.emr_main.content }}</p>
              <p v-else class="text-sm text-slate-400 italic">（空）</p>
              <div class="text-xs text-slate-400 mt-2" v-if="detail.emr_main?.locked_by_name">
                定稿人：{{ detail.emr_main.locked_by_name }} · {{ detail.emr_main.locked_at }}
              </div>
            </div>
          </div>

          <!-- 诊疗方案多版本 -->
          <div v-if="activeTab === 'treatment'">
            <div class="text-xs text-slate-500 mb-3">按时间倒序展示，只读</div>
            <div v-for="v in treatmentSorted" :key="v.version_id" class="bg-slate-50 rounded-lg p-4 mb-3">
              <div class="flex items-center gap-2 mb-2">
                <span class="font-mono text-xs px-2 py-0.5 bg-brand-100 text-brand-700 rounded">v{{ v.version_no }}</span>
                <span class="text-xs text-slate-500">{{ v.created_by_name }} · {{ v.created_at }}</span>
              </div>
              <p class="text-sm text-slate-700 whitespace-pre-wrap">{{ v.content }}</p>
            </div>
            <div v-if="!treatmentSorted.length" class="text-sm text-slate-400 text-center py-4">暂无诊疗方案版本</div>
          </div>

          <!-- MDT 讨论 -->
          <div v-if="activeTab === 'mdt'">
            <div v-for="m in detail.mdt_comments || []" :key="m.comment_id" class="bg-slate-50 rounded-lg p-4 mb-3">
              <div class="flex items-center gap-2 mb-2 flex-wrap">
                <span class="text-sm font-medium text-slate-700">{{ m.author_name }}</span>
                <span class="text-xs text-slate-500">{{ m.author_role }}</span>
                <span class="text-xs text-slate-400">{{ m.created_at }}</span>
                <span v-if="m.is_adopted" class="ml-auto text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">✓ 已采纳</span>
                <span v-else class="ml-auto text-xs px-2 py-0.5 bg-slate-200 text-slate-500 rounded">未采纳</span>
              </div>
              <p class="text-sm text-slate-700 whitespace-pre-wrap">{{ m.content }}</p>
              <div v-if="m.is_adopted && m.adopted_by_name" class="text-xs text-slate-400 mt-2">
                采纳人：{{ m.adopted_by_name }} · {{ m.adopted_at }}
              </div>
            </div>
            <div v-if="!(detail.mdt_comments || []).length" class="text-sm text-slate-400 text-center py-4">暂无 MDT 讨论记录</div>
          </div>

          <!-- 检查任务流转 -->
          <div v-if="activeTab === 'check'">
            <table class="w-full text-sm bg-white border border-slate-100 rounded-lg overflow-hidden">
              <thead class="bg-slate-50 text-slate-600">
                <tr>
                  <th class="px-3 py-2 text-left">任务</th>
                  <th class="px-3 py-2 text-left">类型</th>
                  <th class="px-3 py-2 text-left">状态</th>
                  <th class="px-3 py-2 text-left">创建人</th>
                  <th class="px-3 py-2 text-left">完成时间</th>
                  <th class="px-3 py-2 text-left">结果</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="t in detail.check_tasks || []" :key="t.task_id">
                  <td class="px-3 py-2">{{ t.task_label }}</td>
                  <td class="px-3 py-2"><span class="font-mono text-xs text-slate-500">{{ t.task_type }}</span></td>
                  <td class="px-3 py-2">
                    <span :class="taskStatusBadge(t.status)" class="px-2 py-0.5 rounded text-xs">{{ t.status }}</span>
                  </td>
                  <td class="px-3 py-2 text-slate-600">{{ t.created_by_name }}</td>
                  <td class="px-3 py-2 text-slate-600">{{ t.completed_at || '-' }}</td>
                  <td class="px-3 py-2 text-slate-600 text-xs">{{ t.result?.summary || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!(detail.check_tasks || []).length" class="text-sm text-slate-400 text-center py-4">暂无检查任务</div>
          </div>

          <!-- 全流程审计日志 -->
          <div v-if="activeTab === 'audit'">
            <div class="text-xs text-slate-500 mb-3">患者就诊全流程留痕（仅查阅，不可篡改）</div>
            <div v-for="log in auditSorted" :key="log.log_id" class="border-l-2 border-brand-200 pl-3 pb-3 mb-3">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-mono px-2 py-0.5 bg-slate-100 text-slate-700 rounded">{{ log.action }}</span>
                <span class="text-sm text-slate-700">{{ log.actor_name }}</span>
                <span class="text-xs text-slate-400 ml-auto">{{ log.timestamp }}</span>
              </div>
              <p class="text-sm text-slate-600">{{ log.detail }}</p>
            </div>
            <div v-if="!auditSorted.length" class="text-sm text-slate-400 text-center py-4">暂无审计日志</div>
          </div>
        </div>

        <!-- 底部：导出按钮（仅 Mock 提示） -->
        <div class="px-6 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <span class="text-xs text-slate-400">Mock Demo：导出功能仅做演示，未实现真实文件下载</span>
          <button @click="exportMock" class="px-3 py-1.5 bg-slate-700 text-white rounded-lg text-xs hover:bg-slate-800">导出病案快照（Mock）</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, computed } from 'vue'
import { adminApi } from '../../api/admin'

const cases = ref([])
const detail = ref(null)
const activeTab = ref('emr')
const filters = reactive({ patient_id: '', doctor_id: '' })

const tabs = [
  { key: 'emr', label: '主病历' },
  { key: 'treatment', label: '诊疗方案版本' },
  { key: 'mdt', label: 'MDT讨论' },
  { key: 'check', label: '检查任务流转' },
  { key: 'audit', label: '全流程审计' },
]

const statusMap = {
  in_progress: '就诊中', waiting: '待接诊', archived: '已归档', closed: '已结束',
}
function statusLabel(s) { return statusMap[s] || s }
function statusBadge(s) {
  if (s === 'archived' || s === 'closed') return 'bg-slate-200 text-slate-700'
  if (s === 'in_progress') return 'bg-green-100 text-green-700'
  return 'bg-amber-100 text-amber-700'
}
function taskStatusBadge(s) {
  if (s === 'done') return 'bg-green-100 text-green-700'
  if (s === 'pending') return 'bg-amber-100 text-amber-700'
  return 'bg-slate-100 text-slate-600'
}

const treatmentSorted = computed(() => {
  const list = detail.value?.treatment_versions || []
  return [...list].sort((a, b) => (b.version_no || 0) - (a.version_no || 0))
})
const auditSorted = computed(() => {
  const list = detail.value?.audit_log || []
  return [...list].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
})

async function load() {
  const params = {}
  if (filters.patient_id) params.patient_id = filters.patient_id
  if (filters.doctor_id) params.doctor_id = filters.doctor_id
  cases.value = await adminApi.listCases(params)
}

function resetFilters() {
  filters.patient_id = ''
  filters.doctor_id = ''
  load()
}

async function viewDetail(pid) {
  activeTab.value = 'emr'
  detail.value = await adminApi.getCaseDetail(pid)
}

function exportMock() {
  alert(`Mock 导出：已生成病案 ${detail.value?.patient_id} 的只读快照（Demo 未实现真实文件下载）`)
}

onMounted(load)
</script>

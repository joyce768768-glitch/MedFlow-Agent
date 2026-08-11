<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">系统审计日志</h2>
        <p class="text-sm text-slate-500">
          后台数据修改、Agent开关变更、MDT采纳、归档操作留痕；每条记录含操作人/时间/类型/前后快照
        </p>
      </div>
      <div class="text-xs text-slate-400 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded">
        Mock 模拟：仅记录后台操作，未对接生产级 SIEM
      </div>
    </div>

    <!-- 筛选条 -->
    <div class="bg-white rounded-xl shadow-sm p-4 mb-4">
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block text-xs text-slate-500 mb-1">操作类型</label>
          <select v-model="filters.action" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="">全部</option>
            <option v-for="a in actionList" :key="a" :value="a">{{ actionLabels[a] || a }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">实体类型</label>
          <select v-model="filters.entity" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="">全部</option>
            <option v-for="e in entityList" :key="e" :value="e">{{ entityLabels[e] || e }}</option>
          </select>
        </div>
        <div class="flex items-end gap-2">
          <button @click="load" class="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">查询</button>
          <button @click="resetFilters" class="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-50">重置</button>
        </div>
      </div>
    </div>

    <!-- 日志列表 -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3 text-left">时间</th>
            <th class="px-4 py-3 text-left">操作人</th>
            <th class="px-4 py-3 text-left">操作类型</th>
            <th class="px-4 py-3 text-left">实体类型</th>
            <th class="px-4 py-3 text-left">实体ID</th>
            <th class="px-4 py-3 text-right">详情</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="log in logs" :key="log.log_id" class="hover:bg-slate-50 cursor-pointer" @click="toggleDetail(log.log_id)">
            <td class="px-4 py-3 text-slate-600 text-xs font-mono whitespace-nowrap">{{ log.timestamp }}</td>
            <td class="px-4 py-3 text-slate-700">{{ log.operator_name }} <span class="text-xs text-slate-400 font-mono">{{ log.operator_id }}</span></td>
            <td class="px-4 py-3">
              <span :class="actionBadge(log.action)" class="px-2 py-0.5 rounded text-xs">{{ actionLabels[log.action] || log.action }}</span>
            </td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">{{ entityLabels[log.entity] || log.entity }}</span>
            </td>
            <td class="px-4 py-3 font-mono text-xs text-slate-500">{{ log.entity_id || '-' }}</td>
            <td class="px-4 py-3 text-right">
              <button class="text-xs text-brand-600 hover:underline">
                {{ expanded === log.log_id ? '收起' : '查看快照' }}
              </button>
            </td>
          </tr>
          <tr v-if="!logs.length">
            <td colspan="6" class="px-4 py-8 text-center text-slate-400 text-sm">暂无审计日志</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 详情展开行（前后快照对比） -->
    <div v-if="expandedLog" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" @click.self="expanded = ''">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h3 class="text-lg font-semibold text-slate-800">审计快照详情</h3>
          <button @click="expanded = ''" class="text-slate-400 hover:text-slate-600 text-xl">×</button>
        </div>
        <div class="p-6 overflow-auto">
          <div class="grid grid-cols-2 gap-4 mb-4 text-sm">
            <div>
              <div class="text-xs text-slate-500 mb-1">操作人</div>
              <div class="text-slate-700">{{ expandedLog.operator_name }} <span class="text-xs text-slate-400 font-mono">{{ expandedLog.operator_id }}</span></div>
            </div>
            <div>
              <div class="text-xs text-slate-500 mb-1">时间</div>
              <div class="text-slate-700 font-mono text-xs">{{ expandedLog.timestamp }}</div>
            </div>
            <div>
              <div class="text-xs text-slate-500 mb-1">操作类型</div>
              <div><span :class="actionBadge(expandedLog.action)" class="px-2 py-0.5 rounded text-xs">{{ actionLabels[expandedLog.action] || expandedLog.action }}</span></div>
            </div>
            <div>
              <div class="text-xs text-slate-500 mb-1">实体</div>
              <div class="text-slate-700">{{ entityLabels[expandedLog.entity] || expandedLog.entity }} <span class="font-mono text-xs text-slate-400">{{ expandedLog.entity_id }}</span></div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <!-- 变更前 -->
            <div>
              <div class="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-1">
                <span class="w-2 h-2 rounded-full bg-red-400"></span> 变更前
              </div>
              <pre class="bg-red-50 border border-red-100 rounded-lg p-3 text-xs text-slate-700 overflow-auto max-h-64">{{ formatJson(expandedLog.before) }}</pre>
            </div>
            <!-- 变更后 -->
            <div>
              <div class="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-1">
                <span class="w-2 h-2 rounded-full bg-green-400"></span> 变更后
              </div>
              <pre class="bg-green-50 border border-green-100 rounded-lg p-3 text-xs text-slate-700 overflow-auto max-h-64">{{ formatJson(expandedLog.after) }}</pre>
            </div>
          </div>

          <div v-if="!expandedLog.before && !expandedLog.after" class="text-center text-sm text-slate-400 py-4">
            （无前后快照，如删除操作仅记录动作）
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, computed } from 'vue'
import { adminApi } from '../../api/admin'

const logs = ref([])
const expanded = ref('')  // 当前展开的 log_id
const filters = reactive({ action: '', entity: '' })

const actionList = ['create', 'update', 'delete', 'activate', 'deactivate', 'agent_toggle', 'archive']
const actionLabels = {
  create: '新建',
  update: '更新',
  delete: '删除',
  activate: '启用',
  deactivate: '停用',
  agent_toggle: 'Agent开关',
  archive: '归档',
}

const entityList = ['building', 'floor', 'room', 'department', 'user', 'exam_item', 'rag_doc', 'agent_config', 'case', 'kb']
const entityLabels = {
  building: '楼宇',
  floor: '楼层',
  room: '房间',
  department: '科室',
  user: '用户',
  exam_item: '检验项目',
  rag_doc: 'RAG文档',
  agent_config: 'Agent配置',
  case: '病案',
  kb: '简易知识库',
}

const expandedLog = computed(() => logs.value.find((l) => l.log_id === expanded.value) || null)

function actionBadge(a) {
  const map = {
    create: 'bg-green-100 text-green-700',
    update: 'bg-blue-100 text-blue-700',
    delete: 'bg-red-100 text-red-700',
    activate: 'bg-teal-100 text-teal-700',
    deactivate: 'bg-slate-200 text-slate-600',
    agent_toggle: 'bg-purple-100 text-purple-700',
    archive: 'bg-amber-100 text-amber-700',
  }
  return map[a] || 'bg-slate-100 text-slate-600'
}

function toggleDetail(logId) {
  expanded.value = expanded.value === logId ? '' : logId
}

function formatJson(obj) {
  if (obj === null || obj === undefined) return '(无)'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function load() {
  const params = {}
  if (filters.action) params.action = filters.action
  if (filters.entity) params.entity = filters.entity
  logs.value = await adminApi.listAudit(params)
}

function resetFilters() {
  filters.action = ''
  filters.entity = ''
  load()
}

onMounted(load)
</script>

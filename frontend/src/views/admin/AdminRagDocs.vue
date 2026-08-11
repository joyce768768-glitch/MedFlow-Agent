<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">RAG 文档知识库</h2>
        <p class="text-sm text-slate-500">文档上传后自动 Mock 分块 + Mock 向量；启用后可供 SubAgent 召回引用</p>
      </div>
      <button @click="openCreate" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">+ 上传文档</button>
    </div>

    <!-- 分类筛选 -->
    <div class="flex items-center gap-2 mb-4 flex-wrap">
      <button v-for="(label, key) in categories" :key="key"
        @click="filter = filter === key ? '' : key"
        :class="filter === key ? 'bg-brand-600 text-white' : 'bg-white text-slate-600 border border-slate-200'"
        class="px-3 py-1 rounded-lg text-sm">{{ label }}</button>
      <button v-if="filter" @click="filter = ''" class="text-xs text-slate-500 hover:text-brand-600">清除筛选</button>
    </div>

    <!-- 文档列表 -->
    <div class="space-y-3 mb-6">
      <div v-for="d in filtered" :key="d.doc_id" class="bg-white rounded-xl shadow-sm p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span :class="catBadge(d.category)" class="px-2 py-0.5 rounded text-xs">{{ categories[d.category] || d.category }}</span>
              <span class="font-medium text-slate-800">{{ d.title }}</span>
              <span class="text-xs text-slate-400">v{{ d.version }}</span>
              <span :class="statusBadge(d.status)" class="px-2 py-0.5 rounded text-xs">{{ statusLabel(d.status) }}</span>
            </div>
            <div class="text-xs text-slate-500">
              {{ d.chunks.length }} 个分块 · 上传人 {{ d.uploaded_by_name }} · {{ d.updated_at?.slice(0, 16) }}
            </div>
            <div v-if="d.history && d.history.length" class="text-xs text-slate-400 mt-1">
              历史版本：{{ d.history.map(h => 'v' + h.version).join(' → ') }} → v{{ d.version }}
            </div>
          </div>
          <div class="flex flex-col gap-1 ml-4 shrink-0 text-right">
            <div class="flex gap-2 justify-end">
              <button v-if="d.status !== 'active'" @click="setStatus(d, 'active')" class="text-xs text-green-600 hover:underline">启用</button>
              <button v-if="d.status === 'active'" @click="setStatus(d, 'inactive')" class="text-xs text-slate-600 hover:underline">停用</button>
              <button @click="openEdit(d)" class="text-xs text-brand-600 hover:underline">编辑</button>
              <button @click="toggleChunks(d)" class="text-xs text-slate-600 hover:underline">{{ expanded === d.doc_id ? '收起' : '查看分块' }}</button>
              <button @click="remove(d)" class="text-xs text-red-600 hover:underline">删除</button>
            </div>
          </div>
        </div>
        <!-- 分块详情 -->
        <div v-if="expanded === d.doc_id" class="mt-3 border-t border-slate-100 pt-3 space-y-2">
          <div v-for="c in d.chunks" :key="c.chunk_id" class="bg-slate-50 rounded p-2 text-xs">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono text-slate-400">chunk #{{ c.chunk_no }}</span>
              <span class="text-slate-400">Mock向量: [{{ c.vector_mock.slice(0, 4).map(v => v.toFixed(2)).join(', ') }}, ...]</span>
            </div>
            <p class="text-slate-600">{{ c.text }}</p>
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="bg-white rounded-xl p-8 text-center text-slate-400">暂无文档</div>
    </div>

    <!-- 召回测试面板 -->
    <div class="bg-white rounded-xl shadow-sm p-5">
      <h3 class="font-semibold text-slate-800 mb-2">Mock 召回测试</h3>
      <p class="text-xs text-slate-500 mb-3">输入一句指令，模拟从已启用文档中召回匹配片段（纯 Mock 关键词匹配，生产需替换为真实向量检索）</p>
      <div class="flex gap-2 mb-3">
        <input v-model="recallQuery" @keyup.enter="doRecall" class="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="如：胃炎的诊断要点" />
        <button @click="doRecall" :disabled="recalling" class="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">{{ recalling ? '召回中…' : '召回' }}</button>
      </div>
      <div v-if="recallHits.length" class="space-y-2">
        <div v-for="(h, i) in recallHits" :key="h.chunk_id" class="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-mono text-amber-700">#{{ i + 1 }} score={{ h.score_mock.toFixed(2) }}</span>
            <span class="text-xs text-slate-500">{{ h.doc_title }}</span>
            <span class="text-xs text-slate-400">chunk #{{ h.chunk_no }}</span>
          </div>
          <p class="text-slate-700">{{ h.text }}</p>
        </div>
      </div>
      <div v-else-if="recallDone" class="text-sm text-slate-400 text-center py-4">未召回任何片段（请确认已有 active 文档）</div>
    </div>

    <!-- 上传/编辑弹窗 -->
    <div v-if="showModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">{{ editing ? '编辑文档（生成新版本）' : '上传文档' }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm text-slate-600 mb-1">分类</label>
            <select v-model="form.category" :disabled="editing" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500 disabled:bg-slate-100">
              <option v-for="(label, key) in categories" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">标题</label>
            <input v-model="form.title" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">内容（文本/模拟PDF文本）</label>
            <textarea v-model="form.content" rows="8" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="粘贴文档内容，系统将自动按段落分块（每段≤200字）"></textarea>
            <p class="text-xs text-slate-400 mt-1">提交后自动 Mock 分块 + 生成 Mock 8维向量；状态默认「待审核」，需手动启用后才参与召回</p>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-6">
          <button @click="showModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
          <button @click="save" :disabled="saving" class="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
        <p v-if="error" class="text-sm text-red-600 mt-3">{{ error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, computed } from 'vue'
import { adminApi } from '../../api/admin'

const docs = ref([])
const filter = ref('')
const expanded = ref('')
const showModal = ref(false)
const editing = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ doc_id: '', title: '', category: 'clinical_guide', content: '' })

const recallQuery = ref('')
const recallHits = ref([])
const recalling = ref(false)
const recallDone = ref(false)

const categories = {
  clinical_guide: '诊疗规范', soap_template: '病历模板', sop: '院内SOP', mdt_template: 'MDT模板',
}
const catBadges = {
  clinical_guide: 'bg-blue-100 text-blue-700', soap_template: 'bg-emerald-100 text-emerald-700',
  sop: 'bg-amber-100 text-amber-700', mdt_template: 'bg-purple-100 text-purple-700',
}
function catBadge(c) { return catBadges[c] || 'bg-slate-100 text-slate-600' }
function statusLabel(s) { return { pending: '待审核', active: '已启用', inactive: '已停用' }[s] || s }
function statusBadge(s) { return { pending: 'bg-amber-100 text-amber-700', active: 'bg-green-100 text-green-700', inactive: 'bg-slate-200 text-slate-500' }[s] || 'bg-slate-100' }

const filtered = computed(() => (filter.value ? docs.value.filter((d) => d.category === filter.value) : docs.value))

async function load() { docs.value = await adminApi.listRagDocs() }

function openCreate() {
  editing.value = false; error.value = ''
  Object.assign(form, { doc_id: '', title: '', category: 'clinical_guide', content: '' })
  showModal.value = true
}
function openEdit(d) {
  editing.value = true; error.value = ''
  Object.assign(form, { doc_id: d.doc_id, title: d.title, category: d.category, content: d.content })
  showModal.value = true
}
async function save() {
  saving.value = true; error.value = ''
  try {
    if (editing.value) {
      await adminApi.updateRagDoc(form.doc_id, { title: form.title, content: form.content })
    } else {
      await adminApi.createRagDoc({ title: form.title, category: form.category, content: form.content })
    }
    showModal.value = false
    await load()
  } catch (e) { error.value = e.response?.data?.detail || '保存失败' }
  finally { saving.value = false }
}
async function setStatus(d, status) {
  try { await adminApi.setRagDocStatus(d.doc_id, status); await load() }
  catch (e) { alert(e.response?.data?.detail || '操作失败') }
}
function toggleChunks(d) {
  expanded.value = expanded.value === d.doc_id ? '' : d.doc_id
}
async function remove(d) {
  if (!confirm(`确认删除「${d.title}」？`)) return
  try { await adminApi.deleteRagDoc(d.doc_id); await load() }
  catch (e) { alert(e.response?.data?.detail || '删除失败') }
}
async function doRecall() {
  if (!recallQuery.value.trim()) return
  recalling.value = true; recallDone.value = false; recallHits.value = []
  try {
    recallHits.value = await adminApi.ragRecall(recallQuery.value, 5)
    recallDone.value = true
  } catch (e) { alert(e.response?.data?.detail || '召回失败') }
  finally { recalling.value = false }
}

onMounted(load)
</script>

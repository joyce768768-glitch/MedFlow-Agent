<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">Mock 知识库</h2>
        <p class="text-sm text-slate-500">临床指南 / SOAP 模板 / 药品字典 / MDT 模板，供病历 SubAgent 引用</p>
      </div>
      <button @click="openCreate" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">+ 新建条目</button>
    </div>

    <!-- 分类筛选 -->
    <div class="flex items-center gap-2 mb-4 flex-wrap">
      <button
        v-for="(label, key) in categories"
        :key="key"
        @click="filter = filter === key ? '' : key"
        :class="filter === key ? 'bg-brand-600 text-white' : 'bg-white text-slate-600 border border-slate-200'"
        class="px-3 py-1 rounded-lg text-sm"
      >{{ label }}</button>
      <button v-if="filter" @click="filter = ''" class="text-xs text-slate-500 hover:text-brand-600">清除筛选</button>
    </div>

    <div class="space-y-3">
      <div v-for="e in filtered" :key="e.kb_id" class="bg-white rounded-xl shadow-sm p-4">
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span :class="catBadge(e.category)" class="px-2 py-0.5 rounded text-xs">{{ categories[e.category] || e.category }}</span>
              <span class="font-medium text-slate-800">{{ e.title }}</span>
            </div>
            <p class="text-sm text-slate-600 whitespace-pre-wrap">{{ e.content }}</p>
            <div class="flex flex-wrap gap-1 mt-2">
              <span v-for="t in e.tags" :key="t" class="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-xs">#{{ t }}</span>
            </div>
          </div>
          <div class="flex flex-col gap-1 ml-4 shrink-0">
            <button @click="openEdit(e)" class="text-xs text-brand-600 hover:underline">编辑</button>
            <button @click="remove(e)" class="text-xs text-red-600 hover:underline">删除</button>
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="bg-white rounded-xl p-8 text-center text-slate-400">暂无知识库条目</div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <div v-if="showModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">{{ editing ? '编辑条目' : '新建条目' }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm text-slate-600 mb-1">分类</label>
            <select v-model="form.category" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500">
              <option v-for="(label, key) in categories" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">标题</label>
            <input v-model="form.title" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">内容</label>
            <textarea v-model="form.content" rows="6" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500"></textarea>
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">标签（逗号分隔）</label>
            <input v-model="form.tagsStr" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="胃炎,消化内科" />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-6">
          <button @click="showModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
          <button @click="save" :disabled="saving" class="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
        <p v-if="error" class="text-sm text-red-600 mt-3">{{ error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, computed } from 'vue'
import { adminApi } from '../../api/admin'

const entries = ref([])
const categories = ref({})
const filter = ref('')
const showModal = ref(false)
const editing = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ kb_id: '', category: 'guide', title: '', content: '', tagsStr: '' })

const filtered = computed(() => (filter.value ? entries.value.filter((e) => e.category === filter.value) : entries.value))

const catBadges = {
  guide: 'bg-blue-100 text-blue-700',
  soap_template: 'bg-emerald-100 text-emerald-700',
  drug_dict: 'bg-amber-100 text-amber-700',
  mdt_template: 'bg-purple-100 text-purple-700',
}
function catBadge(c) {
  return catBadges[c] || 'bg-slate-100 text-slate-600'
}

async function load() {
  const [list, cats] = await Promise.all([adminApi.listKb(), adminApi.listKbCategories()])
  entries.value = list
  categories.value = cats
}

function openCreate() {
  editing.value = false
  error.value = ''
  Object.assign(form, { kb_id: '', category: 'guide', title: '', content: '', tagsStr: '' })
  showModal.value = true
}

function openEdit(e) {
  editing.value = true
  error.value = ''
  Object.assign(form, {
    kb_id: e.kb_id,
    category: e.category,
    title: e.title,
    content: e.content,
    tagsStr: (e.tags || []).join(','),
  })
  showModal.value = true
}

function parseTags(s) {
  return s.split(',').map((t) => t.trim()).filter(Boolean)
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const tags = parseTags(form.tagsStr)
    if (editing.value) {
      await adminApi.updateKb(form.kb_id, { title: form.title, content: form.content, tags })
    } else {
      await adminApi.createKb({ category: form.category, title: form.title, content: form.content, tags })
    }
    showModal.value = false
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(e) {
  if (!confirm(`确认删除「${e.title}」？`)) return
  try {
    await adminApi.deleteKb(e.kb_id)
    await load()
  } catch (err) {
    alert(err.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

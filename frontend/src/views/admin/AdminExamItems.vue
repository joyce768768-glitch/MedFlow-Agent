<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">检验/检查项目字典</h2>
        <p class="text-sm text-slate-500">维护标准化检验检查项目编码，供开立检查任务时引用</p>
      </div>
      <button @click="openCreate" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">+ 新建项目</button>
    </div>

    <div class="flex items-center gap-2 mb-4 flex-wrap">
      <button v-for="(label, key) in categories" :key="key"
        @click="filter = filter === key ? '' : key"
        :class="filter === key ? 'bg-brand-600 text-white' : 'bg-white text-slate-600 border border-slate-200'"
        class="px-3 py-1 rounded-lg text-sm">{{ label }}</button>
      <button v-if="filter" @click="filter = ''" class="text-xs text-slate-500 hover:text-brand-600">清除筛选</button>
    </div>

    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3 text-left">编码</th>
            <th class="px-4 py-3 text-left">名称</th>
            <th class="px-4 py-3 text-left">分类</th>
            <th class="px-4 py-3 text-left">规格/要求</th>
            <th class="px-4 py-3 text-left">参考值</th>
            <th class="px-4 py-3 text-right">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="e in filtered" :key="e.item_id" class="hover:bg-slate-50">
            <td class="px-4 py-3 font-mono text-slate-700">{{ e.code }}</td>
            <td class="px-4 py-3">{{ e.name }}</td>
            <td class="px-4 py-3"><span :class="catBadge(e.category)" class="px-2 py-0.5 rounded text-xs">{{ categories[e.category] || e.category }}</span></td>
            <td class="px-4 py-3 text-slate-600">{{ e.spec }}</td>
            <td class="px-4 py-3 text-slate-600">{{ e.ref_range }}</td>
            <td class="px-4 py-3 text-right space-x-2">
              <button @click="openEdit(e)" class="text-xs text-brand-600 hover:underline">编辑</button>
              <button @click="remove(e)" class="text-xs text-red-600 hover:underline">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">{{ editing ? '编辑项目' : '新建项目' }}</h3>
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm text-slate-600 mb-1">编码</label>
              <input v-model="form.code" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="如 CBC" />
            </div>
            <div>
              <label class="block text-sm text-slate-600 mb-1">分类</label>
              <select v-model="form.category" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500">
                <option v-for="(label, key) in categories" :key="key" :value="key">{{ label }}</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">名称</label>
            <input v-model="form.name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="如 血常规" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">规格/要求</label>
            <input v-model="form.spec" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="如 EDTA抗凝血2ml" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">参考值</label>
            <input v-model="form.ref_range" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="如 WBC 4-10×10^9/L" />
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

const items = ref([])
const filter = ref('')
const showModal = ref(false)
const editing = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ item_id: '', code: '', name: '', category: 'blood', spec: '', ref_range: '' })

const categories = {
  blood: '血液检验', ct: 'CT影像', ultrasound: '超声', pathology: '病理', other: '其他',
}
const catBadges = {
  blood: 'bg-red-100 text-red-700', ct: 'bg-blue-100 text-blue-700',
  ultrasound: 'bg-teal-100 text-teal-700', pathology: 'bg-purple-100 text-purple-700', other: 'bg-slate-100 text-slate-600',
}
function catBadge(c) { return catBadges[c] || 'bg-slate-100 text-slate-600' }

const filtered = computed(() => (filter.value ? items.value.filter((e) => e.category === filter.value) : items.value))

async function load() { items.value = await adminApi.listExamItems() }

function openCreate() {
  editing.value = false; error.value = ''
  Object.assign(form, { item_id: '', code: '', name: '', category: 'blood', spec: '', ref_range: '' })
  showModal.value = true
}
function openEdit(e) {
  editing.value = true; error.value = ''
  Object.assign(form, { item_id: e.item_id, code: e.code, name: e.name, category: e.category, spec: e.spec, ref_range: e.ref_range })
  showModal.value = true
}
async function save() {
  saving.value = true; error.value = ''
  try {
    if (editing.value) {
      await adminApi.updateExamItem(form.item_id, { code: form.code, name: form.name, category: form.category, spec: form.spec, ref_range: form.ref_range })
    } else {
      await adminApi.createExamItem({ code: form.code, name: form.name, category: form.category, spec: form.spec, ref_range: form.ref_range })
    }
    showModal.value = false
    await load()
  } catch (e) { error.value = e.response?.data?.detail || '保存失败' }
  finally { saving.value = false }
}
async function remove(e) {
  if (!confirm(`确认删除「${e.name}」？`)) return
  try { await adminApi.deleteExamItem(e.item_id); await load() }
  catch (err) { alert(err.response?.data?.detail || '删除失败') }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">科室管理</h2>
        <p class="text-sm text-slate-500">维护院内科室字典，用于用户归属与权限范围</p>
      </div>
      <button @click="openCreate" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">+ 新建科室</button>
    </div>

    <div class="bg-white rounded-xl shadow-sm divide-y divide-slate-100">
      <div v-for="d in departments" :key="d.dept_id" class="flex items-center px-4 py-3 hover:bg-slate-50">
        <span class="flex-1 text-slate-700">{{ d.name }}</span>
        <span class="text-xs text-slate-400 mr-4">{{ d.created_at?.slice(0, 10) }}</span>
        <button @click="openEdit(d)" class="text-xs text-brand-600 hover:underline mr-3">重命名</button>
        <button @click="remove(d)" class="text-xs text-red-600 hover:underline">删除</button>
      </div>
      <div v-if="!departments.length" class="px-4 py-8 text-center text-slate-400">暂无科室</div>
    </div>

    <div v-if="showModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">{{ editing ? '重命名科室' : '新建科室' }}</h3>
        <input v-model="form.name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="科室名称" />
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
import { onMounted, ref, reactive } from 'vue'
import { adminApi } from '../../api/admin'

const departments = ref([])
const showModal = ref(false)
const editing = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ dept_id: '', name: '' })

async function load() {
  departments.value = await adminApi.listDepartments()
}

function openCreate() {
  editing.value = false
  error.value = ''
  form.dept_id = ''
  form.name = ''
  showModal.value = true
}

function openEdit(d) {
  editing.value = true
  error.value = ''
  form.dept_id = d.dept_id
  form.name = d.name
  showModal.value = true
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (editing.value) await adminApi.updateDepartment(form.dept_id, form.name)
    else await adminApi.createDepartment(form.name)
    showModal.value = false
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(d) {
  if (!confirm(`确认删除科室「${d.name}」？`)) return
  try {
    await adminApi.deleteDepartment(d.dept_id)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

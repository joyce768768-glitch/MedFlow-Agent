<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">用户管理</h2>
        <p class="text-sm text-slate-500">管理医生 / 护士 / 管理员账号、角色与启停状态</p>
      </div>
      <button @click="openCreate" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">+ 新建用户</button>
    </div>

    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3 text-left">用户名</th>
            <th class="px-4 py-3 text-left">姓名</th>
            <th class="px-4 py-3 text-left">角色</th>
            <th class="px-4 py-3 text-left">科室</th>
            <th class="px-4 py-3 text-left">职称</th>
            <th class="px-4 py-3 text-left">状态</th>
            <th class="px-4 py-3 text-right">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="u in users" :key="u.user_id" class="hover:bg-slate-50">
            <td class="px-4 py-3 font-mono text-slate-700">{{ u.username }}</td>
            <td class="px-4 py-3">{{ u.name }}</td>
            <td class="px-4 py-3">
              <span :class="roleBadge(u.role)" class="px-2 py-0.5 rounded text-xs">{{ roleLabel(u.role) }}</span>
            </td>
            <td class="px-4 py-3">{{ u.department }}</td>
            <td class="px-4 py-3">{{ u.title }}</td>
            <td class="px-4 py-3">
              <span :class="u.active ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-500'" class="px-2 py-0.5 rounded text-xs">
                {{ u.active ? '启用' : '停用' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right space-x-2 whitespace-nowrap">
              <button @click="toggleActive(u)" class="text-xs text-slate-600 hover:text-brand-600">{{ u.active ? '停用' : '启用' }}</button>
              <button @click="openEdit(u)" class="text-xs text-brand-600 hover:underline">编辑</button>
              <button v-if="u.username !== 'admin'" @click="remove(u)" class="text-xs text-red-600 hover:underline">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新建/编辑弹窗 -->
    <div v-if="showModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">{{ editing ? '编辑用户' : '新建用户' }}</h3>
        <div class="space-y-3">
          <div v-if="!editing">
            <label class="block text-sm text-slate-600 mb-1">用户名</label>
            <input v-model="form.username" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">姓名</label>
            <input v-model="form.name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">{{ editing ? '新密码（留空不改）' : '密码' }}</label>
            <input v-model="form.password" type="password" :placeholder="editing ? '留空保持原密码' : ''" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm text-slate-600 mb-1">角色</label>
              <select v-model="form.role" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500">
                <option v-for="r in roles" :key="r" :value="r">{{ roleLabel(r) }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-slate-600 mb-1">科室</label>
              <select v-model="form.department" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500">
                <option v-for="d in departments" :key="d.dept_id" :value="d.name">{{ d.name }}</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">职称</label>
            <input v-model="form.title" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
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
import { onMounted, ref, reactive } from 'vue'
import { adminApi } from '../../api/admin'

const users = ref([])
const departments = ref([])
const roles = ['attending', 'mdt_expert', 'nurse', 'readonly', 'admin']
const showModal = ref(false)
const editing = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ user_id: '', username: '', name: '', password: '', role: 'attending', department: '', title: '' })

const roleLabels = { attending: '主治医生', mdt_expert: 'MDT专家', nurse: '护士', readonly: '只读医生', admin: '管理员' }
function roleLabel(r) { return roleLabels[r] || r }
function roleBadge(r) {
  return {
    attending: 'bg-blue-100 text-blue-700',
    mdt_expert: 'bg-purple-100 text-purple-700',
    nurse: 'bg-teal-100 text-teal-700',
    readonly: 'bg-slate-200 text-slate-600',
    admin: 'bg-amber-100 text-amber-700',
  }[r] || 'bg-slate-100 text-slate-600'
}

async function load() {
  const [u, d] = await Promise.all([adminApi.listUsers(), adminApi.listDepartments()])
  users.value = u
  departments.value = d
}

function openCreate() {
  editing.value = false
  error.value = ''
  Object.assign(form, { user_id: '', username: '', name: '', password: '', role: 'attending', department: departments.value[0]?.name || '', title: '' })
  showModal.value = true
}

function openEdit(u) {
  editing.value = true
  error.value = ''
  Object.assign(form, { user_id: u.user_id, username: u.username, name: u.name, password: '', role: u.role, department: u.department, title: u.title })
  showModal.value = true
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (editing.value) {
      const patch = { name: form.name, role: form.role, department: form.department, title: form.title }
      if (form.password) patch.password = form.password
      await adminApi.updateUser(form.user_id, patch)
    } else {
      await adminApi.createUser({
        username: form.username, password: form.password, name: form.name,
        role: form.role, department: form.department, title: form.title,
      })
    }
    showModal.value = false
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function toggleActive(u) {
  try {
    await adminApi.updateUser(u.user_id, { active: !u.active })
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '操作失败')
  }
}

async function remove(u) {
  if (!confirm(`确认删除用户 ${u.name}（${u.username}）？`)) return
  try {
    await adminApi.deleteUser(u.user_id)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

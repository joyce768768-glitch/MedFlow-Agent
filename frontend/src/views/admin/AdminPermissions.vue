<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">角色-动作权限矩阵</h2>
        <p class="text-sm text-slate-500">配置 4 个临床角色的动作权限开关，保存后即时影响后端鉴权与前端视图</p>
      </div>
      <button @click="save" :disabled="saving" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50">
        {{ saving ? '保存中…' : '保存矩阵' }}
      </button>
    </div>

    <div class="bg-white rounded-xl shadow-sm overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3 text-left whitespace-nowrap">角色 / 动作</th>
            <th v-for="a in actions" :key="a" class="px-3 py-3 text-center whitespace-nowrap">{{ actionLabel(a) }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="r in roles" :key="r" class="hover:bg-slate-50">
            <td class="px-4 py-3 font-medium text-slate-700 whitespace-nowrap">{{ roleLabel(r) }}</td>
            <td v-for="a in actions" :key="a" class="px-3 py-3 text-center">
              <input
                type="checkbox"
                :checked="matrix[r] && matrix[r][a]"
                @change="matrix[r] && (matrix[r][a] = $event.target.checked)"
                class="h-4 w-4 rounded text-brand-600 focus:ring-brand-500"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mt-4 text-sm text-amber-800">
      <p>说明：admin 角色固定拥有后台管理权限，不在此矩阵内；此处仅控制 4 个临床角色的工作台动作权限。</p>
      <p class="mt-1">保存后即时生效；已登录的临床用户需刷新页面或重新登录后，权限视图与后端鉴权才会刷新。</p>
    </div>
    <p v-if="msg" class="text-sm mt-3" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { adminApi } from '../../api/admin'

const roles = ref([])
const actions = ref([])
const matrix = reactive({})
const saving = ref(false)
const msg = ref('')
const err = ref(false)

const roleLabels = { attending: '主治医生', mdt_expert: 'MDT专家', nurse: '护士', readonly: '只读医生' }
const actionLabels = {
  can_view_emr: '查看病历', can_edit_emr: '编辑病历', can_lock_emr: '锁定病历', can_generate_ai: '生成AI草稿',
  can_open_check: '开立检查', can_invite_mdt: '邀请MDT', can_adopt_comment: '采纳意见', can_submit_comment: '提交评论',
  can_view_history: '查看历史', can_view_mdt: '查看MDT', can_view_check: '查看检查',
}
function roleLabel(r) { return roleLabels[r] || r }
function actionLabel(a) { return actionLabels[a] || a }

async function load() {
  const data = await adminApi.getPermissions()
  roles.value = data.roles
  actions.value = data.actions
  // 清空旧键后重建，保证 reactive 可追踪
  for (const r of Object.keys(matrix)) delete matrix[r]
  for (const r of data.roles) {
    matrix[r] = {}
    for (const a of data.actions) matrix[r][a] = !!data.matrix[r]?.[a]
  }
}

async function save() {
  saving.value = true
  msg.value = ''
  err.value = false
  try {
    const payload = {}
    for (const r of roles.value) {
      payload[r] = {}
      for (const a of actions.value) payload[r][a] = !!matrix[r]?.[a]
    }
    await adminApi.updatePermissions(payload)
    msg.value = '权限矩阵已保存，即时影响后端鉴权'
  } catch (e) {
    err.value = true
    msg.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

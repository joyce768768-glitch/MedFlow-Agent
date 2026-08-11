<template>
  <div class="bg-white rounded-xl shadow-sm p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-slate-800">MDT 讨论区</h3>
      <button v-if="auth.permissions?.can_invite_mdt" @click="showInvite = !showInvite"
        class="px-3 py-1.5 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700">邀请专家</button>
    </div>

    <!-- 邀请专家面板 -->
    <div v-if="showInvite" class="mb-4 p-3 bg-slate-50 rounded-lg">
      <div class="text-sm text-slate-600 mb-2">选择 MDT 专家并发起邀请（临时授权，带时效）：</div>
      <div class="flex items-center gap-2">
        <select v-model="inviteExpertId" class="px-2 py-1.5 border border-slate-300 rounded-lg text-sm">
          <option value="">请选择专家</option>
          <option v-for="u in experts" :key="u.username" :value="u.username">{{ u.name }}（{{ u.department }}）</option>
        </select>
        <select v-model.number="inviteHours" class="px-2 py-1.5 border border-slate-300 rounded-lg text-sm">
          <option :value="24">24 小时</option>
          <option :value="72">72 小时</option>
          <option :value="168">7 天</option>
        </select>
        <button @click="invite" :disabled="!inviteExpertId"
          class="px-3 py-1.5 bg-slate-700 text-white text-sm rounded-lg hover:bg-slate-800 disabled:opacity-50">发送邀请</button>
      </div>
      <p v-if="inviteMsg" class="text-xs mt-2 text-green-600">{{ inviteMsg }}</p>
      <!-- 已邀请白名单 -->
      <div v-if="invitations.length" class="mt-3 text-xs text-slate-500">
        已邀请：{{ invitations.map(i => i.expert_name + '（至 ' + fmt(i.expires_at) + '）').join('；') }}
      </div>
    </div>

    <!-- 评论列表 -->
    <div class="space-y-3">
      <div v-for="c in comments" :key="c.comment_id" class="p-3 bg-slate-50 rounded-lg border border-slate-100">
        <div class="flex items-center justify-between mb-1">
          <span class="text-sm font-medium text-slate-700">{{ c.author_name }}
            <span class="text-xs text-slate-400 ml-1">（{{ roleLabel(c.author_role) }}）</span>
          </span>
          <span class="text-xs text-slate-400">{{ fmt(c.created_at) }}</span>
        </div>
        <div class="text-sm text-slate-700 whitespace-pre-wrap">{{ c.content }}</div>
        <div class="flex items-center gap-2 mt-2">
          <span v-if="c.is_adopted" class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
            已采纳 · {{ c.adopted_by_name }} · {{ fmt(c.adopted_at) }}
          </span>
          <button v-else-if="auth.permissions?.can_adopt_comment" @click="adopt(c.comment_id)"
            class="text-xs px-2 py-1 rounded-lg bg-green-600 text-white hover:bg-green-700">采纳</button>
          <span v-else class="text-xs text-slate-400">未采纳</span>
        </div>
      </div>
      <div v-if="!comments.length" class="text-sm text-slate-400 text-center py-4">暂无 MDT 讨论</div>
    </div>

    <!-- 评论输入（仅 MDT 专家） -->
    <div v-if="auth.permissions?.can_submit_comment" class="mt-4 border-t border-slate-100 pt-3">
      <textarea v-model="newComment" rows="2" placeholder="提交 MDT 专家意见（提交后冻结，不可修改删除）"
        class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"></textarea>
      <button @click="submit" :disabled="!newComment.trim() || submitting"
        class="mt-2 px-3 py-1.5 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
        {{ submitting ? '提交中…' : '提交意见' }}
      </button>
      <p v-if="msg" class="text-xs mt-1" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
    </div>
    <div v-else-if="auth.isReadonly" class="mt-4 text-xs text-slate-400 border-t border-slate-100 pt-3">
      历史只读医生：评论输入框已隐藏，仅可查阅历史讨论记录。
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ patientId: String })
const emit = defineEmits(['updated'])
const auth = useAuthStore()
const comments = ref([])
const invitations = ref([])
const experts = ref([])
const showInvite = ref(false)
const inviteExpertId = ref('')
const inviteHours = ref(72)
const inviteMsg = ref('')
const newComment = ref('')
const submitting = ref(false)
const msg = ref(''); const err = ref(false)

function roleLabel(r) { return { attending: '主治医生', mdt_expert: 'MDT专家', nurse: '护士', readonly: '只读医生' }[r] || r }
function fmt(t) { return t ? new Date(t).toLocaleString('zh-CN') : '' }

async function load() {
  const [{ data: cs }, { data: invs }, { data: users }] = await Promise.all([
    api.get(`/patients/${props.patientId}/mdt/comments`),
    api.get(`/patients/${props.patientId}/mdt/invitations`).catch(() => ({ data: [] })),
    api.get('/users').catch(() => ({ data: [] })),
  ])
  comments.value = cs
  invitations.value = invs
  experts.value = users.filter(u => u.role === 'mdt_expert')
}
async function submit() {
  submitting.value = true; msg.value = ''; err.value = false
  try {
    await api.post(`/patients/${props.patientId}/mdt/comments`, { content: newComment.value.trim() })
    newComment.value = ''; msg.value = '意见已提交（冻结留痕）'
    await load(); emit('updated')
  } catch (e) { err.value = true; msg.value = e.response?.data?.detail || '提交失败' }
  finally { submitting.value = false }
}
async function adopt(id) {
  try {
    await api.post(`/patients/${props.patientId}/mdt/comments/${id}/adopt`)
    await load(); emit('updated')
  } catch (e) { alert(e.response?.data?.detail || '采纳失败') }
}
async function invite() {
  const expert = experts.value.find(u => u.username === inviteExpertId.value)
  if (!expert) return
  try {
    const { data } = await api.post(`/patients/${props.patientId}/mdt/invite`, {
      expert_id: expert.user_id, expires_hours: inviteHours.value,
    })
    invitations.value = data
    inviteMsg.value = `已邀请 ${expert.name}（时效 ${inviteHours.value}h）`
  } catch (e) { alert(e.response?.data?.detail || '邀请失败') }
}
onMounted(load)
</script>

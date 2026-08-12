<template>
  <div class="bg-white rounded-xl shadow-sm flex flex-col" style="height: 70vh; min-height: 480px;">
    <!-- 顶部标题栏 -->
    <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <h3 class="font-semibold text-slate-800">病历辅助 Agent</h3>
        <span v-if="enabled" class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">SubAgent 已开启</span>
        <span v-else class="text-xs px-2 py-0.5 rounded-full bg-slate-200 text-slate-600">SubAgent 已关闭</span>
      </div>
      <div class="flex items-center gap-2">
        <button v-if="auth.permissions?.can_generate_ai" @click="quickGenerate" :disabled="generating"
          class="text-xs px-2 py-1 rounded bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 disabled:opacity-50">
          {{ generating ? '生成中…' : '一键生成草稿' }}
        </button>
        <button @click="clearChat" :disabled="clearing"
          class="text-xs px-2 py-1 rounded bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100 disabled:opacity-50">
          {{ clearing ? '清空中…' : '清空对话' }}
        </button>
      </div>
    </div>

    <!-- 提示条 -->
    <div class="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-700 shrink-0">
      AI 输出为独立建议，不会自动写入正式病历；需主治 HITL 确认后手动采纳。
    </div>

    <!-- 消息列表 -->
    <div ref="msgBox" class="flex-1 overflow-auto px-4 py-3 space-y-3 bg-slate-50/30">
      <div v-if="!messages.length && !loading" class="h-full flex items-center justify-center text-slate-400 text-sm">
        <div class="text-center">
          <div class="mb-2">尚无对话历史</div>
          <div class="text-xs">向 AI 提问，例如：「根据主诉生成 SOAP 草稿」「增加鉴别诊断」</div>
        </div>
      </div>

      <div v-for="m in messages" :key="m.msg_id" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
        <div class="max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap"
          :class="m.role === 'user'
            ? 'bg-brand-600 text-white'
            : 'bg-white border border-slate-200 text-slate-700'">
          <div v-if="m.role === 'assistant'" class="flex items-center gap-1 mb-1 text-xs"
            :class="m.provider_used === 'openai_compatible' ? 'text-green-600' : 'text-slate-400'">
            <span>AI</span>
            <span class="text-[10px]">·</span>
            <span>{{ m.provider_used === 'openai_compatible' ? '真模型' : 'Mock' }}</span>
          </div>
          {{ m.content }}
          <div class="text-[10px] mt-1 opacity-60">{{ formatTime(m.timestamp) }}</div>

          <!-- 结构化 SOAP 输出 -->
          <div v-if="m.structured_output && hasStructuredData(m.structured_output)" class="mt-3 pt-2 border-t border-slate-100">
            <div class="text-xs font-semibold text-slate-600 mb-2">📋 SOAP 结构化草稿</div>
            <div class="space-y-2 text-xs">
              <div v-if="m.structured_output.chief_complaint" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">主诉：</span>
                <span class="text-slate-800 flex-1">{{ m.structured_output.chief_complaint }}</span>
              </div>
              <div v-if="m.structured_output.present_illness" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">现病史：</span>
                <span class="text-slate-800 flex-1">{{ m.structured_output.present_illness }}</span>
              </div>
              <div v-if="m.structured_output.past_history" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">既往史：</span>
                <span class="text-slate-800 flex-1">{{ m.structured_output.past_history }}</span>
              </div>
              <div v-if="m.structured_output.examination" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">查体：</span>
                <span class="text-slate-800 flex-1">{{ m.structured_output.examination }}</span>
              </div>
              <div v-if="m.structured_output.assessment" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">评估：</span>
                <span class="text-slate-800 flex-1">{{ m.structured_output.assessment }}</span>
              </div>
              <div v-if="m.structured_output.differential_diagnosis && m.structured_output.differential_diagnosis.length" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">鉴别诊断：</span>
                <span class="text-slate-800 flex-1">
                  <span v-for="(dd, i) in m.structured_output.differential_diagnosis" :key="i" class="inline-block px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded mr-1">{{ dd }}</span>
                </span>
              </div>
              <div v-if="m.structured_output.risk_flags && m.structured_output.risk_flags.length" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">风险提示：</span>
                <span class="text-slate-800 flex-1">
                  <span v-for="(rf, i) in m.structured_output.risk_flags" :key="i" class="inline-block px-1.5 py-0.5 bg-red-50 text-red-600 rounded mr-1">{{ rf }}</span>
                </span>
              </div>
              <div v-if="m.structured_output.plan" class="flex gap-2">
                <span class="text-slate-500 min-w-[60px]">诊疗计划：</span>
                <span class="text-slate-800 flex-1">{{ m.structured_output.plan }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="flex justify-start">
        <div class="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-500">
          <span class="inline-block animate-pulse">AI 思考中…</span>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="px-4 py-3 border-t border-slate-100 shrink-0" v-if="auth.permissions?.can_generate_ai">
      <div class="flex items-end gap-2">
        <textarea
          v-model="input"
          @keydown.enter.exact.prevent="send"
          @keydown.enter.shift.exact="input += '\n'"
          rows="2"
          class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm resize-none focus:outline-none focus:border-brand-500"
          placeholder="输入消息（Enter 发送，Shift+Enter 换行）"
          :disabled="loading"
        ></textarea>
        <button @click="send" :disabled="loading || !input.trim()"
          class="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-50">
          发送
        </button>
      </div>
      <!-- 快捷指令 -->
      <div class="flex flex-wrap gap-1 mt-2">
        <button v-for="q in quickPrompts" :key="q" @click="usePrompt(q)"
          class="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded">
          {{ q }}
        </button>
      </div>
    </div>
    <div v-else class="px-4 py-3 border-t border-slate-100 text-xs text-slate-400 shrink-0">
      当前角色无 AI 对话权限
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, nextTick, watch } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ patientId: String })
const auth = useAuthStore()

const messages = ref([])
const input = ref('')
const loading = ref(false)
const generating = ref(false)
const clearing = ref(false)
const enabled = ref(false)
const msgBox = ref(null)

const quickPrompts = [
  '根据主诉生成 SOAP 草稿',
  '把评估部分写详细些',
  '增加鉴别诊断',
  '检查结果：血常规正常',
]

function formatTime(ts) {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(0, 19)
}

function hasStructuredData(structured) {
  if (!structured || typeof structured !== 'object') return false
  // 检查是否有任何非空字段
  const fields = ['chief_complaint', 'present_illness', 'past_history', 'examination', 'assessment', 'plan']
  for (const f of fields) {
    if (structured[f] && String(structured[f]).trim()) return true
  }
  if (structured.differential_diagnosis && structured.differential_diagnosis.length) return true
  if (structured.risk_flags && structured.risk_flags.length) return true
  return false
}

async function load() {
  try {
    const [emrRes, histRes] = await Promise.all([
      api.get(`/patients/${props.patientId}/emr`),
      api.get(`/patients/${props.patientId}/emr/chat/history`),
    ])
    enabled.value = !!emrRes.data.enable_emr_subagent
    messages.value = histRes.data || []
    await scrollToBottom()
  } catch (e) {
    console.error('加载病历对话失败', e)
  }
}

async function send() {
  const msg = input.value.trim()
  if (!msg || loading.value) return
  input.value = ''
  loading.value = true

  // 乐观显示用户消息
  const tempId = `temp_${Date.now()}`
  messages.value.push({ msg_id: tempId, role: 'user', content: msg, timestamp: new Date().toISOString() })
  await scrollToBottom()

  try {
    const { data } = await api.post(`/patients/${props.patientId}/emr/chat`, { message: msg })
    // 替换 tempId 为正式消息（其实后端已经记录了 user 消息，但我们用乐观显示简化处理）
    // 这里直接 push AI 回复，user 消息保持乐观版本即可（刷新时会从后端同步）
    messages.value.push({
      ...data,
      msg_id: data.msg_id || `ai_${Date.now()}`,
    })
    await scrollToBottom()
  } catch (e) {
    messages.value.push({
      msg_id: `err_${Date.now()}`,
      role: 'assistant',
      content: `请求失败：${e.response?.data?.detail || e.message}`,
      timestamp: new Date().toISOString(),
      provider_used: 'mock',
    })
    await scrollToBottom()
  } finally {
    loading.value = false
  }
}

async function quickGenerate() {
  generating.value = true
  try {
    const { data } = await api.post(`/patients/${props.patientId}/emr/ai-draft`)
    // 把一键生成的草稿作为一条 AI 消息推入对话
    messages.value.push({
      msg_id: `draft_${Date.now()}`,
      role: 'assistant',
      content: data.ai_draft,
      timestamp: new Date().toISOString(),
      provider_used: data.enabled ? 'mock' : 'mock',
    })
    enabled.value = data.enabled
    await scrollToBottom()
  } catch (e) {
    messages.value.push({
      msg_id: `err_${Date.now()}`,
      role: 'assistant',
      content: `生成失败：${e.response?.data?.detail || e.message}`,
      timestamp: new Date().toISOString(),
      provider_used: 'mock',
    })
  } finally {
    generating.value = false
  }
}

async function clearChat() {
  if (!confirm('确认清空当前患者的病历对话历史？')) return
  clearing.value = true
  try {
    await api.delete(`/patients/${props.patientId}/emr/chat/session`)
    messages.value = []
  } catch (e) {
    alert('清空失败：' + (e.response?.data?.detail || e.message))
  } finally {
    clearing.value = false
  }
}

function usePrompt(p) {
  input.value = p
}

async function scrollToBottom() {
  await nextTick()
  if (msgBox.value) {
    msgBox.value.scrollTop = msgBox.value.scrollHeight
  }
}

watch(() => props.patientId, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-slate-800">Agent 能力灰度配置</h2>
      <p class="text-sm text-slate-500">控制 LangGraph 节点内 SubAgent 分支开关；全局开关 + 医院级灰度覆盖（医院级优先）</p>
    </div>

    <div class="space-y-4">
      <div v-for="agent in agentList" :key="agent.key" class="bg-white rounded-xl shadow-sm p-5">
        <div class="flex items-center justify-between mb-3">
          <div>
            <div class="font-semibold text-slate-800">{{ agent.label }}</div>
            <div class="text-xs text-slate-500 mt-0.5">{{ agent.desc }}</div>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-sm text-slate-600">全局开关</span>
            <Toggle :model-value="config[agent.key]?.global" @update:model-value="(v) => toggleGlobal(agent.key, v)" />
            <span :class="config[agent.key]?.global ? 'text-green-600' : 'text-slate-400'" class="text-sm font-medium">
              {{ config[agent.key]?.global ? '已开启' : '已关闭' }}
            </span>
          </div>
        </div>

        <!-- 医院级灰度 -->
        <div class="border-t border-slate-100 pt-3">
          <div class="text-xs text-slate-500 mb-2">医院级灰度覆盖（医院级优先于全局开关）</div>
          <div v-if="config[agent.key]?.hospitals && Object.keys(config[agent.key].hospitals).length" class="flex flex-wrap gap-2 mb-2">
            <span v-for="(on, hid) in config[agent.key].hospitals" :key="hid" class="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 rounded text-xs">
              {{ hid }}
              <span :class="on ? 'text-green-600' : 'text-slate-400'">{{ on ? '✓开' : '✗关' }}</span>
              <button @click="removeHospitalOverride(agent.key, hid)" class="text-red-500 hover:text-red-700 ml-1">✕</button>
            </span>
          </div>
          <div class="flex items-center gap-2">
            <input v-model="hospitalForms[agent.key].id" class="px-2 py-1 border border-slate-300 rounded text-sm w-40" placeholder="医院ID（如 h001）" />
            <button @click="setHospital(agent.key, true)" class="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700">设为开</button>
            <button @click="setHospital(agent.key, false)" class="px-2 py-1 bg-slate-600 text-white rounded text-xs hover:bg-slate-700">设为关</button>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4 text-sm text-blue-800">
      <p><strong>架构说明</strong>：开关对应 LangGraph 方案A「同节点内 if 分支」——开启时调用 SubAgent（AI 草稿/影像初筛），关闭时直接走人工分支。两条路径最终收敛到同一 HITL 终审卡点。</p>
      <p class="mt-1"><strong>审计</strong>：每次开关变更自动写入系统审计日志（操作人、时间、变更前后），可在「系统审计」页查阅。</p>
      <p class="mt-1 text-xs text-blue-600">⚠ Mock 模拟逻辑：生产环境需对接配置中心（如 Apollo/Nacos）实现多实例同步。</p>
    </div>
    <p v-if="msg" class="text-sm mt-3" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { adminApi } from '../../api/admin'
import Toggle from '../../components/Toggle.vue'

const config = ref({})
const msg = ref('')
const err = ref(false)
const hospitalForms = reactive({ emr_agent: { id: '' }, imaging_agent: { id: '' } })

const agentList = [
  { key: 'emr_agent', label: '病历辅助 Agent', desc: '开启：接诊节点调用 emr_draft_subagent 生成 AI 草稿（隔离区）；关闭：走人工编辑' },
  { key: 'imaging_agent', label: '影像初筛辅助 Agent', desc: '开启：影像节点调用 imaging_subagent 辅助初筛；关闭：纯人工阅片' },
]

async function load() {
  config.value = await adminApi.getAgentConfig()
}

async function toggleGlobal(agentKey, on) {
  try {
    config.value = await adminApi.toggleAgent({ agent_key: agentKey, global_on: on })
    msg.value = `${agentKey} 全局开关已${on ? '开启' : '关闭'}，已记录审计日志`
    err.value = false
  } catch (e) {
    err.value = true
    msg.value = e.response?.data?.detail || '操作失败'
  }
}

async function setHospital(agentKey, on) {
  const hid = hospitalForms[agentKey].id.trim()
  if (!hid) { err.value = true; msg.value = '请输入医院ID'; return }
  try {
    config.value = await adminApi.toggleAgent({ agent_key: agentKey, hospital_id: hid, hospital_on: on })
    hospitalForms[agentKey].id = ''
    msg.value = `${agentKey} 医院 ${hid} 已设为${on ? '开启' : '关闭'}`
    err.value = false
  } catch (e) {
    err.value = true
    msg.value = e.response?.data?.detail || '操作失败'
  }
}

async function removeHospitalOverride(agentKey, hid) {
  // Mock：通过设置为全局值来"移除"覆盖（Demo简化，不实现真正的删除）
  const globalOn = config.value[agentKey]?.global
  try {
    config.value = await adminApi.toggleAgent({ agent_key: agentKey, hospital_id: hid, hospital_on: globalOn })
    msg.value = `${agentKey} 医院 ${hid} 覆盖已移除（回退到全局${globalOn ? '开' : '关'}）`
    err.value = false
  } catch (e) {
    err.value = true
    msg.value = e.response?.data?.detail || '操作失败'
  }
}

onMounted(load)
</script>

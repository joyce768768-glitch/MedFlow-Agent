<template>
  <div class="min-h-screen bg-slate-100">
    <header class="h-14 bg-slate-900 text-white flex items-center px-4 gap-4">
      <router-link to="/workstation" class="flex items-center gap-2">
        <span class="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center font-bold">医</span>
        <span class="font-semibold">SubAgent 配置</span>
      </router-link>
      <span class="text-xs text-slate-400">后台可插拔插件开关（方案A：节点内 if 分支即时生效）</span>
      <router-link to="/workstation" class="ml-auto px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 text-sm">返回工作台</router-link>
    </header>

    <div class="max-w-2xl mx-auto py-8">
      <div class="bg-white rounded-xl shadow-sm p-6">
        <h2 class="text-lg font-semibold text-slate-800 mb-1">SubAgent 开关</h2>
        <p class="text-sm text-slate-500 mb-6">切换开关后即时同步到所有患者 State，节点内 if 分支立即按新配置走 AI / 人工路径。</p>

        <div class="space-y-4">
          <div class="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
            <div>
              <div class="font-medium text-slate-700">病历草稿 SubAgent</div>
              <div class="text-xs text-slate-500 mt-0.5">开启：接诊节点调用 emr_draft_subagent 生成 AI 草稿（隔离）；关闭：走人工编辑</div>
            </div>
            <Toggle v-model="cfg.enable_emr_subagent" />
          </div>
          <div class="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
            <div>
              <div class="font-medium text-slate-700">检验汇总 SubAgent</div>
              <div class="text-xs text-slate-500 mt-0.5">开启：调用 lab_summary_subagent 汇总已完成检查；关闭：人工解读</div>
            </div>
            <Toggle v-model="cfg.enable_lab_subagent" />
          </div>
        </div>

        <button @click="save" :disabled="saving"
          class="mt-6 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
        <p v-if="msg" class="text-sm mt-3" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
      </div>

      <div class="bg-white rounded-xl shadow-sm p-6 mt-4">
        <h3 class="font-semibold text-slate-800 mb-2">演示要点</h3>
        <ul class="text-sm text-slate-600 list-disc pl-5 space-y-1">
          <li>关闭病历 SubAgent 后，回到工作台点"生成 AI 病历草稿"将提示走人工编辑路径。</li>
          <li>两条分支最终都收敛到同一 HITL 终审卡点，AI 输出绝不自动写入正式病历。</li>
          <li>不维护两套 Graph，仅在节点内 if 判断 enable_*_subagent。</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import Toggle from '../components/Toggle.vue'

const cfg = reactive({ enable_emr_subagent: false, enable_lab_subagent: false })
const saving = ref(false); const msg = ref(''); const err = ref(false)

async function load() {
  const { data } = await api.get('/config/subagents')
  cfg.enable_emr_subagent = data.enable_emr_subagent
  cfg.enable_lab_subagent = data.enable_lab_subagent
}
async function save() {
  saving.value = true; msg.value = ''; err.value = false
  try {
    await api.put('/config/subagents', { ...cfg })
    msg.value = '配置已保存，已同步至所有患者'
  } catch (e) { err.value = true; msg.value = e.response?.data?.detail || '保存失败' }
  finally { saving.value = false }
}
onMounted(load)
</script>

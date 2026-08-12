<template>
  <div>
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-slate-800">Agent 配置（开关 + 模型）</h2>
      <p class="text-sm text-slate-500">
        每个 SubAgent 独立配置：能力灰度开关 + 模型接入（Mock / OpenAI 兼容云端模型）。模型配置热更新，无需重启后端。
      </p>
    </div>

    <div class="space-y-5">
      <div v-for="agent in agentList" :key="agent.key" class="bg-white rounded-xl shadow-sm overflow-hidden">
        <!-- 顶部：标题 + 全局开关 -->
        <div class="p-5 flex items-center justify-between">
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
        <div class="border-t border-slate-100 px-5 py-3 bg-slate-50/50">
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

        <!-- 模型配置区域 -->
        <div class="border-t border-slate-100 px-5 py-4">
          <div class="flex items-center justify-between mb-3">
            <div class="text-sm font-semibold text-slate-700">模型配置</div>
            <div class="flex items-center gap-2">
              <span v-if="modelStates[agent.key]" class="text-xs px-2 py-0.5 rounded" :class="modelStates[agent.key].real_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'">
                {{ modelStates[agent.key].real_active ? '● 真模型已激活' : '○ Mock 模式' }}
              </span>
              <button @click="loadModelConfig(agent.key)" class="text-xs text-blue-600 hover:underline">刷新</button>
            </div>
          </div>

          <div v-if="modelStates[agent.key]">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <!-- Provider -->
              <div>
                <label class="block text-xs text-slate-600 mb-1">Provider（接入方式）</label>
                <select v-model="modelForms[agent.key].provider" class="w-full px-2 py-1.5 border border-slate-300 rounded text-sm">
                  <option value="mock">mock（本地关键词规则，零密钥依赖）</option>
                  <option value="openai_compatible">openai_compatible（OpenAI 兼容云端模型）</option>
                </select>
              </div>
              <!-- enable_real -->
              <div>
                <label class="block text-xs text-slate-600 mb-1">启用真模型</label>
                <select v-model.number="modelForms[agent.key].enable_real" class="w-full px-2 py-1.5 border border-slate-300 rounded text-sm">
                  <option :value="0">0 - 关闭（走 Mock）</option>
                  <option :value="1">1 - 开启（走真模型，失败自动降级 Mock）</option>
                </select>
              </div>
              <!-- model -->
              <div>
                <label class="block text-xs text-slate-600 mb-1">模型名称（model）</label>
                <input v-model="modelForms[agent.key].model" class="w-full px-2 py-1.5 border border-slate-300 rounded text-sm" placeholder="如 deepseek-chat / qwen-plus" />
              </div>
              <!-- base_url -->
              <div>
                <label class="block text-xs text-slate-600 mb-1">Base URL</label>
                <input v-model="modelForms[agent.key].base_url" class="w-full px-2 py-1.5 border border-slate-300 rounded text-sm" placeholder="如 https://api.deepseek.com/v1" />
              </div>
              <!-- api_key -->
              <div>
                <label class="block text-xs text-slate-600 mb-1">
                  API Key
                  <span v-if="modelStates[agent.key].api_key_configured" class="text-green-600 ml-1">（已配置：{{ modelStates[agent.key].api_key_masked }}）</span>
                  <span v-else class="text-slate-400 ml-1">（未配置）</span>
                </label>
                <div class="flex items-center gap-1">
                  <input v-model="modelForms[agent.key].api_key" :type="keyVisible[agent.key] ? 'text' : 'password'"
                    autocomplete="new-password"
                    class="flex-1 px-2 py-1.5 border border-slate-300 rounded text-sm"
                    placeholder="留空不修改；输入新值覆盖"
                    @focus="onKeyFocus(agent.key)"
                    @input="onKeyInput(agent.key)"
                  />
                  <button type="button" @click="toggleKeyVisible(agent.key)"
                    class="px-2 py-1.5 border border-slate-300 rounded text-sm text-slate-500 hover:bg-slate-50"
                    :title="keyVisible[agent.key] ? '隐藏' : '显示'">
                    <span v-if="keyVisible[agent.key]">👁️‍🗨️</span>
                    <span v-else>👁️</span>
                  </button>
                </div>
              </div>
              <!-- timeout -->
              <div>
                <label class="block text-xs text-slate-600 mb-1">超时（秒）</label>
                <input v-model.number="modelForms[agent.key].timeout" type="number" min="5" max="120" class="w-full px-2 py-1.5 border border-slate-300 rounded text-sm" />
              </div>
            </div>

            <!-- Prompt 编辑区 -->
            <div class="mt-4 pt-3 border-t border-slate-100">
              <div class="flex items-center justify-between mb-1">
                <label class="text-xs text-slate-600">
                  System Prompt
                  <span v-if="modelStates[agent.key].prompt_is_default" class="text-slate-400 ml-1">（使用默认）</span>
                  <span v-else class="text-green-600 ml-1">（自定义）</span>
                </label>
                <div class="flex items-center gap-2">
                  <button v-if="!modelForms[agent.key].prompt" @click="useDefaultPrompt(agent.key)"
                    class="text-xs text-blue-600 hover:underline">从默认加载</button>
                  <button v-else @click="clearPrompt(agent.key)"
                    class="text-xs text-slate-500 hover:underline">清除自定义</button>
                </div>
              </div>
              <textarea v-model="modelForms[agent.key].prompt" rows="5"
                class="w-full px-2 py-1.5 border border-slate-300 rounded text-xs font-mono resize-y"
                :placeholder="defaultPromptPlaceholder(agent.key)"
              ></textarea>
              <div class="text-xs text-slate-400 mt-1">留空使用默认 Prompt；修改后保存即生效</div>
            </div>

            <!-- Output Schema 编辑区（仅 emr_agent 显示） -->
            <div v-if="agent.key === 'emr_agent'" class="mt-4 pt-3 border-t border-slate-100">
              <div class="flex items-center justify-between mb-1">
                <label class="text-xs text-slate-600">
                  输出 Schema（结构化输出字段）
                  <span v-if="modelStates[agent.key].output_schema_is_default" class="text-slate-400 ml-1">（使用默认）</span>
                  <span v-else class="text-green-600 ml-1">（自定义）</span>
                </label>
                <div class="flex items-center gap-2">
                  <button v-if="!modelForms[agent.key].output_schema" @click="useDefaultOutputSchema(agent.key)"
                    class="text-xs text-blue-600 hover:underline">从默认加载</button>
                  <button v-else @click="clearOutputSchema(agent.key)"
                    class="text-xs text-slate-500 hover:underline">清除自定义</button>
                </div>
              </div>
              <textarea v-model="modelForms[agent.key].output_schema" rows="8"
                class="w-full px-2 py-1.5 border border-slate-300 rounded text-xs font-mono resize-y"
                :placeholder="defaultOutputSchemaPlaceholder(agent.key)"
              ></textarea>
              <div class="text-xs text-slate-400 mt-1">定义 LLM 输出的 JSON Schema 字段（用于前端 SOAP 卡片渲染）；留空使用默认 Schema</div>
            </div>
          </div>

          <div v-else class="text-sm text-slate-400 py-2">加载中…</div>

          <div class="flex items-center gap-2 mt-4">
            <button @click="saveModelConfig(agent.key)" class="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">保存配置</button>
            <button @click="testModel(agent.key)" class="px-3 py-1.5 bg-slate-600 text-white rounded text-sm hover:bg-slate-700">测试连通性</button>
            <span v-if="testResults[agent.key]" class="text-xs ml-2" :class="testResults[agent.key].ok ? 'text-green-600' : 'text-red-600'">
              {{ testResults[agent.key].ok ? `✓ 连通正常（${testResults[agent.key].provider_used}）` : `✗ ${testResults[agent.key].error || '连通失败'}` }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4 text-sm text-blue-800">
      <p><strong>架构说明</strong>：开关对应 LangGraph 方案A「同节点内 if 分支」——开启时调用 SubAgent，关闭时直接走人工分支。两条路径最终收敛到同一 HITL 终审卡点。</p>
      <p class="mt-1"><strong>模型配置</strong>：每个 SubAgent 单独配置模型，支持 Mock / OpenAI 兼容接口（通义千问 / DeepSeek / 智谱 GLM / 本地 Ollama 等）。配置热更新，运行时即时生效。</p>
      <p class="mt-1"><strong>审计</strong>：每次开关或模型配置变更自动写入系统审计日志，可在「系统审计」页查阅。</p>
      <p class="mt-1 text-xs text-blue-600">⚠ Mock 模拟逻辑：生产环境需对接配置中心（如 Apollo/Nacos）实现多实例同步。</p>
    </div>
    <p v-if="msg" class="text-sm mt-3" :class="err ? 'text-red-600' : 'text-green-600'">{{ msg }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, nextTick } from 'vue'
import { adminApi } from '../../api/admin'
import Toggle from '../../components/Toggle.vue'

const config = ref({})
const msg = ref('')
const err = ref(false)
const modelStates = reactive({})   // 真实返回状态（含 api_key_masked / real_active）
const modelForms = reactive({})    // 表单输入
const keyVisible = reactive({})    // API Key 可见性切换
const testResults = reactive({})   // 测试结果
const hospitalForms = reactive({
  patient_triage_agent: { id: '' },
  emr_agent: { id: '' },
  imaging_agent: { id: '' },
})

const agentList = [
  {
    key: 'patient_triage_agent',
    label: '患者导诊 Agent',
    desc: '患者端 AI 智能分诊：采集症状，推荐 2-3 个就诊科室 + 置信度（强制免责声明）',
  },
  {
    key: 'emr_agent',
    label: '病历辅助 Agent',
    desc: '开启：接诊节点调用 emr_draft_subagent 生成 AI 草稿（隔离区）；关闭：走人工编辑',
  },
  {
    key: 'imaging_agent',
    label: '影像初筛辅助 Agent',
    desc: '开启：影像节点调用 imaging_subagent 辅助初筛；关闭：纯人工阅片',
  },
]

async function load() {
  config.value = await adminApi.getAgentConfig()
  // 并行加载每个 agent 的模型配置
  await Promise.all(agentList.map((a) => loadModelConfig(a.key)))
}

async function loadModelConfig(agentKey) {
  try {
    const data = await adminApi.getAgentModelConfig(agentKey)
    modelStates[agentKey] = data
    modelForms[agentKey] = {
      provider: data.provider,
      enable_real: data.enable_real,
      model: data.model,
      base_url: data.base_url,
      api_key: '',       // 始终为空：后端脱敏不返回真实 key，留空=不修改
      key_dirty: false,  // 标记用户是否主动操作过 Key 输入框（防浏览器自动填充误覆盖）
      timeout: data.timeout,
      prompt: data.prompt || '',  // 自定义 Prompt，空=使用默认
      output_schema: data.output_schema || '',  // 自定义输出 Schema，空=使用默认
    }
    keyVisible[agentKey] = false  // 默认隐藏 Key
    // 渲染后强制清空 input 值，覆盖浏览器自动填充
    await nextTick()
    if (modelForms[agentKey]) {
      modelForms[agentKey].api_key = ''
    }
  } catch (e) {
    err.value = true
    msg.value = `加载 ${agentKey} 模型配置失败：${e.response?.data?.detail || e.message}`
  }
}

function onKeyFocus(agentKey) {
  // 用户聚焦输入框 → 标记为可能修改（浏览器自动填充不触发 focus）
  const form = modelForms[agentKey]
  if (form) form.key_dirty = true
}

function onKeyInput(agentKey) {
  // 用户输入 → 确认修改
  const form = modelForms[agentKey]
  if (form) form.key_dirty = true
}

function toggleKeyVisible(agentKey) {
  keyVisible[agentKey] = !keyVisible[agentKey]
}

const DEFAULT_PROMPTS = {
  patient_triage_agent: '你是一家三级甲等医院的【AI智能导诊助手】，只负责分诊科室推荐，绝对不能做诊断、开处方、推荐药物或给出治疗方案。',
  emr_agent: '你是一家三级甲等医院的【AI 病历辅助助手】，协助主治医生起草和优化病历，绝不替代医生做最终决策。',
  imaging_agent: '你是一家三级甲等医院的【AI 影像辅助助手】，辅助医生分析影像，绝不独立做诊断。',
}

function defaultPromptPlaceholder(agentKey) {
  return DEFAULT_PROMPTS[agentKey] || '留空使用默认 Prompt'
}

function useDefaultPrompt(agentKey) {
  const form = modelForms[agentKey]
  if (form) {
    form.prompt = defaultPromptPlaceholder(agentKey)
  }
}

function clearPrompt(agentKey) {
  const form = modelForms[agentKey]
  if (form) {
    form.prompt = ''
  }
}

const DEFAULT_OUTPUT_SCHEMAS = {
  emr_agent: JSON.stringify({
    chief_complaint: '主诉',
    present_illness: '现病史',
    past_history: '既往史',
    examination: '查体',
    assessment: '评估',
    differential_diagnosis: ['鉴别诊断1', '鉴别诊断2'],
    risk_flags: ['风险提示'],
    plan: '诊疗计划',
  }, null, 2),
}

function defaultOutputSchemaPlaceholder(agentKey) {
  return DEFAULT_OUTPUT_SCHEMAS[agentKey] || '留空使用默认 Schema'
}

function useDefaultOutputSchema(agentKey) {
  const form = modelForms[agentKey]
  if (form) {
    form.output_schema = defaultOutputSchemaPlaceholder(agentKey)
  }
}

function clearOutputSchema(agentKey) {
  const form = modelForms[agentKey]
  if (form) {
    form.output_schema = ''
  }
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

async function saveModelConfig(agentKey) {
  const form = modelForms[agentKey]
  if (!form) return

  const trimmedKey = form.api_key.trim()
  const body = {
    provider: form.provider,
    enable_real: form.enable_real,
    model: form.model,
    base_url: form.base_url,
    timeout: form.timeout,
    prompt: form.prompt,  // Prompt 始终发送（空=清除自定义恢复默认）
    output_schema: form.output_schema,  // Output Schema 始终发送（空=清除自定义恢复默认）
  }

  // 核心保护：只有用户主动操作过 Key 输入框（key_dirty=true）才发送 api_key
  // 防止浏览器自动填充 password 字段导致 Key 被误覆盖
  if (form.key_dirty) {
    if (trimmedKey) {
      body.api_key = trimmedKey     // 用户输入了新 Key → 覆盖
    } else {
      body.api_key = ''             // 用户聚焦过但清空了 → 显式清除
    }
  }
  // key_dirty=false → 不传 api_key，后端保持原 Key 不变

  try {
    const data = await adminApi.updateAgentModelConfig(agentKey, body)
    modelStates[agentKey] = data
    // 保存后重置 key_dirty + 清空输入框
    modelForms[agentKey].api_key = ''
    modelForms[agentKey].key_dirty = false
    modelForms[agentKey].prompt = data.prompt || ''
    modelForms[agentKey].output_schema = data.output_schema || ''
    msg.value = `${agentKey} 模型配置已保存，已记录审计日志`
    err.value = false
  } catch (e) {
    err.value = true
    msg.value = `保存失败：${e.response?.data?.detail || e.message}`
  }
}

async function testModel(agentKey) {
  testResults[agentKey] = { ok: false, error: '测试中…' }
  try {
    const data = await adminApi.testAgentModel(agentKey)
    testResults[agentKey] = data
    if (data.ok) {
      msg.value = `${agentKey} 模型连通正常：${(data.reply_preview || '').slice(0, 60)}`
      err.value = false
    } else {
      msg.value = `${agentKey} 模型连通失败：${data.error}`
      err.value = true
    }
  } catch (e) {
    testResults[agentKey] = { ok: false, error: e.response?.data?.detail || e.message }
    err.value = true
    msg.value = `测试请求失败：${e.response?.data?.detail || e.message}`
  }
}

onMounted(load)
</script>

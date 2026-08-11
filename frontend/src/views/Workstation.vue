<template>
  <div class="h-screen flex flex-col">
    <!-- 顶部栏 -->
    <header class="h-14 bg-slate-900 text-white flex items-center px-4 gap-4 shrink-0">
      <div class="flex items-center gap-2">
        <span class="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center font-bold">医</span>
        <span class="font-semibold">医院诊疗 Agent 工作台</span>
        <span class="text-xs text-slate-400 ml-2">Demo · LangGraph + 可插拔 SubAgent</span>
      </div>
      <div class="ml-auto flex items-center gap-3 text-sm">
        <span class="text-slate-300">{{ auth.user?.name }}（{{ roleLabel }}）</span>
        <router-link v-if="auth.isAttending" to="/config"
          class="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600">SubAgent 配置</router-link>
        <router-link v-if="auth.isAdmin" to="/admin"
          class="px-3 py-1 rounded bg-brand-600 hover:bg-brand-700">后台管理</router-link>
        <button @click="logout" class="px-3 py-1 rounded bg-slate-700 hover:bg-red-600">退出</button>
      </div>
    </header>

    <!-- 主体 -->
    <div class="flex-1 flex overflow-hidden">
      <!-- 左侧：患者列表 / 分诊队列 -->
      <PatientList :role="auth.role" @select="onSelect" />

      <!-- 右侧：患者详情 -->
      <main class="flex-1 overflow-auto p-4">
        <div v-if="!selectedId" class="h-full flex items-center justify-center text-slate-400">
          请在左侧选择一位患者
        </div>
        <PatientDetail v-else :patient-id="selectedId" :key="selectedId + reloadKey" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import PatientList from '../components/PatientList.vue'
import PatientDetail from '../components/PatientDetail.vue'

const auth = useAuthStore()
const router = useRouter()
const selectedId = ref(null)
const reloadKey = ref(0)

const roleLabel = {
  attending: '主治医生', mdt_expert: 'MDT会诊专家', nurse: '护士', readonly: '历史只读医生',
}[auth.role] || auth.role

function onSelect(id) {
  selectedId.value = id
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

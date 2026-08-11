<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-100 to-blue-100">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand-600 text-white text-2xl font-bold mb-3">医</div>
        <h1 class="text-2xl font-bold text-slate-800">医院诊疗 Agent 工作台</h1>
        <p class="text-sm text-slate-500 mt-1">LangGraph Workflow + 可插拔 SubAgent · Demo</p>
      </div>

      <form @submit.prevent="onLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-600 mb-1">用户名</label>
          <input v-model="username" type="text" autocomplete="username"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-600 mb-1">密码</label>
          <input v-model="password" type="password" autocomplete="current-password"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <button type="submit" :disabled="loading"
          class="w-full py-2.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-60">
          {{ loading ? '登录中…' : '登 录' }}
        </button>
        <p v-if="error" class="text-sm text-red-600 text-center">{{ error }}</p>
      </form>

      <div class="mt-6 border-t border-slate-100 pt-4">
        <p class="text-xs text-slate-400 mb-2">演示账号（密码均为 123456，点击快速填充）：</p>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="a in accounts" :key="a.username" type="button" @click="fill(a.username)"
            class="text-left px-3 py-2 rounded-lg border border-slate-200 hover:border-brand-400 hover:bg-brand-50">
            <div class="text-sm font-medium text-slate-700">{{ a.name }}</div>
            <div class="text-xs text-slate-400">{{ a.username }} · {{ a.desc }}</div>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const username = ref('attending')
const password = ref('123456')
const loading = ref(false)
const error = ref('')

const accounts = [
  { username: 'admin', name: '系统管理员', desc: '后台管理' },
  { username: 'attending', name: '张明 · 主治医生', desc: '全权工作台' },
  { username: 'mdtexpert', name: '李华 · MDT专家', desc: '仅评论' },
  { username: 'nurse', name: '王芳 · 护士', desc: '分诊只读' },
  { username: 'readonly', name: '陈强 · 只读医生', desc: '全病案只读' },
]

function fill(u) {
  username.value = u
  password.value = '123456'
}

async function onLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    // admin 角色默认进后台管理，其他角色进工作台
    router.push(auth.isAdmin ? '/admin' : '/workstation')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-screen flex flex-col">
    <!-- 顶部栏 -->
    <header class="h-14 bg-slate-900 text-white flex items-center px-4 gap-4 shrink-0">
      <div class="flex items-center gap-2">
        <span class="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center font-bold">管</span>
        <span class="font-semibold">后台管理工作台</span>
        <span class="text-xs text-slate-400 ml-2">主数据 · RAG · Agent · 病案 · 审计</span>
      </div>
      <div class="ml-auto flex items-center gap-3 text-sm">
        <span class="text-slate-300">{{ auth.user?.name }}（管理员）</span>
        <router-link to="/workstation" class="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600">返回工作台</router-link>
        <button @click="logout" class="px-3 py-1 rounded bg-slate-700 hover:bg-red-600">退出</button>
      </div>
    </header>

    <!-- 主体：分组侧边导航 + 子路由出口 -->
    <div class="flex-1 flex overflow-hidden">
      <nav class="w-56 bg-slate-800 text-slate-300 py-3 shrink-0 overflow-y-auto">
        <template v-for="g in menuGroups" :key="g.title">
          <div class="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">{{ g.title }}</div>
          <router-link
            v-for="m in g.items"
            :key="m.to"
            :to="m.to"
            class="block px-4 py-2 text-sm hover:bg-slate-700 hover:text-white"
            active-class="bg-slate-700 text-white border-l-2 border-brand-500"
          >
            {{ m.label }}
          </router-link>
        </template>
      </nav>

      <main class="flex-1 overflow-auto p-6 bg-slate-100">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const menuGroups = [
  {
    title: '基础主数据',
    items: [
      { to: '/admin/buildings', label: '楼宇&楼层' },
      { to: '/admin/departments', label: '科室管理' },
      { to: '/admin/users', label: '医生人员' },
      { to: '/admin/exam-items', label: '检验项目' },
    ],
  },
  {
    title: 'RAG知识库',
    items: [
      { to: '/admin/rag', label: '文档管理' },
      { to: '/admin/kb', label: '简易知识库' },
    ],
  },
  {
    title: 'Agent配置',
    items: [
      { to: '/admin/agents', label: 'Agent开关' },
      { to: '/admin/permissions', label: '权限矩阵' },
    ],
  },
  {
    title: '病案&审计',
    items: [
      { to: '/admin/cases', label: '病案查阅' },
      { to: '/admin/audit', label: '系统审计' },
    ],
  },
]

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

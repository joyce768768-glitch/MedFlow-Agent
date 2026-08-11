<template>
  <nav class="fixed bottom-0 left-0 right-0 z-20">
    <div class="w-full max-w-md mx-auto bg-white border-t border-slate-100">
      <div class="grid grid-cols-4">
        <router-link
          v-for="tab in navItems"
          :key="tab.key"
          :to="tab.path"
          :class="[
            'flex flex-col items-center justify-center py-2.5 gap-0.5 transition-colors',
            isActive(tab.path)
              ? 'text-brand-600'
              : 'text-slate-400 hover:text-slate-600',
          ]"
        >
          <span class="text-lg leading-none">{{ tab.icon }}</span>
          <span class="text-xs">{{ tab.label }}</span>
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { key: 'home', icon: '🏠', label: '首页', path: '/patient/home' },
  { key: 'booking', icon: '📅', label: '挂号', path: '/patient/booking' },
  { key: 'reports', icon: '📋', label: '报告', path: '/patient/reports' },
  { key: 'profile', icon: '👤', label: '我的', path: '/patient/profile' },
]

function isActive(path) {
  return route.path.startsWith(path)
}
</script>
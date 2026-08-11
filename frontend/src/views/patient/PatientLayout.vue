<template>
  <div class="patient-app min-h-screen bg-slate-50" :class="fontClass">
    <!-- 移动端容器 -->
    <div class="max-w-md mx-auto min-h-screen bg-white shadow-xl relative">
      <!-- 顶部状态栏 -->
      <header class="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-100">
        <div class="flex items-center justify-between px-4 py-3">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white text-sm font-bold">M</div>
            <span class="font-semibold text-slate-800">MedFlow</span>
            <span class="text-xs text-slate-400 ml-1">患者端</span>
          </div>
          <button v-if="isOnPatientPage" @click="patientStore.logout()" class="text-xs text-slate-400 hover:text-red-500">退出</button>
        </div>
      </header>

      <!-- 主内容区 -->
      <main class="pb-20 min-h-[calc(100vh-64px)]">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <!-- 底部导航栏 -->
      <PatientBottomNav />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { usePatientStore } from '../../stores/patient'
import PatientBottomNav from './PatientBottomNav.vue'

const route = useRoute()
const patientStore = usePatientStore()

const isOnPatientPage = computed(() => route.path.startsWith('/patient'))
const fontClass = computed(() => {
  const scale = patientStore.fontScale
  return scale === 2 ? 'text-lg' : scale === 1 ? 'text-base' : 'text-sm'
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>

<template>
  <span :class="cls" class="text-xs px-2 py-0.5 rounded-full">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ status: String })
const map = { waiting: '待接诊', in_progress: '诊疗中', archived: '已归档' }
const label = computed(() => map[props.status] || props.status)
const cls = computed(() => ({
  'bg-yellow-100 text-yellow-700': props.status === 'waiting',
  'bg-green-100 text-green-700': props.status === 'in_progress',
  'bg-slate-200 text-slate-600': props.status === 'archived',
}))
</script>

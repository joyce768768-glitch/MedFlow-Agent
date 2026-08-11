<template>
  <span :class="cls" class="text-xs px-2 py-0.5 rounded-full">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ status: String })
const map = { ordered: '已开立', pending: '待执行', done: '已完成' }
const label = computed(() => map[props.status] || props.status)
const cls = computed(() => ({
  'bg-blue-100 text-blue-700': props.status === 'ordered',
  'bg-amber-100 text-amber-700': props.status === 'pending',
  'bg-green-100 text-green-700': props.status === 'done',
}))
</script>

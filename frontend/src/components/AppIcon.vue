<script setup>
defineProps({ name: { type: String, default: 'spark' }, size: { type: Number, default: 20 } })
const paths = {
  grid: ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M3 14h7v7H3z', 'M14 14h7v7h-7z'],
  spark: ['m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z', 'M20 2v4', 'M18 4h4'],
  ticket: ['M4 5h16v5a2 2 0 0 0 0 4v5H4v-5a2 2 0 0 0 0-4Z', 'M15 5v3m0 3v2m0 3v3'],
  clock: ['M12 8v5l3 2', 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0'],
  arrow: ['M5 12h14', 'm13 6 6 6-6 6'],
  search: ['M20 20l-5-5', 'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0'],
  refresh: ['M20 7v5h-5', 'M4 17v-5h5', 'M6 7a7 7 0 0 1 11-2l3 3', 'M18 17a7 7 0 0 1-11 2l-3-3'],
  close: ['m6 6 12 12', 'M18 6 6 18'],
  plus: ['M12 5v14', 'M5 12h14'],
  send: ['M12 19V5', 'm6 11 6-6 6 6'],
  user: ['M20 21v-2a7 7 0 0 0-14 0v2', 'M17 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0'],
  exit: ['M9 4H4v16h5', 'M9 12h12', 'm17 8 4 4-4 4'],
  calendar: ['M5 5h14v15H5z', 'M8 3v4m8-4v4M5 10h14'],
}
</script>
<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="(path, index) in (paths[name] || paths.spark)" :key="index" :d="path" /></svg>
</template>

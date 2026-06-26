<template>
  <section class="metric-card">
    <span>{{ label }}</span>
    <strong>{{ value }}</strong>
    <small v-if="hint">{{ hint }}</small>
  </section>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  hint: String
})
</script>

<template>
  <section class="panel">
    <div class="panel-title">
      <h2>{{ title }}</h2>
      <span class="pill" :class="{ accent: allowed }">{{ allowed ? '会员可见' : '权限受限' }}</span>
    </div>
    <pre class="report-content">{{ content }}</pre>
  </section>
</template>

<script setup>
defineProps({
  title: String,
  content: String,
  allowed: Boolean
})
</script>

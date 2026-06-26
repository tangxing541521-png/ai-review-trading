<template>
  <div class="page">
    <h1>免责声明</h1>
    <section class="panel warning-panel">
      <h2>{{ data.title || '免责声明' }}</h2>
      <p class="big-warning">{{ data.content }}</p>
      <ul>
        <li v-for="item in data.details" :key="item">{{ item }}</li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const data = ref({ details: [] })
onMounted(async () => {
  const res = await api.disclaimer()
  data.value = res.data || { details: [] }
})
</script>

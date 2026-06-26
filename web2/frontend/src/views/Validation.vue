<template>
  <div class="page">
    <h1>Forward Validation 验证结果</h1>
    <ReportPanel :title="report.title" :content="report.content" :allowed="report.allowed" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import ReportPanel from '../components/ReportPanel.vue'
import { api } from '../services/api'

const report = ref({ title: 'Validation', content: '加载中...', allowed: false })
onMounted(async () => {
  const res = await api.validation()
  report.value = {
    allowed: res.allowed,
    ...(res.data || {})
  }
})
</script>

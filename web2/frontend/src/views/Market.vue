<template>
  <div class="page">
    <h1>今日市场</h1>
    <div class="metric-grid">
      <MetricCard label="市场状态" :value="data.market_status" />
      <MetricCard label="允许交易" :value="data.allow_trade" />
      <MetricCard label="风险等级" :value="data.risk_level" />
      <MetricCard label="今日收益" :value="`${data.daily_return || '暂无'}%`" />
    </div>
    <section class="panel">
      <h2>免费用户可见摘要</h2>
      <p>当前仅展示市场状态、风险等级和免责声明。完整报告、推荐股票和订单详情仅会员可见。</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import { api } from '../services/api'

const data = ref({})
onMounted(async () => {
  data.value = await api.dashboard()
})
</script>

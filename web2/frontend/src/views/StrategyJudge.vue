<template>
  <div class="page">
    <h1>Strategy Judge</h1>
    <section v-if="!data.allowed" class="panel locked">
      <h2>会员权限</h2>
      <p>请升级会员后查看策略评分。</p>
    </section>
    <template v-else>
      <div class="hero-card" :class="scoreClass">
        <span>策略健康分</span>
        <strong>{{ data.health?.strategy_health_score || '0' }}/100</strong>
        <small>{{ data.health?.rating }}</small>
      </div>
      <div class="metric-grid">
        <MetricCard label="胜率" :value="metric('胜率')" />
        <MetricCard label="盈亏比" :value="metric('盈亏比')" />
        <MetricCard label="最大回撤" :value="metric('最大回撤')" />
        <MetricCard label="是否建议进入模拟盘" :value="suggestPaper" />
      </div>
      <section class="panel">
        <h2>最大风险点</h2>
        <p>{{ data.health?.sample_warning || '暂无' }}</p>
      </section>
      <section class="panel">
        <h2>完整指标</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>指标</th><th>数值</th><th>单位</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-if="!data.metrics.length">
                <td colspan="4">暂无数据，请先运行今日策略。</td>
              </tr>
              <tr v-for="row in data.metrics" :key="row.metric">
                <td>{{ row.metric }}</td>
                <td class="num">{{ row.value }}</td>
                <td>{{ row.unit }}</td>
                <td>{{ row.description }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import { api } from '../services/api'

const data = ref({ allowed: false, health: {}, metrics: [] })
const scoreClass = computed(() => {
  const score = Number(data.value.health?.strategy_health_score || 0)
  if (score >= 60) return 'positive'
  if (score >= 40) return 'neutral'
  return 'negative'
})
const suggestPaper = computed(() => Number(data.value.health?.strategy_health_score || 0) >= 60 ? 'YES' : 'NO')
function metric(name) {
  const row = (data.value.metrics || []).find((item) => item.metric === name)
  return row ? `${row.value}${row.unit || ''}` : '暂无'
}
onMounted(async () => {
  const res = await api.strategyJudge()
  data.value = {
    allowed: res.allowed,
    ...(res.data || {}),
    health: res.data?.health || {},
    metrics: Array.isArray(res.data?.metrics) ? res.data.metrics : []
  }
})
</script>

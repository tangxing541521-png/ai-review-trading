<template>
  <div class="page">
    <h1>Paper Trading 虚拟账户</h1>
    <section v-if="!paper.allowed" class="panel locked">
      <h2>会员权限</h2>
      <p>请升级会员后查看 Paper Trading 账户。</p>
    </section>
    <template v-else>
      <div class="metric-grid">
        <MetricCard label="账户总资产" :value="paper.account?.total_assets || '暂无'" />
        <MetricCard label="现金" :value="paper.account?.cash || '暂无'" />
        <MetricCard label="持仓市值" :value="paper.account?.market_value || '暂无'" />
        <MetricCard label="累计收益" :value="`${paper.account?.cumulative_return || '0'}%`" />
      </div>
      <section class="chart-grid">
        <div class="chart-card">
          <h2>资金曲线</h2>
          <p v-if="!paper.equity_curve.length">暂无足够数据，请继续前向验证</p>
          <div ref="assetsChart" class="chart-box"></div>
        </div>
        <div class="chart-card">
          <h2>累计收益曲线</h2>
          <p v-if="!paper.equity_curve.length">暂无足够数据，请继续前向验证</p>
          <div ref="returnChart" class="chart-box"></div>
        </div>
        <div class="chart-card">
          <h2>最大回撤曲线</h2>
          <p v-if="!paper.equity_curve.length">暂无足够数据，请继续前向验证</p>
          <div ref="drawdownChart" class="chart-box"></div>
        </div>
      </section>
      <section class="panel">
        <h2>当前持仓</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>代码</th><th>名称</th><th>成本价</th><th>现价</th><th>浮盈亏</th><th>持仓天数</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-if="!paper.positions.length">
                <td colspan="7">暂无数据，请先运行今日策略。</td>
              </tr>
              <tr v-for="pos in paper.positions" :key="`${pos.stock_code}-${pos.buy_date}`">
                <td>{{ pos.stock_code }}</td>
                <td>{{ pos.name }}</td>
                <td>{{ pos.cost_price }}</td>
                <td>{{ pos.latest_price }}</td>
                <td :class="Number(pos.floating_pnl || 0) >= 0 ? 'positive-text' : 'negative-text'">{{ pos.floating_pnl }}</td>
                <td>{{ pos.holding_days }}</td>
                <td>{{ pos.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="panel">
        <h2>资金曲线表格</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>日期</th><th>现金</th><th>持仓市值</th><th>总资产</th><th>今日收益</th><th>累计收益</th><th>最大回撤</th></tr>
            </thead>
            <tbody>
              <tr v-if="!paper.equity_curve.length">
                <td colspan="7">暂无数据，请先运行今日策略。</td>
              </tr>
              <tr v-for="row in paper.equity_curve" :key="row.date">
                <td>{{ row.date }}</td>
                <td>{{ row.cash }}</td>
                <td>{{ row.market_value }}</td>
                <td>{{ row.total_assets }}</td>
                <td :class="Number(row.daily_return || 0) >= 0 ? 'positive-text' : 'negative-text'">{{ row.daily_return }}%</td>
                <td>{{ row.cumulative_return }}%</td>
                <td class="negative-text">{{ row.max_drawdown }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
    <ReportPanel :title="report.title" :content="report.content" :allowed="report.allowed" />
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { nextTick, onMounted, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import ReportPanel from '../components/ReportPanel.vue'
import { api } from '../services/api'

const report = ref({ title: 'Paper Trading', content: '加载中...', allowed: false })
const paper = ref({ allowed: false, account: {}, positions: [], equity_curve: [] })
const assetsChart = ref(null)
const returnChart = ref(null)
const drawdownChart = ref(null)

function num(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function renderLine(el, title, dates, values, color, suffix = '') {
  if (!el || !dates.length) return
  const chart = echarts.init(el)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: '#0b1723', borderColor: '#25415b', textStyle: { color: '#e7eef8' } },
    grid: { left: 42, right: 18, top: 24, bottom: 34 },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#25415b' } }, axisLabel: { color: '#8aa2b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#8aa2b8', formatter: `{value}${suffix}` }, splitLine: { lineStyle: { color: '#14283b' } } },
    series: [{ name: title, type: 'line', smooth: true, showSymbol: true, data: values, lineStyle: { color, width: 3 }, itemStyle: { color }, areaStyle: { color: `${color}22` } }]
  })
}

function renderCharts() {
  const rows = paper.value.equity_curve || []
  const dates = rows.map((row) => row.date)
  renderLine(assetsChart.value, '总资产', dates, rows.map((row) => num(row.total_assets)), '#00c2ff')
  renderLine(returnChart.value, '累计收益', dates, rows.map((row) => num(row.cumulative_return)), '#35d07f', '%')
  renderLine(drawdownChart.value, '最大回撤', dates, rows.map((row) => num(row.max_drawdown)), '#ff6b6b', '%')
}

onMounted(async () => {
  const [paperData, paperReport] = await Promise.all([api.paperData(), api.paperAccount()])
  paper.value = {
    allowed: paperData.allowed,
    ...(paperData.data || {}),
    positions: Array.isArray(paperData.data?.positions) ? paperData.data.positions : [],
    equity_curve: Array.isArray(paperData.data?.equity_curve) ? paperData.data.equity_curve : []
  }
  report.value = {
    allowed: paperReport.allowed,
    ...(paperReport.data || {})
  }
  await nextTick()
  renderCharts()
})
</script>

<style scoped>
.chart-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.chart-card {
  border: 1px solid #183047;
  border-radius: 8px;
  background: rgba(9, 18, 29, 0.94);
  padding: 18px;
}

.chart-card h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.chart-card p {
  color: #8aa2b8;
  margin: 0 0 10px;
}

.chart-box {
  height: 260px;
}

@media (max-width: 980px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>

<template>
  <div class="page">
    <h1>冻结订单</h1>
    <section v-if="!data.allowed" class="panel locked">
      <h2>会员权限</h2>
      <p>请升级会员后查看冻结订单。</p>
    </section>
    <template v-else>
      <div class="metric-grid">
        <MetricCard label="是否已冻结" :value="data.is_frozen ? 'YES' : 'NO'" />
        <MetricCard label="冻结时间" :value="data.freeze_time || '暂无'" />
        <MetricCard label="订单数量" :value="data.order_count || 0" />
        <MetricCard label="日期" :value="data.date || '暂无'" />
      </div>
      <section class="panel">
        <div class="panel-title">
          <h2>今日冻结订单</h2>
          <span class="pill">只读</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>股票代码</th>
                <th>action</th>
                <th>position_ratio</th>
                <th>score</th>
                <th>cycle</th>
                <th>reason</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!data.orders.length">
                <td colspan="6">暂无数据，请先运行今日策略。</td>
              </tr>
              <tr v-for="order in data.orders" :key="`${order.stock_code}-${order.action}`">
                <td>{{ order.stock_code }}</td>
                <td :class="actionClass(order.action)">{{ order.action }}</td>
                <td class="num">{{ order.position_ratio }}</td>
                <td class="num">{{ order.score }}</td>
                <td>{{ order.cycle }}</td>
                <td>{{ order.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import { api } from '../services/api'

const data = ref({ allowed: false, orders: [] })
function actionClass(action) {
  if (action === 'BUY') return 'positive-text'
  if (action === 'SELL') return 'negative-text'
  return 'muted-text'
}
onMounted(async () => {
  const res = await api.frozenOrders()
  data.value = {
    allowed: res.allowed,
    ...(res.data || {}),
    orders: Array.isArray(res.data?.orders) ? res.data.orders : []
  }
})
</script>

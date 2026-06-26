<template>
  <div class="page">
    <h1>龙头排行榜</h1>
    <section v-if="!data.allowed" class="panel locked">
      <h2>会员权限</h2>
      <p>请升级会员后查看龙头排行榜。</p>
    </section>
    <section v-else class="panel">
      <div class="panel-title">
        <h2>Leader Board</h2>
        <span class="pill accent">Top {{ data.items?.length || 0 }}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>股票代码</th>
              <th>股票名称</th>
              <th>master_score</th>
              <th>leader_tier</th>
              <th>momentum_score</th>
              <th>trend_score</th>
              <th>risk_level</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!data.items.length">
              <td colspan="7">暂无数据，请先运行今日策略。</td>
            </tr>
            <tr v-for="item in data.items" :key="item.code">
              <td>{{ item.code }}</td>
              <td>{{ item.name }}</td>
              <td class="num positive-text">{{ item.master_score }}</td>
              <td>{{ item.leader_tier }}</td>
              <td class="num">{{ item.momentum_score }}</td>
              <td class="num">{{ item.trend_score }}</td>
              <td class="num negative-text">{{ item.risk_level }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const data = ref({ allowed: false, items: [] })
onMounted(async () => {
  const res = await api.leaders()
  data.value = {
    allowed: res.allowed,
    items: Array.isArray(res.data) ? res.data : []
  }
})
</script>

<template>
  <main class="command-center">
    <header class="page-head">
      <div>
        <p class="eyebrow">AI Trading Command Center</p>
        <h1>AI交易指挥舱</h1>
      </div>
      <span class="status-badge">本地模拟</span>
    </header>

    <section class="decision-card">
      <div class="section-title">
        <span>01</span>
        <h2>今日决策</h2>
      </div>
      <div class="decision-grid">
        <div class="metric-box">
          <small>市场状态</small>
          <strong>{{ dashboard.market_status || '暂无' }}</strong>
        </div>
        <div class="metric-box">
          <small>是否允许交易</small>
          <strong :class="dashboard.allow_trade === 'YES' ? 'up' : 'flat'">
            {{ dashboard.allow_trade || '暂无' }}
          </strong>
        </div>
        <div class="metric-box">
          <small>建议仓位</small>
          <strong>{{ dashboard.position_advice || '暂无' }}</strong>
        </div>
        <div class="metric-box">
          <small>风险等级</small>
          <strong class="risk">{{ dashboard.risk_level || '暂无' }}</strong>
        </div>
      </div>
    </section>

    <section class="panel-grid">
      <div class="module-card">
        <div class="section-title">
          <span>02</span>
          <h2>今日核心标的</h2>
        </div>
        <div class="target-list">
          <div v-for="item in placeholderTargets" :key="item.code" class="target-row">
            <div>
              <strong>{{ item.name }}</strong>
              <small>{{ item.code }}</small>
            </div>
            <span>{{ item.role }}</span>
          </div>
        </div>
      </div>

      <div class="module-card">
        <div class="section-title">
          <span>03</span>
          <h2>系统表现</h2>
        </div>
        <div class="performance-grid">
          <div>
            <small>模拟收益</small>
            <strong>0%</strong>
          </div>
          <div>
            <small>最大回撤</small>
            <strong>0%</strong>
          </div>
          <div>
            <small>胜率</small>
            <strong>0%</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="summary-card">
      <div class="section-title">
        <span>04</span>
        <h2>AI总结</h2>
      </div>
      <p>系统初始化中</p>
    </section>

    <button class="run-button" type="button" @click="runTodayStrategy">
      运行今日策略
    </button>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const dashboard = ref({})
const placeholderTargets = ref([
  { code: '-', name: '暂无核心标的', role: '等待数据' }
])

function runTodayStrategy() {
  window.alert('运行今日策略：当前为前端占位按钮，后续接入本地策略执行 API。')
}

onMounted(async () => {
  const dashboardRes = await api.dashboard()
  dashboard.value = dashboardRes.data || {}
  const res = await api.leaders()
  placeholderTargets.value = Array.isArray(res.data) && res.data.length
    ? res.data.slice(0, 3).map((item) => ({
        code: item.code,
        name: item.name,
        role: item.leader_tier || '核心标的'
      }))
    : [{ code: '-', name: '暂无数据，请先运行今日策略。', role: '等待数据' }]
})
</script>

<style scoped>
.command-center {
  min-height: calc(100vh - 64px);
  padding: 28px;
  color: #e7eef8;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #7f99ad;
  font-size: 13px;
  letter-spacing: 0;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 32px;
  letter-spacing: 0;
}

.status-badge {
  border: 1px solid #25415b;
  border-radius: 999px;
  color: #00c2ff;
  padding: 8px 14px;
  background: rgba(0, 194, 255, 0.08);
}

.decision-card,
.module-card,
.summary-card {
  border: 1px solid #183047;
  border-radius: 8px;
  background: rgba(9, 18, 29, 0.94);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}

.decision-card {
  padding: 22px;
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.section-title span {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: #10263a;
  color: #00c2ff;
  font-size: 13px;
  font-weight: 800;
}

.section-title h2 {
  font-size: 18px;
}

.decision-grid,
.performance-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-box,
.performance-grid > div {
  min-height: 104px;
  border: 1px solid #14283b;
  border-radius: 8px;
  background: #08131f;
  padding: 16px;
}

small {
  display: block;
  color: #8199ad;
  font-size: 13px;
}

strong {
  display: block;
  margin-top: 12px;
  color: #f3f8ff;
  font-size: 24px;
  line-height: 1.2;
}

.up {
  color: #35d07f;
}

.risk {
  color: #ff6b6b;
}

.flat {
  color: #8aa2b8;
}

.panel-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 16px;
  margin-bottom: 16px;
}

.module-card,
.summary-card {
  padding: 20px;
}

.target-list {
  display: grid;
  gap: 10px;
}

.target-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid #14283b;
  border-radius: 8px;
  background: #08131f;
  padding: 14px 16px;
}

.target-row strong {
  margin-top: 0;
  font-size: 18px;
}

.target-row span {
  color: #8aa2b8;
  font-size: 13px;
}

.performance-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-card {
  margin-bottom: 18px;
}

.summary-card p {
  border-left: 3px solid #00c2ff;
  background: #08131f;
  border-radius: 6px;
  color: #d7e7f3;
  padding: 16px;
}

.run-button {
  width: 100%;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(135deg, #00c2ff, #35d07f);
  color: #041019;
  cursor: pointer;
  font-size: 18px;
  font-weight: 800;
  padding: 16px 20px;
}

@media (max-width: 980px) {
  .decision-grid,
  .panel-grid,
  .performance-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}
</style>

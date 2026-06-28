<template>
  <main class="agent-page">
    <section class="hero-card">
      <div>
        <p class="eyebrow">AI Trader Agent V1</p>
        <h1>{{ agent.name || 'AI Trader' }}</h1>
        <p class="summary">当前任务：{{ payload.current_task || '等待机会' }}，下一步：{{ payload.next_action || '继续观察' }}</p>
      </div>
      <div class="status-grid">
        <div><small>状态</small><strong>{{ agent.status || 'RUNNING' }}</strong></div>
        <div><small>版本</small><strong>{{ agent.version || '1.0' }}</strong></div>
        <div><small>模式</small><strong>{{ agent.mode || 'OBSERVE' }}</strong></div>
        <div><small>市场阶段</small><strong>{{ agent.market_stage || '暂无' }}</strong></div>
        <div><small>交易许可</small><strong :class="agent.allow_trade ? 'positive' : 'danger'">{{ agent.allow_trade ? 'YES' : 'NO' }}</strong></div>
        <div><small>心跳</small><strong>{{ agent.heartbeat || '-' }}</strong></div>
      </div>
    </section>

    <section class="stats-grid">
      <div><small>当前状态</small><strong>{{ payload.decision || 'WAIT' }}</strong></div>
      <div><small>信号</small><strong>{{ statistics.signals || 0 }}</strong></div>
      <div><small>观察</small><strong>{{ statistics.watch || 0 }}</strong></div>
      <div><small>取消</small><strong class="danger">{{ statistics.cancel || 0 }}</strong></div>
      <div><small>BUY</small><strong class="positive">{{ statistics.buy || 0 }}</strong></div>
      <div><small>已执行</small><strong>{{ statistics.executed || 0 }}</strong></div>
    </section>

    <section class="main-grid">
      <div class="panel">
        <div class="section-head">
          <span>FLOW</span>
          <div>
            <h2>Workflow</h2>
            <p>MarketHub → Decision → Auction → Realtime → 等待买点 → 订单 → Execution → Paper Trading → Review</p>
          </div>
        </div>
        <div class="timeline">
          <article v-for="(item, index) in workflow" :key="`${item.step}-${index}`" class="flow-step" :class="item.status.toLowerCase()">
            <div class="node">{{ index + 1 }}</div>
            <div>
              <h3>{{ item.step }}</h3>
              <p>{{ item.status }}</p>
            </div>
          </article>
        </div>
      </div>

      <div class="panel log-panel">
        <div class="section-head">
          <span>LOG</span>
          <div>
            <h2>当前日志</h2>
          </div>
        </div>
        <div class="log-stream">
          <p v-for="line in logs" :key="line">{{ line }}</p>
          <p v-if="!logs.length">暂无日志</p>
        </div>
      </div>
    </section>

    <section class="panel order-panel">
      <div class="section-head">
        <span>ORDER</span>
        <div>
          <h2>Order Queue</h2>
          <p>本阶段不自动下单，订单队列仅展示等待人工确认的模拟队列。</p>
        </div>
      </div>
      <div v-if="orderQueue.length" class="order-list">
        <article v-for="order in orderQueue" :key="`${order.code}-${order.action}`">
          <strong>{{ order.code }}</strong>
          <span>{{ order.action }}</span>
        </article>
      </div>
      <div v-else class="empty-order">暂无订单</div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'

const payload = ref({})
const agent = computed(() => payload.value.agent || {})
const statistics = computed(() => payload.value.statistics || {})
const workflow = computed(() => Array.isArray(payload.value.workflow) ? payload.value.workflow : [])
const logs = computed(() => Array.isArray(payload.value.log) ? payload.value.log : [])
const orderQueue = computed(() => Array.isArray(payload.value.order_queue) ? payload.value.order_queue : [])

async function loadTraderAgent() {
  const response = await api.traderAgent()
  payload.value = response.data || {}
}

onMounted(loadTraderAgent)
</script>

<style scoped>
.agent-page {
  min-height: calc(100vh - 64px);
  padding: 28px;
  color: #e7eef8;
  background:
    radial-gradient(circle at 18% 0%, rgba(0, 194, 255, 0.12), transparent 30%),
    radial-gradient(circle at 88% 14%, rgba(53, 208, 127, 0.1), transparent 28%);
}

.hero-card,
.panel,
.stats-grid > div {
  border: 1px solid rgba(57, 104, 140, 0.46);
  border-radius: 18px;
  background: linear-gradient(145deg, rgba(9, 18, 29, 0.96), rgba(4, 13, 24, 0.94));
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.34);
}

.hero-card {
  display: grid;
  grid-template-columns: 1fr 1.25fr;
  gap: 22px;
  margin-bottom: 22px;
  padding: 28px;
}

.eyebrow {
  color: #00c2ff;
  font-size: 13px;
  font-weight: 900;
  margin: 0 0 10px;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  color: #f3f8ff;
  font-size: clamp(38px, 4.8vw, 64px);
  line-height: 1;
}

.summary {
  color: #c7d8e8;
  font-size: 20px;
  line-height: 1.7;
  margin-top: 22px;
}

.status-grid,
.stats-grid,
.main-grid {
  display: grid;
  gap: 14px;
}

.status-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.stats-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin-bottom: 22px;
}

.main-grid {
  grid-template-columns: 1.35fr 0.65fr;
}

.status-grid > div,
.stats-grid > div {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  min-width: 0;
  padding: 16px;
}

small {
  color: #8199ad;
  display: block;
  font-size: 13px;
}

strong {
  color: #f3f8ff;
  display: block;
  font-size: 25px;
  line-height: 1.2;
  margin-top: 10px;
  overflow-wrap: anywhere;
}

.positive {
  color: #35d07f !important;
}

.danger {
  color: #ff7d85 !important;
}

.panel {
  margin-bottom: 22px;
  padding: 24px;
}

.section-head {
  align-items: center;
  display: flex;
  gap: 14px;
  margin-bottom: 18px;
}

.section-head > span {
  background: linear-gradient(135deg, #00c2ff, #35d07f);
  border-radius: 10px;
  color: #041019;
  display: grid;
  font-weight: 900;
  height: 42px;
  place-items: center;
  width: 62px;
}

.section-head h2,
.flow-step h3 {
  color: #f3f8ff;
}

.section-head p,
.flow-step p {
  color: #8199ad;
  margin-top: 6px;
}

.timeline {
  display: grid;
  gap: 14px;
}

.flow-step {
  align-items: center;
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 16px;
}

.node {
  background: rgba(0, 194, 255, 0.14);
  border: 1px solid rgba(0, 194, 255, 0.3);
  border-radius: 999px;
  color: #5fdcff;
  display: grid;
  font-weight: 900;
  height: 42px;
  place-items: center;
  width: 42px;
}

.flow-step.done .node {
  background: rgba(53, 208, 127, 0.14);
  border-color: rgba(53, 208, 127, 0.3);
  color: #35d07f;
}

.flow-step.running .node {
  background: rgba(255, 183, 77, 0.14);
  border-color: rgba(255, 183, 77, 0.3);
  color: #ffca7a;
}

.log-stream {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  max-height: 420px;
  overflow: auto;
  padding: 16px;
}

.log-stream p {
  border-bottom: 1px solid rgba(20, 40, 59, 0.8);
  color: #d7e7f3;
  line-height: 1.8;
  padding: 8px 0;
}

.empty-order,
.order-list article {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  color: #8199ad;
  padding: 18px;
}

.order-list {
  display: grid;
  gap: 12px;
}

@media (max-width: 1100px) {
  .hero-card,
  .main-grid {
    grid-template-columns: 1fr;
  }

  .status-grid,
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .agent-page {
    padding: 18px;
  }

  .status-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>

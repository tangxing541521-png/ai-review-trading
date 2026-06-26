<template>
  <section class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Mainline Engine</p>
        <h1>AI 主线分析</h1>
      </div>
      <span class="emotion-badge">{{ mainline.market_emotion || '暂无数据' }}</span>
    </header>

    <section class="overview-grid">
      <div class="info-card">
        <small>市场情绪</small>
        <strong>{{ mainline.market_emotion || '暂无数据，请先运行今日策略' }}</strong>
      </div>
      <div class="info-card">
        <small>明日动作</small>
        <strong>{{ plan.action || '暂无数据' }}</strong>
      </div>
      <div class="info-card">
        <small>建议仓位</small>
        <strong>{{ plan.position || '暂无数据' }}</strong>
      </div>
      <div class="info-card">
        <small>数据样本</small>
        <strong>{{ dataStatus.leader_rows || 0 }} / {{ dataStatus.trend_rows || 0 }}</strong>
      </div>
    </section>

    <section class="panel">
      <div class="section-title">
        <span>01</span>
        <h2>主线排行榜</h2>
      </div>
      <div v-if="mainlines.length" class="mainline-list">
        <article v-for="item in mainlines" :key="item.theme" class="mainline-card">
          <div>
            <h3>{{ item.theme }}</h3>
            <p>龙头：{{ item.leader || '暂无' }} ｜ 趋势核心：{{ item.core_trend || '暂无' }}</p>
          </div>
          <strong>{{ item.heat_score }}</strong>
          <ul>
            <li v-for="reason in item.reason" :key="reason">{{ reason }}</li>
          </ul>
        </article>
      </div>
      <p v-else class="empty">暂无数据，请先运行今日策略。</p>
    </section>

    <section class="tier-grid">
      <div class="panel">
        <div class="section-title">
          <span>T1</span>
          <h2>核心龙头</h2>
        </div>
        <StockList :items="tiers.T1 || []" />
      </div>
      <div class="panel">
        <div class="section-title">
          <span>T2</span>
          <h2>补涨龙头</h2>
        </div>
        <StockList :items="tiers.T2 || []" />
      </div>
      <div class="panel">
        <div class="section-title">
          <span>TC</span>
          <h2>趋势核心</h2>
        </div>
        <StockList :items="tiers.trend_core || []" />
      </div>
    </section>

    <section class="plan-grid">
      <div class="panel">
        <div class="section-title">
          <span>02</span>
          <h2>明日计划</h2>
        </div>
        <div class="plan-box">
          <p><b>动作：</b>{{ plan.action || '暂无数据' }}</p>
          <p><b>仓位：</b>{{ plan.position || '暂无数据' }}</p>
          <p><b>买入条件：</b>{{ plan.buy_condition || '暂无数据，请先运行今日策略。' }}</p>
          <p><b>风险条件：</b>{{ plan.risk_condition || '暂无数据，请先运行今日策略。' }}</p>
        </div>
      </div>

      <div class="panel">
        <div class="section-title">
          <span>03</span>
          <h2>观察名单</h2>
        </div>
        <StockList :items="plan.watchlist || []" />
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { api } from '../services/api'

const mainline = ref({})

const mainlines = computed(() => mainline.value.mainlines || [])
const tiers = computed(() => mainline.value.leader_tiers || {})
const plan = computed(() => mainline.value.tomorrow_plan || {})
const dataStatus = computed(() => mainline.value.data_status || {})

const StockList = defineComponent({
  props: {
    items: {
      type: Array,
      default: () => []
    }
  },
  setup(props) {
    return () => {
      if (!props.items.length) {
        return h('p', { class: 'empty' }, '暂无数据，请先运行今日策略。')
      }
      return h(
        'div',
        { class: 'stock-list' },
        props.items.map((item) =>
          h('div', { class: 'stock-row', key: `${item.code}-${item.name}` }, [
            h('div', [h('strong', item.name || '-'), h('small', item.code || '-')]),
            h('span', item.score || item.master_score || '-')
          ])
        )
      )
    }
  }
})

onMounted(async () => {
  const response = await api.mainline()
  mainline.value = response.data || {}
})
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e7eef8;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.eyebrow,
small {
  color: #8199ad;
  font-size: 13px;
  margin: 0 0 6px;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  font-size: 32px;
}

.emotion-badge {
  border: 1px solid #25415b;
  border-radius: 999px;
  color: #35d07f;
  padding: 8px 14px;
  background: rgba(53, 208, 127, 0.08);
}

.overview-grid,
.tier-grid,
.plan-grid {
  display: grid;
  gap: 16px;
}

.overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
}

.tier-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 16px;
}

.plan-grid {
  grid-template-columns: 1fr 1fr;
}

.info-card,
.panel,
.mainline-card {
  border: 1px solid #183047;
  border-radius: 8px;
  background: rgba(9, 18, 29, 0.94);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}

.info-card,
.panel {
  padding: 20px;
}

.info-card strong {
  display: block;
  color: #f3f8ff;
  font-size: 26px;
  margin-top: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.section-title span {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: #10263a;
  color: #00c2ff;
  font-weight: 800;
}

.section-title h2 {
  font-size: 18px;
}

.mainline-list,
.stock-list {
  display: grid;
  gap: 10px;
}

.mainline-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 16px;
  padding: 16px;
}

.mainline-card h3 {
  color: #f3f8ff;
  font-size: 20px;
}

.mainline-card p,
.plan-box p {
  color: #b7c8d8;
  line-height: 1.8;
}

.mainline-card > strong {
  color: #35d07f;
  font-size: 26px;
}

.mainline-card ul {
  grid-column: 1 / -1;
  margin: 4px 0 0;
  padding-left: 18px;
  color: #d7e7f3;
  line-height: 1.7;
}

.stock-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid #14283b;
  border-radius: 8px;
  background: #08131f;
  padding: 12px 14px;
}

.stock-row strong {
  display: block;
  color: #f3f8ff;
}

.stock-row span {
  color: #35d07f;
  font-weight: 800;
}

.empty {
  border: 1px solid #14283b;
  border-radius: 8px;
  background: #08131f;
  color: #8199ad;
  padding: 16px;
}

.plan-box {
  display: grid;
  gap: 10px;
}

@media (max-width: 1100px) {
  .overview-grid,
  .tier-grid,
  .plan-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}
</style>

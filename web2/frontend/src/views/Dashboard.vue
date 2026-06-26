<template>
  <main class="brain-page">
    <section class="hero-section">
      <div class="hero-copy">
        <p class="eyebrow">Trading Brain Pro</p>
        <h1>AI 游资大脑</h1>
        <p class="one-line">{{ brain.decision?.summary || '暂无数据，请先运行今日策略。' }}</p>
        <div class="stars" aria-label="system confidence">★★★★★</div>
      </div>

      <div class="hero-grid">
        <div class="brain-stat-card primary">
          <small>今天属于</small>
          <strong>{{ brain.emotion?.stage || '暂无' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>市场情绪</small>
          <strong>{{ brain.emotion?.score ?? 0 }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>建议</small>
          <strong>{{ brain.decision?.action || '观察' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>建议仓位</small>
          <strong>{{ brain.position?.suggested_position || '0%' }}</strong>
        </div>
        <div class="brain-stat-card risk">
          <small>风险</small>
          <strong>{{ brain.risk?.risk_label || '暂无' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>主线</small>
          <strong>{{ brain.theme?.main_theme || '暂无主线' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>龙头</small>
          <strong>{{ firstName(tiers.T1) }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>补涨</small>
          <strong>{{ firstName(tiers.T2) }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>趋势核心</small>
          <strong>{{ firstName(tiers.trend_core) }}</strong>
        </div>
      </div>
    </section>

    <section class="section-card action-section">
      <div class="section-head">
        <span>01</span>
        <div>
          <h2>AI今日操作</h2>
          <p>基于 Market Brain 的统一结论，不做额外策略判断。</p>
        </div>
      </div>
      <div class="action-grid">
        <div class="action-tile">
          <small>可以买？</small>
          <strong :class="canBuy ? 'positive' : 'danger'">{{ canBuy ? 'YES' : 'NO' }}</strong>
        </div>
        <div class="action-tile">
          <small>建议</small>
          <strong>{{ actionLabel }}</strong>
        </div>
        <div class="reason-card">
          <small>操作理由</small>
          <p>{{ brain.position?.reason || '暂无数据，请先运行今日策略。' }}</p>
        </div>
        <div class="reason-card risk-copy">
          <small>风险提示</small>
          <p>{{ riskText }}</p>
        </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <span>02</span>
        <div>
          <h2>龙头梯队</h2>
          <p>T1、T2、趋势核心与观察名单统一来自 Market Brain。</p>
        </div>
      </div>
      <div class="tier-grid">
        <TierCard title="T1 核心龙头" :items="tiers.T1" accent="green" />
        <TierCard title="T2 补涨龙头" :items="tiers.T2" accent="blue" />
        <TierCard title="趋势核心" :items="tiers.trend_core" accent="cyan" />
        <TierCard title="观察名单" :items="brain.decision?.watchlist || []" accent="gray" />
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <span>03</span>
        <div>
          <h2>市场情绪</h2>
          <p>情绪分、风险分、建议仓位三块仪表盘。</p>
        </div>
      </div>
      <div class="gauge-grid">
        <div class="gauge-panel">
          <h3>情绪分</h3>
          <div ref="emotionGauge" class="gauge-box"></div>
        </div>
        <div class="gauge-panel">
          <h3>风险分</h3>
          <div ref="riskGauge" class="gauge-box"></div>
        </div>
        <div class="gauge-panel">
          <h3>建议仓位</h3>
          <div ref="positionGauge" class="gauge-box"></div>
        </div>
      </div>
    </section>

    <section class="section-card ai-comment">
      <div class="section-head">
        <span>04</span>
        <div>
          <h2>AI点评</h2>
          <p>统一市场大脑输出的自然语言摘要。</p>
        </div>
      </div>
      <div class="chat-card">
        <div class="avatar">AI</div>
        <div class="chat-content">
          <h3>今日总评</h3>
          <p>{{ brain.decision?.summary || '暂无数据，请先运行今日策略。' }}</p>
          <h3>情绪描述</h3>
          <p>{{ brain.emotion?.description || '暂无数据。' }}</p>
          <h3>风险提示</h3>
          <ul>
            <li v-for="item in warnings" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, defineComponent, h, nextTick, onMounted, ref } from 'vue'
import { api } from '../services/api'

const brain = ref({})
const emotionGauge = ref(null)
const riskGauge = ref(null)
const positionGauge = ref(null)

const tiers = computed(() => brain.value.leader?.tier_summary || {})
const warnings = computed(() => brain.value.risk?.warnings || ['暂无风险提示。'])
const canBuy = computed(() => !['防守', '观察'].includes(brain.value.decision?.action))
const actionLabel = computed(() => {
  const position = positionNumber(brain.value.position?.suggested_position)
  if (position >= 90) return '满仓'
  if (position >= 50) return '半仓'
  if (position > 0) return '轻仓'
  return brain.value.decision?.action || '观察'
})
const riskText = computed(() => warnings.value.join('；'))

const TierCard = defineComponent({
  props: {
    title: { type: String, required: true },
    items: { type: Array, default: () => [] },
    accent: { type: String, default: 'green' }
  },
  setup(props) {
    return () =>
      h('article', { class: ['tier-card', `accent-${props.accent}`] }, [
        h('h3', props.title),
        props.items?.length
          ? h(
              'div',
              { class: 'stock-stack' },
              props.items.slice(0, 5).map((item) =>
                h('div', { class: 'stock-row', key: `${item.code}-${item.name}` }, [
                  h('div', [h('strong', item.name || '-'), h('small', item.code || '-')]),
                  h('span', item.score ?? item.master_score ?? '-')
                ])
              )
            )
          : h('p', { class: 'empty' }, '暂无数据，请先运行今日策略。')
      ])
  }
})

function firstName(items = []) {
  return items?.[0]?.name || '暂无'
}

function numberValue(value) {
  const parsed = Number(String(value ?? '0').replace('%', ''))
  return Number.isFinite(parsed) ? parsed : 0
}

function positionNumber(value) {
  return Math.max(0, Math.min(100, numberValue(value)))
}

function renderGauge(el, value, name, color) {
  if (!el) return
  const chart = echarts.init(el)
  chart.setOption({
    backgroundColor: 'transparent',
    series: [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        radius: '92%',
        progress: { show: true, width: 14, itemStyle: { color } },
        axisLine: { lineStyle: { width: 14, color: [[1, '#13283d']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: '#7f99ad', distance: 18 },
        pointer: { width: 4, itemStyle: { color } },
        title: { color: '#8aa2b8', fontSize: 13, offsetCenter: [0, '68%'] },
        detail: { color: '#f3f8ff', fontSize: 30, fontWeight: 800, formatter: '{value}', offsetCenter: [0, '38%'] },
        data: [{ value: Math.round(Math.max(0, Math.min(100, value))), name }]
      }
    ]
  })
}

function renderAllGauges() {
  renderGauge(emotionGauge.value, numberValue(brain.value.emotion?.score), 'Emotion', '#35d07f')
  renderGauge(riskGauge.value, numberValue(brain.value.risk?.risk_level), 'Risk', '#ff5d66')
  renderGauge(positionGauge.value, positionNumber(brain.value.position?.suggested_position), 'Position', '#00c2ff')
}

onMounted(async () => {
  const response = await api.marketBrain()
  brain.value = response.data || {}
  await nextTick()
  renderAllGauges()
})
</script>

<style scoped>
.brain-page {
  min-height: calc(100vh - 64px);
  padding: 28px;
  color: #e7eef8;
  background:
    radial-gradient(circle at 20% 0%, rgba(0, 194, 255, 0.12), transparent 32%),
    radial-gradient(circle at 90% 12%, rgba(53, 208, 127, 0.1), transparent 28%);
}

.hero-section,
.section-card {
  border: 1px solid rgba(57, 104, 140, 0.46);
  border-radius: 18px;
  background: linear-gradient(145deg, rgba(9, 18, 29, 0.96), rgba(4, 13, 24, 0.94));
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.36);
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(280px, 0.82fr) 1.18fr;
  gap: 24px;
  margin-bottom: 22px;
  overflow: hidden;
  padding: 28px;
  position: relative;
}

.hero-section::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, rgba(0, 194, 255, 0.09), transparent 50%, rgba(53, 208, 127, 0.08));
  pointer-events: none;
}

.hero-copy,
.hero-grid,
.section-card {
  position: relative;
}

.eyebrow {
  color: #00c2ff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
  margin: 0 0 10px;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  color: #f3f8ff;
  font-size: clamp(38px, 5vw, 72px);
  letter-spacing: 0;
  line-height: 1;
}

.one-line {
  color: #c7d8e8;
  font-size: 20px;
  line-height: 1.7;
  margin-top: 24px;
  max-width: 720px;
}

.stars {
  color: #35d07f;
  font-size: 26px;
  letter-spacing: 4px;
  margin-top: 24px;
}

.hero-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.brain-stat-card,
.action-tile,
.reason-card,
.gauge-panel,
.tier-card,
.chat-card {
  border: 1px solid rgba(34, 68, 96, 0.88);
  border-radius: 14px;
  background: rgba(7, 17, 29, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.brain-stat-card {
  min-height: 116px;
  padding: 18px;
}

.brain-stat-card.primary {
  background: linear-gradient(135deg, rgba(0, 194, 255, 0.22), rgba(53, 208, 127, 0.14));
}

.brain-stat-card.risk strong {
  color: #ff7d85;
}

small {
  color: #8199ad;
  display: block;
  font-size: 13px;
}

strong {
  color: #f3f8ff;
  display: block;
  font-size: 27px;
  line-height: 1.18;
  margin-top: 14px;
  word-break: break-word;
}

.brain-stat-card strong {
  font-size: clamp(24px, 2.4vw, 40px);
  line-height: 1.15;
  word-break: keep-all;
}

.brain-stat-card small {
  white-space: nowrap;
}

.section-card {
  margin-bottom: 22px;
  padding: 24px;
}

.section-head {
  align-items: center;
  display: flex;
  gap: 14px;
  margin-bottom: 20px;
}

.section-head > span {
  background: linear-gradient(135deg, #00c2ff, #35d07f);
  border-radius: 10px;
  color: #041019;
  display: grid;
  font-weight: 900;
  height: 42px;
  place-items: center;
  width: 42px;
}

.section-head h2 {
  color: #f3f8ff;
  font-size: 24px;
}

.section-head p {
  color: #8199ad;
  font-size: 14px;
  margin-top: 6px;
}

.action-grid {
  display: grid;
  grid-template-columns: 0.7fr 0.7fr 1.3fr 1.3fr;
  gap: 14px;
}

.action-tile,
.reason-card {
  padding: 18px;
}

.action-tile strong {
  font-size: 36px;
}

.positive {
  color: #35d07f;
}

.danger,
.risk-copy p {
  color: #ff7d85;
}

.reason-card p {
  color: #d7e7f3;
  line-height: 1.8;
  margin-top: 12px;
}

.tier-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.tier-card {
  padding: 18px;
}

.tier-card h3 {
  color: #f3f8ff;
  font-size: 18px;
  margin-bottom: 14px;
}

.accent-green {
  border-color: rgba(53, 208, 127, 0.48);
}

.accent-blue {
  border-color: rgba(0, 194, 255, 0.48);
}

.accent-cyan {
  border-color: rgba(95, 220, 255, 0.48);
}

.stock-stack {
  display: grid;
  gap: 10px;
}

.stock-row {
  align-items: center;
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 10px;
  display: flex;
  justify-content: space-between;
  padding: 12px;
}

.stock-row strong {
  font-size: 16px;
  margin: 0;
}

.stock-row small {
  display: block;
  margin-top: 4px;
}

.stock-row span {
  color: #35d07f;
  font-weight: 900;
}

.empty {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 10px;
  color: #8199ad;
  padding: 14px;
}

.gauge-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.gauge-panel {
  padding: 18px;
}

.gauge-panel h3 {
  color: #d7e7f3;
  font-size: 18px;
}

.gauge-box {
  height: 260px;
}

.chat-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 18px;
  padding: 20px;
}

.avatar {
  background: linear-gradient(135deg, #00c2ff, #35d07f);
  border-radius: 14px;
  color: #041019;
  display: grid;
  font-weight: 900;
  height: 48px;
  place-items: center;
  width: 48px;
}

.chat-content {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  padding: 18px;
}

.chat-content h3 {
  color: #35d07f;
  font-size: 16px;
  margin: 0 0 8px;
}

.chat-content h3:not(:first-child) {
  margin-top: 18px;
}

.chat-content p,
.chat-content li {
  color: #d7e7f3;
  line-height: 1.8;
}

.chat-content ul {
  margin: 0;
  padding-left: 18px;
}

@media (max-width: 1180px) {
  .hero-section,
  .action-grid,
  .tier-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 820px) {
  .brain-page {
    padding: 18px;
  }

  .hero-section,
  .hero-grid,
  .action-grid,
  .tier-grid,
  .gauge-grid,
  .chat-card {
    grid-template-columns: 1fr;
  }
}
</style>

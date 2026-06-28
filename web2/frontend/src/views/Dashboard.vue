<template>
  <main class="brain-page">
    <section class="hero-section">
      <div class="hero-copy">
        <p class="eyebrow">Trading Brain Pro</p>
        <h1>AI 游资大脑</h1>
        <p class="one-line">{{ brain.decision?.summary || '暂无数据，请先运行今日策略。' }}</p>
        <div class="stars" aria-label="system confidence">★★★★★</div>
        <div class="data-meta">
          <span>数据更新时间：{{ dataUpdatedAt }}</span>
          <span>最新报告日期：{{ latestReportDate }}</span>
          <span v-if="dataRefreshMessage" class="refresh-ok">{{ dataRefreshMessage }}</span>
        </div>
        <button class="pipeline-button" type="button" :disabled="pipelineLoading" @click="runPipeline">
          {{ pipelineLoading ? '正在执行AI复盘...' : '一键AI复盘' }}
        </button>
      </div>

      <div class="hero-grid">
        <div class="brain-stat-card primary">
          <small>当前阶段</small>
          <strong>{{ brain.emotion?.stage || '暂无' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>情绪分</small>
          <strong>{{ brain.emotion?.score ?? 0 }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>今日动作</small>
          <strong>{{ brain.decision?.action || '观察' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>建议仓位</small>
          <strong>{{ brain.position?.suggested_position || '0%' }}</strong>
        </div>
        <div class="brain-stat-card risk">
          <small>风险等级</small>
          <strong>{{ brain.risk?.risk_label || '暂无' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>当前主线</small>
          <strong>{{ brain.theme?.main_theme || '暂无主线' }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>龙头</small>
          <strong>{{ firstName(tiers.T1) }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>趋势备选</small>
          <strong>{{ firstName(tiers.T2) }}</strong>
        </div>
        <div class="brain-stat-card">
          <small>趋势核心</small>
          <strong>{{ firstName(tiers.trend_core) }}</strong>
        </div>
      </div>
    </section>

    <section v-if="pipelineJob" class="section-card pipeline-result-card">
      <div class="section-head">
        <span>RUN</span>
        <div>
          <h2>{{ pipelineTitle }}</h2>
          <p>后台 Job 正在执行 main.py，页面每2秒自动查询一次状态。</p>
        </div>
      </div>
      <div class="progress-shell">
        <div class="progress-bar" :style="{ width: `${pipelineJob.progress || 0}%` }"></div>
      </div>
      <div class="progress-meta">
        <strong>{{ pipelineJob.progress || 0 }}%</strong>
        <span>当前步骤：{{ pipelineJob.current_step || '启动' }}</span>
        <span>已经运行：{{ pipelineJob.elapsed || 0 }} 秒</span>
      </div>
      <div class="pipeline-summary">
        <div>
          <small>执行状态</small>
          <strong :class="pipelineStatusClass">
            {{ pipelineStatusText }}
          </strong>
        </div>
        <div>
          <small>Job ID</small>
          <strong>{{ pipelineJob.job_id || '-' }}</strong>
        </div>
      </div>
      <p class="pipeline-message">{{ pipelineJob.message || '正在执行AI复盘……' }}</p>
      <p v-if="dataRefreshMessage" class="pipeline-message refresh-message">{{ dataRefreshMessage }}</p>
      <div class="pipeline-steps">
        <article v-for="step in pipelineJob.steps || []" :key="`${step.name}-${step.time}`" class="pipeline-step">
          <div class="step-head">
            <strong>{{ step.name }}</strong>
            <span :class="['ok', 'completed'].includes(step.status) ? 'positive' : step.status === 'failed' ? 'danger' : 'flat'">{{ step.status }}</span>
          </div>
          <small>耗时：{{ step.time }} 秒</small>
          <pre>{{ step.message }}</pre>
        </article>
      </div>
    </section>

    <section class="section-card market-hub-summary-card">
      <div class="section-head">
        <span>HUB</span>
        <div>
          <h2>Market Data Hub</h2>
          <p>统一行情快照：{{ marketHub.source || 'mock/manual' }}，缓存时间 {{ marketHub.cache_time || '-' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>市场状态</small>
          <strong>{{ marketHub.market_status || '暂无' }}</strong>
        </div>
        <div>
          <small>市场温度</small>
          <strong>{{ marketHub.board_strength?.temperature ?? 0 }}</strong>
        </div>
        <div>
          <small>成交额</small>
          <strong>{{ amountText(marketHub.turnover?.total_amount) }}</strong>
        </div>
        <div>
          <small>最热主题</small>
          <strong>{{ marketHub.hot_themes?.[0]?.name || '暂无' }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/market-hub">查看 Market Data Hub</RouterLink>
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

    <section class="section-card plan-summary-card">
      <div class="section-head">
        <span>PLAN</span>
        <div>
          <h2>明日交易计划摘要</h2>
          <p>{{ tradingPlan.summary || '暂无交易计划，请先运行今日策略。' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>总建议</small>
          <strong>{{ tradingPlanSummary }}</strong>
        </div>
        <div>
          <small>可操作标的</small>
          <strong>{{ actionableCount }}</strong>
        </div>
        <div>
          <small>观察标的</small>
          <strong>{{ observeCount }}</strong>
        </div>
        <div>
          <small>回避标的</small>
          <strong>{{ avoidCount }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/trading-plan">查看交易计划</RouterLink>
    </section>

    <section class="section-card script-summary-card">
      <div class="section-head">
        <span>SCRIPT</span>
        <div>
          <h2>明日剧本摘要</h2>
          <p>{{ tradeScript.tomorrow_summary || '暂无明日剧本，请先运行今日策略。' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>明日总策略</small>
          <strong>{{ tradeScriptSummary }}</strong>
        </div>
        <div>
          <small>剧本数量</small>
          <strong>{{ scriptCount }}</strong>
        </div>
        <div>
          <small>重点观察</small>
          <strong>{{ keyWatchCount }}</strong>
        </div>
        <div>
          <small>市场模式</small>
          <strong>{{ tradeScript.market_mode || '暂无' }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/trade-script">查看明日剧本</RouterLink>
    </section>

    <section class="section-card pre-market-summary-card">
      <div class="section-head">
        <span>PRE</span>
        <div>
          <h2>盘前AI摘要</h2>
          <p>{{ preMarket.summary || '暂无盘前AI摘要，请先运行今日策略。' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>今日模式</small>
          <strong>{{ preMarket.market_summary?.market_mode || '暂无' }}</strong>
        </div>
        <div>
          <small>观察数量</small>
          <strong>{{ preMarketWatchCount }}</strong>
        </div>
        <div>
          <small>重点关注</small>
          <strong>{{ preMarketFocusCount }}</strong>
        </div>
        <div>
          <small>建议仓位</small>
          <strong>{{ preMarket.market_summary?.position || '0%' }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/pre-market">查看盘前AI</RouterLink>
    </section>

    <section class="section-card auction-summary-card">
      <div class="section-head">
        <span>AUCTION</span>
        <div>
          <h2>集合竞价AI摘要</h2>
          <p>{{ auctionAi.summary || '暂无集合竞价判断，请先准备 mock 数据。' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>当前状态</small>
          <strong>{{ auctionAi.market_mode || '暂无' }}</strong>
        </div>
        <div>
          <small>取消数量</small>
          <strong>{{ auctionStats.cancel || 0 }}</strong>
        </div>
        <div>
          <small>重点观察</small>
          <strong>{{ auctionStats.strong || 0 }}</strong>
        </div>
        <div>
          <small>竞价时间</small>
          <strong>{{ auctionAi.auction_time || '09:25' }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/auction-ai">查看集合竞价AI</RouterLink>
    </section>

    <section class="section-card realtime-summary-card">
      <div class="section-head">
        <span>LIVE</span>
        <div>
          <h2>实时AI摘要</h2>
          <p>{{ realtimeAi.summary || '暂无实时AI事件。' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>最新事件数</small>
          <strong>{{ realtimeStats.events || 0 }}</strong>
        </div>
        <div>
          <small>观察信号</small>
          <strong>{{ realtimeStats.watch_signal || 0 }}</strong>
        </div>
        <div>
          <small>取消信号</small>
          <strong>{{ realtimeStats.cancel_signal || 0 }}</strong>
        </div>
        <div>
          <small>买入信号</small>
          <strong>{{ realtimeStats.buy_signal || 0 }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/realtime-ai">查看实时AI</RouterLink>
    </section>

    <section class="section-card ai-decision-summary-card">
      <div class="section-head">
        <span>DECIDE</span>
        <div>
          <h2>AI决策摘要</h2>
          <p>{{ aiDecision.global_decision?.summary || '暂无AI决策。' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>当前全局动作</small>
          <strong>{{ aiDecision.global_decision?.action || 'WAIT' }}</strong>
        </div>
        <div>
          <small>BUY数量</small>
          <strong>{{ aiDecisionStats.buy || 0 }}</strong>
        </div>
        <div>
          <small>WATCH数量</small>
          <strong>{{ aiDecisionStats.watch || 0 }}</strong>
        </div>
        <div>
          <small>CANCEL数量</small>
          <strong>{{ aiDecisionStats.cancel || 0 }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/ai-decision">查看AI决策</RouterLink>
    </section>

    <section class="section-card trader-agent-summary-card">
      <div class="section-head">
        <span>AGENT</span>
        <div>
          <h2>AI Trader状态</h2>
          <p>{{ traderAgent.current_task || '等待中' }}，{{ traderAgent.next_action || '继续观察' }}</p>
        </div>
      </div>
      <div class="plan-summary-grid">
        <div>
          <small>状态</small>
          <strong>{{ traderAgent.agent?.status || 'RUNNING' }}</strong>
        </div>
        <div>
          <small>模式</small>
          <strong>{{ traderAgent.agent?.mode || 'OBSERVE' }}</strong>
        </div>
        <div>
          <small>当前决策</small>
          <strong>{{ traderAgent.decision || 'WAIT' }}</strong>
        </div>
        <div>
          <small>订单队列</small>
          <strong>{{ traderAgent.order_queue?.length || 0 }}</strong>
        </div>
      </div>
      <RouterLink class="plan-link" to="/trader-agent">进入AI Trader</RouterLink>
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
          <p>当前阶段、情绪分、下阶段推演和风险提示。</p>
        </div>
      </div>
      <div class="cycle-strip">
        <div>
          <small>当前阶段</small>
          <strong>{{ brain.emotion?.stage || '暂无' }}</strong>
        </div>
        <div>
          <small>情绪分</small>
          <strong>{{ brain.emotion?.score ?? 0 }}</strong>
        </div>
        <div>
          <small>下阶段推演</small>
          <strong>{{ brain.emotion?.next_stage_guess || '暂无数据' }}</strong>
        </div>
        <div>
          <small>风险提示</small>
          <p>{{ riskText }}</p>
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
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../services/api'

const brain = ref({})
const marketHub = ref({})
const tradingPlan = ref({})
const tradeScript = ref({})
const preMarket = ref({})
const auctionAi = ref({})
const realtimeAi = ref({})
const aiDecision = ref({})
const traderAgent = ref({})
const pipelineLoading = ref(false)
const pipelineJob = ref(null)
const dataRefreshMessage = ref('')
let pollingTimer = null
const emotionGauge = ref(null)
const riskGauge = ref(null)
const positionGauge = ref(null)

const tiers = computed(() => brain.value.leader?.tier_summary || {})
const dataUpdatedAt = computed(() => brain.value.data_updated_at || '-')
const latestReportDate = computed(() => brain.value.latest_report_date || '-')
const planItems = computed(() => Array.isArray(tradingPlan.value.plans) ? tradingPlan.value.plans : [])
const tradingPlanSummary = computed(() => tradingPlan.value.summary || '暂无')
const actionableCount = computed(() => planItems.value.filter((item) => !['观察', '回避'].includes(item.action)).length)
const observeCount = computed(() => planItems.value.filter((item) => item.action === '观察').length)
const avoidCount = computed(() => planItems.value.filter((item) => item.action === '回避').length)
const scriptItems = computed(() => Array.isArray(tradeScript.value.scripts) ? tradeScript.value.scripts : [])
const tradeScriptSummary = computed(() => tradeScript.value.tomorrow_summary || '暂无')
const scriptCount = computed(() => scriptItems.value.length)
const keyWatchCount = computed(() => scriptItems.value.filter((item) => String(item.watch_level || '').includes('重点')).length)
const preMarketWatchList = computed(() => Array.isArray(preMarket.value.watch_list) ? preMarket.value.watch_list : [])
const preMarketWatchCount = computed(() => preMarketWatchList.value.length)
const preMarketFocusCount = computed(() => Array.isArray(preMarket.value.today_focus) ? preMarket.value.today_focus.length : 0)
const auctionStats = computed(() => auctionAi.value.stats || {})
const realtimeStats = computed(() => realtimeAi.value.stats || {})
const aiDecisionStats = computed(() => aiDecision.value.stats || {})
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
const pipelineTitle = computed(() => {
  if (!pipelineJob.value) return 'AI复盘任务'
  if (pipelineJob.value.status === 'completed') return 'AI复盘完成'
  if (pipelineJob.value.status === 'failed') return 'AI复盘失败'
  if (pipelineJob.value.status === 'timeout') return '仍在后台运行……'
  return 'AI复盘进行中'
})
const pipelineStatusText = computed(() => {
  const status = pipelineJob.value?.status
  if (status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'timeout') return '后台运行'
  if (status === 'running') return '运行中'
  return '排队中'
})
const pipelineStatusClass = computed(() => {
  const status = pipelineJob.value?.status
  if (status === 'completed') return 'positive'
  if (status === 'failed') return 'danger'
  return 'flat'
})

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
                  h('div', [
                    h('strong', item.name || '-'),
                    h('small', item.code || '-'),
                    h('em', `${item.life_stage || '观察'} / ${item.lifecycle_action || item.action || '观察'}`)
                  ]),
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

function amountText(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return '-'
  if (number >= 100000000) return `${(number / 100000000).toFixed(0)}亿`
  return `${(number / 10000).toFixed(0)}万`
}

function renderGauge(el, value, name, color) {
  if (!el) return
  const existing = echarts.getInstanceByDom(el)
  if (existing) existing.dispose()
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

async function loadMarketBrain() {
  const response = await api.marketBrain()
  brain.value = response.data || {}
  await nextTick()
  renderAllGauges()
}

async function loadMarketHub() {
  const response = await api.marketHub()
  marketHub.value = response.data || {}
}

async function loadTradingPlan() {
  const response = await api.tradingPlan()
  tradingPlan.value = response.data || {}
}

async function loadTradeScript() {
  const response = await api.tradeScript()
  tradeScript.value = response.data || {}
}

async function loadPreMarket() {
  const response = await api.preMarket()
  preMarket.value = response.data || {}
}

async function loadAuctionAi() {
  const response = await api.auctionAi()
  auctionAi.value = response.data || {}
}

async function loadRealtimeAi() {
  const response = await api.realtimeAi()
  realtimeAi.value = response.data || {}
}

async function loadAiDecision() {
  const response = await api.aiDecision()
  aiDecision.value = response.data || {}
}

async function loadTraderAgent() {
  const response = await api.traderAgent()
  traderAgent.value = response.data || {}
}

async function refreshAfterJob() {
  await Promise.allSettled([
    loadMarketBrain(),
    loadMarketHub(),
    api.dashboard(),
    api.mainline(),
    api.dailyAiReport(),
    api.paperData(),
    loadTradingPlan(),
    loadTradeScript(),
    loadPreMarket(),
    loadAuctionAi(),
    loadRealtimeAi(),
    loadAiDecision(),
    loadTraderAgent()
  ])
  dataRefreshMessage.value = '数据已刷新'
}

function normalizeCompletedJob(job = {}) {
  const steps = (job.steps || []).map((step) => ({
    ...step,
    status: ['queued', 'running', 'timeout'].includes(step.status) ? 'completed' : step.status
  }))
  if (!steps.some((step) => step.status === 'completed' && String(step.name).includes('完成'))) {
    steps.push({
      name: '完成',
      status: 'completed',
      time: job.elapsed || 0,
      message: 'AI复盘完成，页面数据已刷新。'
    })
  }
  return {
    ...job,
    status: 'completed',
    progress: 100,
    current_step: '完成',
    message: `${job.message || 'AI复盘完成。'}\n数据已刷新`,
    steps
  }
}

async function runPipeline() {
  if (pipelineLoading.value) return
  pipelineLoading.value = true
  dataRefreshMessage.value = ''
  pipelineJob.value = {
    status: 'queued',
    progress: 0,
    current_step: '启动',
    elapsed: 0,
    message: '正在创建后台任务……',
    steps: []
  }
  try {
    const response = await api.runPipeline()
    const jobId = response.data?.job_id
    pipelineJob.value = {
      ...pipelineJob.value,
      job_id: jobId,
      status: response.data?.status || 'queued',
      message: '后台任务已创建，开始轮询执行状态。'
    }
    startPolling(jobId)
  } catch (error) {
    pipelineJob.value = {
      status: 'failed',
      progress: 0,
      current_step: '请求失败',
      elapsed: 0,
      message: error.message || '请求失败',
      steps: [
        {
          name: 'run-pipeline',
          status: 'failed',
          time: 0,
          message: error.message || '请求失败'
        }
      ]
    }
    pipelineLoading.value = false
  }
}

function startPolling(jobId) {
  stopPolling()
  pollingTimer = window.setInterval(async () => {
    try {
      const response = await api.jobStatus(jobId)
      pipelineJob.value = response.data || pipelineJob.value
      const status = pipelineJob.value?.status
      if (status === 'completed') {
        stopPolling()
        pipelineJob.value = normalizeCompletedJob(pipelineJob.value)
        await refreshAfterJob()
        pipelineJob.value = normalizeCompletedJob(pipelineJob.value)
        pipelineLoading.value = false
      } else if (status === 'failed') {
        stopPolling()
        pipelineLoading.value = false
      }
    } catch (error) {
      pipelineJob.value = {
        ...pipelineJob.value,
        status: 'failed',
        message: error.message || '查询任务状态失败'
      }
      stopPolling()
      pipelineLoading.value = false
    }
  }, 2000)
}

function stopPolling() {
  if (pollingTimer) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

onMounted(async () => {
  await Promise.allSettled([loadMarketBrain(), loadMarketHub(), loadTradingPlan(), loadTradeScript(), loadPreMarket(), loadAuctionAi(), loadRealtimeAi(), loadAiDecision(), loadTraderAgent()])
})

onBeforeUnmount(() => {
  stopPolling()
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

.data-meta {
  display: grid;
  gap: 8px;
  margin-top: 18px;
}

.data-meta span {
  color: #9eb4c8;
  font-size: 13px;
}

.data-meta .refresh-ok,
.refresh-message {
  color: #35d07f;
}

.pipeline-button {
  border: 0;
  border-radius: 14px;
  background: linear-gradient(135deg, #00c2ff, #35d07f);
  box-shadow: 0 18px 34px rgba(0, 194, 255, 0.18);
  color: #041019;
  cursor: pointer;
  font-size: 18px;
  font-weight: 900;
  margin-top: 28px;
  min-width: 180px;
  padding: 15px 22px;
}

.pipeline-button:disabled {
  cursor: wait;
  filter: grayscale(0.25);
  opacity: 0.72;
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

.pipeline-result-card {
  border-color: rgba(0, 194, 255, 0.45);
}

.market-hub-summary-card {
  border-color: rgba(0, 194, 255, 0.36);
}

.pipeline-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.progress-shell {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 999px;
  height: 18px;
  margin-bottom: 14px;
  overflow: hidden;
}

.progress-bar {
  background: linear-gradient(90deg, #00c2ff, #35d07f);
  height: 100%;
  transition: width 0.35s ease;
}

.progress-meta {
  align-items: center;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 14px;
  margin-bottom: 14px;
}

.progress-meta strong {
  color: #35d07f;
  font-size: 26px;
  margin: 0;
}

.progress-meta span {
  color: #c7d8e8;
}

.pipeline-summary > div,
.pipeline-step {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  padding: 16px;
}

.pipeline-summary strong {
  font-size: 24px;
}

.pipeline-message {
  background: #08131f;
  border-left: 3px solid #00c2ff;
  border-radius: 8px;
  color: #d7e7f3;
  line-height: 1.8;
  margin-bottom: 14px;
  padding: 14px;
}

.pipeline-steps {
  display: grid;
  gap: 14px;
}

.step-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.step-head strong {
  font-size: 18px;
  margin: 0;
}

.pipeline-step pre {
  background: rgba(3, 10, 18, 0.82);
  border: 1px solid #14283b;
  border-radius: 10px;
  color: #c7d8e8;
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
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

.plan-summary-card {
  border-color: rgba(53, 208, 127, 0.36);
}

.script-summary-card {
  border-color: rgba(0, 194, 255, 0.36);
}

.pre-market-summary-card {
  border-color: rgba(121, 149, 255, 0.36);
}

.auction-summary-card {
  border-color: rgba(255, 183, 77, 0.36);
}

.realtime-summary-card {
  border-color: rgba(53, 208, 127, 0.36);
}

.ai-decision-summary-card {
  border-color: rgba(121, 149, 255, 0.42);
}

.trader-agent-summary-card {
  border-color: rgba(0, 194, 255, 0.5);
}

.plan-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.plan-summary-grid div {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  padding: 16px;
}

.plan-summary-grid strong {
  font-size: 30px;
}

.plan-link {
  align-items: center;
  background: linear-gradient(135deg, #00c2ff, #35d07f);
  border-radius: 12px;
  color: #041019;
  display: inline-flex;
  font-weight: 900;
  min-height: 42px;
  padding: 0 16px;
  text-decoration: none;
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

.stock-row em {
  color: #00c2ff;
  display: block;
  font-style: normal;
  font-size: 12px;
  margin-top: 6px;
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

.cycle-strip {
  display: grid;
  grid-template-columns: 0.8fr 0.7fr 1fr 1.5fr;
  gap: 14px;
  margin-bottom: 14px;
}

.cycle-strip > div {
  background: #08131f;
  border: 1px solid #14283b;
  border-radius: 14px;
  padding: 16px;
}

.cycle-strip strong {
  color: #35d07f;
  font-size: 24px;
}

.cycle-strip p {
  color: #ffb4b4;
  line-height: 1.8;
  margin-top: 10px;
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
  .plan-summary-grid,
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
  .plan-summary-grid,
  .tier-grid,
  .cycle-strip,
  .gauge-grid,
  .progress-meta,
  .chat-card {
    grid-template-columns: 1fr;
  }
}
</style>

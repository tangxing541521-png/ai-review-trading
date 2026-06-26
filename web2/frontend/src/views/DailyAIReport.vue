<template>
  <section class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Daily AI Report</p>
        <h1>{{ report.title || 'AI复盘日报' }}</h1>
      </div>
      <span class="status-badge">模拟验证</span>
    </header>

    <section class="summary-card">
      <small>今日总结</small>
      <strong>{{ report.summary || emptyText }}</strong>
    </section>

    <section class="report-grid">
      <article class="panel">
        <div class="section-title">
          <span>01</span>
          <h2>市场判断</h2>
        </div>
        <p>{{ report.market_view || emptyText }}</p>
      </article>

      <article class="panel">
        <div class="section-title">
          <span>02</span>
          <h2>主线判断</h2>
        </div>
        <p>{{ report.mainline_view || emptyText }}</p>
      </article>

      <article class="panel">
        <div class="section-title">
          <span>03</span>
          <h2>龙头梯队</h2>
        </div>
        <pre>{{ report.leader_view || emptyText }}</pre>
      </article>

      <article class="panel">
        <div class="section-title">
          <span>04</span>
          <h2>风险提示</h2>
        </div>
        <p class="risk-text">{{ report.risk_view || emptyText }}</p>
      </article>

      <article class="panel wide">
        <div class="section-title">
          <span>05</span>
          <h2>明日计划</h2>
        </div>
        <p>{{ report.tomorrow_plan || emptyText }}</p>
      </article>
    </section>

    <section class="panel full-report">
      <div class="section-title">
        <span>MD</span>
        <h2>完整日报 Markdown</h2>
      </div>
      <pre>{{ report.full_report || emptyText }}</pre>
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const emptyText = '暂无数据，请先运行今日策略。'
const report = ref({})

onMounted(async () => {
  const response = await api.dailyAiReport()
  report.value = response.data || {}
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
p,
pre {
  margin: 0;
}

h1 {
  font-size: 32px;
}

.status-badge {
  border: 1px solid #25415b;
  border-radius: 999px;
  color: #00c2ff;
  padding: 8px 14px;
  background: rgba(0, 194, 255, 0.08);
}

.summary-card,
.panel {
  border: 1px solid #183047;
  border-radius: 8px;
  background: rgba(9, 18, 29, 0.94);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}

.summary-card {
  padding: 22px;
  margin-bottom: 16px;
}

.summary-card strong {
  display: block;
  color: #35d07f;
  font-size: 24px;
  line-height: 1.45;
  margin-top: 10px;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.panel {
  padding: 20px;
}

.wide {
  grid-column: 1 / -1;
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

p,
pre {
  color: #d7e7f3;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.risk-text {
  color: #ffb4b4;
}

.full-report pre {
  border: 1px solid #14283b;
  border-radius: 8px;
  background: #08131f;
  color: #d7e7f3;
  max-height: 560px;
  overflow: auto;
  padding: 16px;
}

@media (max-width: 980px) {
  .report-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}
</style>

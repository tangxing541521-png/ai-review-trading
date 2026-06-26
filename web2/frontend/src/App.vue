<template>
  <div class="app-shell">
    <aside class="sidebar" v-if="route.name !== 'login'">
      <div class="brand">
        <span class="brand-mark">AI</span>
        <div>
          <strong>Review Trading</strong>
          <small>Web 2.0 Skeleton</small>
        </div>
      </div>
      <nav>
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/market">今日市场</RouterLink>
        <RouterLink to="/leaders">龙头排行榜</RouterLink>
        <RouterLink to="/frozen-orders">冻结订单</RouterLink>
        <RouterLink to="/paper">Paper Trading</RouterLink>
        <RouterLink to="/strategy-judge">Strategy Judge</RouterLink>
        <RouterLink to="/validation">Validation</RouterLink>
        <RouterLink to="/reports">报告</RouterLink>
        <RouterLink to="/membership">会员中心</RouterLink>
        <RouterLink to="/disclaimer">免责声明</RouterLink>
      </nav>
    </aside>

    <main class="main-panel">
      <TopBar v-if="route.name !== 'login'" />
      <RouterView />
      <footer class="disclaimer">
        本系统仅用于学习研究和模拟验证，不构成任何投资建议，不承诺收益，交易风险自担。
      </footer>
    </main>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import TopBar from './components/TopBar.vue'

const route = useRoute()
</script>

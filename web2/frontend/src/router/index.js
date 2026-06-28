import { createRouter, createWebHistory } from 'vue-router'
import AIDecision from '../views/AIDecision.vue'
import AuctionAI from '../views/AuctionAI.vue'
import Dashboard from '../views/Dashboard.vue'
import DailyAIReport from '../views/DailyAIReport.vue'
import Login from '../views/Login.vue'
import Market from '../views/Market.vue'
import MarketHub from '../views/MarketHub.vue'
import PaperTrading from '../views/PaperTrading.vue'
import PreMarket from '../views/PreMarket.vue'
import RealtimeAI from '../views/RealtimeAI.vue'
import Reports from '../views/Reports.vue'
import Disclaimer from '../views/Disclaimer.vue'
import FrozenOrders from '../views/FrozenOrders.vue'
import Leaders from '../views/Leaders.vue'
import Mainline from '../views/Mainline.vue'
import Membership from '../views/Membership.vue'
import StrategyJudge from '../views/StrategyJudge.vue'
import TradeScript from '../views/TradeScript.vue'
import TraderAgent from '../views/TraderAgent.vue'
import TradingPlan from '../views/TradingPlan.vue'
import Validation from '../views/Validation.vue'

const routes = [
  { path: '/login', name: 'login', component: Login },
  { path: '/', name: 'dashboard', component: Dashboard },
  { path: '/daily-ai-report', name: 'dailyAiReport', component: DailyAIReport },
  { path: '/market', name: 'market', component: Market },
  { path: '/market-hub', name: 'marketHub', component: MarketHub },
  { path: '/leaders', name: 'leaders', component: Leaders },
  { path: '/mainline', name: 'mainline', component: Mainline },
  { path: '/trading-plan', name: 'tradingPlan', component: TradingPlan },
  { path: '/trade-script', name: 'tradeScript', component: TradeScript },
  { path: '/pre-market', name: 'preMarket', component: PreMarket },
  { path: '/auction-ai', name: 'auctionAi', component: AuctionAI },
  { path: '/realtime-ai', name: 'realtimeAi', component: RealtimeAI },
  { path: '/ai-decision', name: 'aiDecision', component: AIDecision },
  { path: '/trader-agent', name: 'traderAgent', component: TraderAgent },
  { path: '/frozen-orders', name: 'frozenOrders', component: FrozenOrders },
  { path: '/paper', name: 'paper', component: PaperTrading },
  { path: '/strategy-judge', name: 'strategyJudge', component: StrategyJudge },
  { path: '/validation', name: 'validation', component: Validation },
  { path: '/reports', name: 'reports', component: Reports },
  { path: '/membership', name: 'membership', component: Membership },
  { path: '/disclaimer', name: 'disclaimer', component: Disclaimer }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!token && to.name !== 'login') {
    return '/login'
  }
})

export default router

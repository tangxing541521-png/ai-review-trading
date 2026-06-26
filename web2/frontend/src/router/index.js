import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Login from '../views/Login.vue'
import Market from '../views/Market.vue'
import PaperTrading from '../views/PaperTrading.vue'
import Reports from '../views/Reports.vue'
import Disclaimer from '../views/Disclaimer.vue'
import FrozenOrders from '../views/FrozenOrders.vue'
import Leaders from '../views/Leaders.vue'
import Mainline from '../views/Mainline.vue'
import Membership from '../views/Membership.vue'
import StrategyJudge from '../views/StrategyJudge.vue'
import Validation from '../views/Validation.vue'

const routes = [
  { path: '/login', name: 'login', component: Login },
  { path: '/', name: 'dashboard', component: Dashboard },
  { path: '/market', name: 'market', component: Market },
  { path: '/leaders', name: 'leaders', component: Leaders },
  { path: '/mainline', name: 'mainline', component: Mainline },
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

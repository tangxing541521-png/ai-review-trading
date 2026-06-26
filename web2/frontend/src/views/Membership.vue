<template>
  <div class="page">
    <h1>会员中心</h1>
    <div class="hero-card neutral">
      <span>当前用户等级</span>
      <strong>{{ data.membership_level || 'free' }}</strong>
      <small>到期日：{{ data.expire_date || '暂无' }}</small>
    </div>
    <div class="plan-grid">
      <section v-for="plan in data.plans" :key="plan.name" class="panel plan-card">
        <h2>{{ plan.name }}</h2>
        <ul>
          <li v-for="feature in plan.features" :key="feature">{{ feature }}</li>
        </ul>
      </section>
    </div>
    <section class="panel">
      <h2>升级提示</h2>
      <p>{{ data.upgrade_note }}</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const data = ref({ plans: [] })
onMounted(async () => {
  const res = await api.membership()
  data.value = res.data || { plans: [] }
})
</script>

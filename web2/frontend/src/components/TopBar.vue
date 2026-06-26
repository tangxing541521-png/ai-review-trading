<template>
  <header class="topbar">
    <div>
      <span class="status-dot"></span>
      <span>本地模拟环境</span>
    </div>
    <div class="topbar-right">
      <span class="pill">{{ user.username || 'unknown' }}</span>
      <span class="pill accent">{{ user.membership_level }}</span>
      <button class="ghost" @click="handleLogout">退出</button>
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { currentUser, logout } from '../services/api'

const router = useRouter()
const user = currentUser()

function handleLogout() {
  logout()
  router.push('/login')
}
</script>

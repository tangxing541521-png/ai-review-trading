<template>
  <div class="login-page">
    <section class="login-card">
      <div class="brand large">
        <span class="brand-mark">AI</span>
        <div>
          <strong>AI Review Trading</strong>
          <small>Web 2.0 本地产品骨架</small>
        </div>
      </div>
      <h1>登录</h1>
      <label>用户名</label>
      <input v-model="username" />
      <label>密码</label>
      <input v-model="password" type="password" />
      <button @click="submit">进入系统</button>
      <p class="error" v-if="error">{{ error }}</p>
      <p class="hint">测试账号：free/free123，member/member123，admin/admin123</p>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../services/api'

const router = useRouter()
const username = ref('free')
const password = ref('free123')
const error = ref('')

async function submit() {
  error.value = ''
  try {
    await login(username.value, password.value)
    router.push('/')
  } catch (err) {
    error.value = '登录失败，请检查账号密码。'
  }
}
</script>

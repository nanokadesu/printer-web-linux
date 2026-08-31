<template>
  <main class="login"><form @submit.prevent="submit"><h1>GreenPrint</h1><p>Linux CUPS 打印服务</p>
    <label>用户名<input v-model.trim="username" autocomplete="username" required /></label>
    <label>密码<input v-model="password" type="password" autocomplete="current-password" required /></label>
    <button :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
    <div v-if="error" class="error">{{ error }}</div>
  </form></main>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setLoginCookie } from '../utils/auth'
import api from '../services/api'
const router = useRouter(); const username = ref(''); const password = ref(''); const error = ref(''); const loading = ref(false)
const submit = async () => { error.value = ''; loading.value = true; try { const result = await api.post('/login', { username: username.value, password: password.value }); setLoginCookie(result.username, result.token); router.push('/print') } catch (err) { error.value = err?.error || '登录失败' } finally { loading.value = false } }
</script>
<style scoped>
.login { min-height: 100vh; display: grid; place-items: center; background: #edf6f0; padding: 20px; }
form { width: min(100%, 380px); display: grid; gap: 16px; padding: 32px; background: white; border: 1px solid #d6e8dc; border-radius: 8px; box-shadow: 0 8px 24px #21483214; }
h1 { margin: 0; color: #1f7049; } p { margin: -8px 0 8px; color: #60756a; } label { display: grid; gap: 6px; color: #294334; font-size: 14px; } input { padding: 10px 12px; border: 1px solid #c8dbcf; border-radius: 6px; font-size: 16px; } button { padding: 11px; border: 0; border-radius: 6px; background: #2f8f62; color: white; font-weight: 600; cursor: pointer; } button:disabled { opacity: .6; } .error { color: #b42318; background: #fff1f0; padding: 10px; border-radius: 6px; }
</style>

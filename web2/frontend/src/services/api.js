const API_BASE = 'http://127.0.0.1:8000/api'

export function currentUser() {
  return {
    username: localStorage.getItem('username') || '',
    membership_level: localStorage.getItem('membership_level') || 'free'
  }
}

export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  localStorage.removeItem('membership_level')
}

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `API 请求失败：${response.status}`)
  }
  return response.json()
}

export async function login(username, password) {
  const data = await request('/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
  localStorage.setItem('token', data.access_token)
  localStorage.setItem('username', data.username)
  localStorage.setItem('membership_level', data.membership_level)
  return data
}

export const api = {
  health: () => request('/health'),
  dashboard: () => request('/dashboard'),
  finalReport: () => request('/reports/final'),
  paperAccount: () => request('/paper/account'),
  paperData: () => request('/paper/data'),
  validation: () => request('/validation'),
  leaders: () => request('/leaders'),
  frozenOrders: () => request('/frozen-orders'),
  strategyJudge: () => request('/strategy-judge'),
  membership: () => request('/membership'),
  disclaimer: () => request('/disclaimer')
}

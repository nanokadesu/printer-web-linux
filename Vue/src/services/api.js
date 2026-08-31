import axios from 'axios'
import { getToken, removeToken } from '../utils/auth'

const backendPort = import.meta.env.VITE_API_PORT || '5181'
const prefix = (import.meta.env.VITE_API_PREFIX || '/api').replace(/\/$/, '')
const timeout = Number(import.meta.env.VITE_IP_PROBE_TIMEOUT_MS || 1500)
const configuredIps = (import.meta.env.VITE_IP_LIST || window.location.hostname)
  .split(',').map((value) => value.trim()).filter(Boolean)
const ips = [window.location.hostname, ...configuredIps]
  .filter((ip, index, values) => values.indexOf(ip) === index)

let activeIp = null

const backendOriginFor = (ip) => `${window.location.protocol}//${ip}:${backendPort}`

async function probe(ip) {
  // Require two successful backend probes before selecting a channel. This
  // filters transient routes and verifies that the print API is reachable,
  // rather than only checking whether the UI port responds.
  const healthUrl = ip === window.location.hostname
    ? `${prefix}/health`
    : `${backendOriginFor(ip)}${prefix}/health`
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await axios.get(healthUrl, { timeout })
  }
  return ip
}

const baseUrlFor = (ip) => ip === window.location.hostname
  ? prefix
  : `${backendOriginFor(ip)}${prefix}`

async function resolveIp(force = false, excluded = new Set()) {
  if (activeIp && !force && !excluded.has(activeIp)) return activeIp
  for (const ip of ips) {
    if (excluded.has(ip)) continue
    try {
      activeIp = await probe(ip)
      return activeIp
    } catch (_) {
      // Try the next configured address in priority order.
    }
  }
  activeIp = null
  const error = new Error('所有打印服务地址均不可访问')
  error.status = 400
  error.error = error.message
  throw error
}

async function request(config, excluded = new Set()) {
  let ip
  try {
    ip = await resolveIp(false, excluded)
  } catch (error) {
    throw error
  }
  const headers = { ...(config.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  try {
    const response = await axios({
      ...config,
      baseURL: baseUrlFor(ip),
      headers,
      timeout: 30000,
    })
    return response.data
  } catch (error) {
    if (error.response?.status === 401) {
      removeToken()
      window.location.href = '/login'
      throw error.response.data
    }
    const shouldFailOver = !error.response || [502, 503, 504].includes(error.response.status)
    if (shouldFailOver && excluded.size < ips.length - 1) {
      excluded.add(ip)
      activeIp = null
      return request(config, excluded)
    }
    if (shouldFailOver) {
      const networkError = new Error('所有打印服务地址均不可访问')
      networkError.status = 400
      networkError.error = networkError.message
      throw networkError
    }
    throw error.response.data || error
  }
}

export const resetApiChannel = () => { activeIp = null }
export const getActiveApiIp = () => activeIp

export default {
  get: (url, config = {}) => request({ ...config, method: 'get', url }),
  post: (url, data, config = {}) => request({ ...config, method: 'post', url, data }),
  delete: (url, config = {}) => request({ ...config, method: 'delete', url }),
  resolveIp,
}

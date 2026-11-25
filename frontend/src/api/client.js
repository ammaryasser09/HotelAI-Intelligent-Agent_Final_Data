import { mockRequest } from './mock.js'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

const TOKEN_KEY = 'np_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token) {
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ }
}

export class ApiError extends Error {
  constructor(status, detail) {
    const reason = typeof detail === 'object' && detail ? detail.reason || JSON.stringify(detail) : String(detail || 'ERROR')
    super(reason)
    this.status = status
    this.detail = detail
  }
}

export async function api(path, { method = 'GET', body, query } = {}) {
  const qs = query ? '?' + new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')) : ''
  if (USE_MOCK) return mockRequest(method, path + qs, body, getToken())
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(API_URL + path + qs, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data)
  return data
}

export function staffSocketUrl() {
  return API_URL.replace(/^http/, 'ws') + '/ws/staff?token=' + encodeURIComponent(getToken() || '')
}

export const imageUrl = (p) => (p ? (USE_MOCK ? p : API_URL + p) : '')

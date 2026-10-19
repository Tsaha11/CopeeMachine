export class AuthError extends Error {}

// Where the backend lives. Empty = same origin (dev proxy, or a host that proxies /api).
export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export async function api(path, opts) {
  const r = await fetch(API_BASE + path, { credentials: 'include', ...opts })
  if (r.status === 401 && !path.startsWith('/api/auth')) throw new AuthError('auth')
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.error || r.statusText)
  return body
}

const json = (method, data) => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
})
export const post = (path, data) => api(path, json('POST', data))
export const patch = (path, data) => api(path, json('PATCH', data))
export const del = (path) => api(path, { method: 'DELETE' })

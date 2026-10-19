export class AuthError extends Error {}

export async function api(path, opts) {
  const r = await fetch(path, opts)
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

const BASE = import.meta.env.VITE_API_URL || ''

export function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setSession(token: string, user: unknown) {
  localStorage.setItem('token', token)
  localStorage.setItem('user', JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export function currentUser(): any | null {
  const raw = localStorage.getItem('user')
  return raw ? JSON.parse(raw) : null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request(method: string, path: string, body?: unknown) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (res.status === 401 && !path.includes('/auth/login')) {
    clearSession()
    window.location.href = '/login'
    throw new ApiError(401, 'Session expired')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {}
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

export const api = {
  get: (path: string) => request('GET', path),
  post: (path: string, body?: unknown) => request('POST', path, body),
  put: (path: string, body?: unknown) => request('PUT', path, body),
  patch: (path: string, body?: unknown) => request('PATCH', path, body),
  delete: (path: string) => request('DELETE', path),
}

export const inr = (n: number) =>
  '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 2 })

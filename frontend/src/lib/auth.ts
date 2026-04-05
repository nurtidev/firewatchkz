export type AuthRole = 'viewer' | 'dispatcher' | 'analyst' | 'admin'

export interface AuthUser {
  email: string
  role: AuthRole
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

export const AUTH_TOKEN_KEY = 'firewatch.auth.token'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
}

export function clearStoredToken(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
}

export async function loginRequest(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const payload = await safeJson(response)
    throw new Error(payload?.detail ?? 'Не удалось войти')
  }

  return response.json()
}

export async function meRequest(token: string): Promise<AuthUser> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    const payload = await safeJson(response)
    throw new Error(payload?.detail ?? 'Сессия недействительна')
  }

  const payload = await response.json()
  return payload.user as AuthUser
}

async function safeJson(response: Response): Promise<{ detail?: string } | null> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

'use client'

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import {
  clearStoredToken,
  getStoredToken,
  loginRequest,
  meRequest,
  setStoredToken,
  type AuthRole,
  type AuthUser,
} from '@/lib/auth'

type AuthStatus = 'loading' | 'ready'

interface AuthContextValue {
  user: AuthUser | null
  token: string | null
  status: AuthStatus
  isAuthenticated: boolean
  isAdmin: boolean
  role: AuthRole | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
  hasRole: (roles: AuthRole[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
      const storedToken = getStoredToken()
      if (!storedToken) {
        if (!cancelled) setStatus('ready')
        return
      }

      try {
        const storedUser = await meRequest(storedToken)
        if (cancelled) return
        setToken(storedToken)
        setUser(storedUser)
      } catch {
        clearStoredToken()
        if (!cancelled) {
          setToken(null)
          setUser(null)
        }
      } finally {
        if (!cancelled) setStatus('ready')
      }
    }

    restoreSession()

    return () => {
      cancelled = true
    }
  }, [])

  async function login(email: string, password: string) {
    const response = await loginRequest(email, password)
    setStoredToken(response.token)
    setToken(response.token)
    setUser(response.user)
    setStatus('ready')
  }

  function logout() {
    clearStoredToken()
    setToken(null)
    setUser(null)
    setStatus('ready')
  }

  async function refresh() {
    const storedToken = getStoredToken()
    if (!storedToken) {
      logout()
      return
    }

    try {
      const storedUser = await meRequest(storedToken)
      setToken(storedToken)
      setUser(storedUser)
    } catch {
      logout()
    }
  }

  const value: AuthContextValue = {
    user,
    token,
    status,
    isAuthenticated: Boolean(user && token),
    isAdmin: user?.role === 'admin',
    role: user?.role ?? null,
    login,
    logout,
    refresh,
    hasRole: (roles: AuthRole[]) => Boolean(user && roles.includes(user.role)),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

export function RequireAuth({
  children,
  roles,
  fallback,
}: {
  children: ReactNode
  roles?: AuthRole[]
  fallback?: ReactNode
}) {
  const router = useRouter()
  const auth = useAuth()
  const allowedByRole = !roles || (auth.role !== null && roles.includes(auth.role))
  const shouldRedirect = auth.status === 'ready' && (!auth.isAuthenticated || !allowedByRole)

  useEffect(() => {
    if (auth.status !== 'ready') return

    if (!auth.isAuthenticated) {
      router.replace('/login')
      return
    }

    if (!allowedByRole) {
      router.replace('/dashboard')
    }
  }, [allowedByRole, auth.isAuthenticated, auth.status, router])

  if (auth.status !== 'ready') {
    return fallback ?? (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-white/70">
        Проверяем доступ...
      </div>
    )
  }

  if (shouldRedirect) {
    return fallback ?? null
  }

  return <>{children}</>
}

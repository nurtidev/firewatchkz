'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, ArrowRight, Flame, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const DEMO_USERS = [
  { email: 'admin@firewatch.kz', password: 'admin123', role: 'admin' },
  { email: 'analyst@firewatch.kz', password: 'analyst123', role: 'analyst' },
]

export default function LoginPage() {
  const router = useRouter()
  const { isAuthenticated, login, status } = useAuth()
  const [email, setEmail] = useState(DEMO_USERS[0].email)
  const [password, setPassword] = useState(DEMO_USERS[0].password)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (status === 'ready' && isAuthenticated) {
      router.replace('/dashboard')
    }
  }, [isAuthenticated, router, status])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await login(email.trim(), password)
      router.replace('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen relative overflow-hidden bg-[#07111f] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(249,115,22,0.25),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(34,197,94,0.12),_transparent_24%),linear-gradient(180deg,_rgba(7,17,31,0.96)_0%,_rgba(3,7,18,1)_100%)]" />
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-orange-500/20 to-transparent blur-3xl" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl items-center px-6 py-12">
        <div className="grid w-full gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="flex flex-col justify-center gap-8">
            <div className="inline-flex w-fit items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/75 backdrop-blur">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-500/15 text-orange-300">
                <Flame className="h-4 w-4" />
              </span>
              FireWatch Auth Shell
            </div>

            <div className="space-y-5">
              <h1 className="max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
                Вход в FireWatch для аналитиков, диспетчеров и админов
              </h1>
              <p className="max-w-2xl text-base leading-7 text-white/70 sm:text-lg">
                Используйте тестовую учётную запись, чтобы попасть в защищённые разделы и увидеть
                роль пользователя в интерфейсе.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-orange-200">
                  <ShieldCheck className="h-4 w-4" />
                  Защита маршрутов
                </div>
                <p className="text-sm leading-6 text-white/65">
                  `AuthProvider` + `RequireAuth` уже готовы для подключения к layout и страницам.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-emerald-200">
                  <LockKeyhole className="h-4 w-4" />
                  Сессия в браузере
                </div>
                <p className="text-sm leading-6 text-white/65">
                  Токен хранится в `localStorage` и восстанавливается через `GET /api/v2/auth/me`.
                </p>
              </div>
            </div>
          </section>

          <section className="flex items-center justify-center">
            <div className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-950/70 p-8 shadow-2xl shadow-black/40 backdrop-blur-xl">
              <div className="mb-8">
                <h2 className="text-2xl font-semibold">Войти в систему</h2>
                <p className="mt-2 text-sm text-white/60">Введите email и пароль тестового пользователя.</p>
              </div>

              <form className="space-y-5" onSubmit={handleSubmit}>
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-white/80">Email</span>
                  <input
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-white/30 focus:border-orange-400/60 focus:bg-white/7"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="admin@firewatch.kz"
                    autoComplete="email"
                    required
                  />
                </label>

                <label className="block space-y-2">
                  <span className="text-sm font-medium text-white/80">Пароль</span>
                  <input
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-white/30 focus:border-orange-400/60 focus:bg-white/7"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    required
                  />
                </label>

                {error ? (
                  <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-100">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={loading}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-orange-500 px-4 py-3 font-medium text-white transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? 'Входим...' : 'Войти'}
                  <ArrowRight className="h-4 w-4" />
                </button>
              </form>

              <div className="mt-8 border-t border-white/10 pt-6">
                <p className="text-sm font-medium text-white/75">Тестовые пользователи</p>
                <div className="mt-3 space-y-2">
                  {DEMO_USERS.map((user) => (
                    <button
                      key={user.email}
                      type="button"
                      onClick={() => {
                        setEmail(user.email)
                        setPassword(user.password)
                      }}
                      className="flex w-full items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left text-sm text-white/75 transition hover:border-orange-400/40 hover:bg-white/8"
                    >
                      <span>{user.email}</span>
                      <span className="text-xs uppercase tracking-[0.2em] text-white/45">{user.role}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  )
}

'use client'

import { Flame } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { useCity } from '@/context/CityContext'

const ROLE_LABELS = {
  viewer: 'viewer',
  dispatcher: 'dispatcher',
  analyst: 'analyst',
  admin: 'admin',
} as const

export function TopBar() {
  const { city, cities, setCity } = useCity()
  const { isAuthenticated, role, logout } = useAuth()
  const router = useRouter()

  return (
    <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-2">
        <Flame className="text-orange-500" size={22} />
        <span className="font-semibold text-white text-lg tracking-tight">FireWatch</span>
      </div>

      <div className="flex items-center gap-3">
        {isAuthenticated && role && (
          <span className="hidden md:inline-flex rounded-full border border-orange-400/30 bg-orange-500/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.18em] text-orange-200">
            {ROLE_LABELS[role]}
          </span>
        )}
        <label className="text-gray-400 text-sm">Город:</label>
        <select
          className="bg-gray-800 text-white text-sm border border-gray-700 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-orange-500"
          value={city?.id ?? ''}
          onChange={(e) => {
            const selected = cities.find((c) => c.id === e.target.value)
            if (selected) setCity(selected)
          }}
        >
          {cities.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        <span className="text-gray-500 text-xs hidden sm:block">
          Обновлено: {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
        </span>
        {isAuthenticated && (
          <button
            type="button"
            className="rounded-md border border-gray-700 px-3 py-1.5 text-xs text-gray-300 transition hover:border-orange-400/50 hover:text-white"
            onClick={() => {
              logout()
              router.replace('/login')
            }}
          >
            Выйти
          </button>
        )}
      </div>
    </header>
  )
}

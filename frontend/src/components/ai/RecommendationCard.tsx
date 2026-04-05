'use client'

import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { clsx } from 'clsx'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { Recommendation } from '@/lib/types'

const PRIORITY_CONFIG = {
  high: { label: 'Высокий', color: 'text-red-400 bg-red-400/10 border-red-400/20', Icon: AlertTriangle },
  medium: { label: 'Средний', color: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20', Icon: AlertCircle },
  low: { label: 'Низкий', color: 'text-green-400 bg-green-400/10 border-green-400/20', Icon: Info },
}

const CACHE_TTL_MS = 15 * 60 * 1000

function getCacheKey(cityId: string): string {
  return `firewatch.recommendations.${cityId}`
}

function readCache(cityId: string): Recommendation[] | null {
  if (typeof window === 'undefined') return null

  try {
    const raw = window.sessionStorage.getItem(getCacheKey(cityId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as { items: Recommendation[]; timestamp: number }
    if (!parsed?.items || !Array.isArray(parsed.items)) return null
    if (Date.now() - parsed.timestamp > CACHE_TTL_MS) return null
    return parsed.items
  } catch {
    return null
  }
}

function writeCache(cityId: string, nextItems: Recommendation[]) {
  if (typeof window === 'undefined') return
  window.sessionStorage.setItem(
    getCacheKey(cityId),
    JSON.stringify({ items: nextItems, timestamp: Date.now() }),
  )
}

export function RecommendationsPanel() {
  const { city } = useCity()
  const [items, setItems] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const visibleItems = items
  const showSkeleton = loading && !visibleItems.length

  const load = useCallback((cityId: string, { background = false, keepItems = false } = {}) => {
    if (!cityId) return Promise.resolve()

    if (background) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    return api.recommendations.get(cityId)
      .then((nextItems) => {
        setItems(nextItems)
        writeCache(cityId, nextItems)
      })
      .catch(() => {
        if (!keepItems) setItems([])
      })
      .finally(() => {
        setLoading(false)
        setRefreshing(false)
      })
  }, [])

  useEffect(() => {
    if (!city) return

    const timer = window.setTimeout(() => {
      const cachedItems = readCache(city.id)
      if (cachedItems?.length) {
        setItems(cachedItems)
        setLoading(false)
        void load(city.id, { background: true, keepItems: true })
        return
      }

      void load(city.id)
    }, 0)

    return () => window.clearTimeout(timer)
  }, [city, load])

  return (
    <div className="rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] p-5 flex flex-col gap-4 shadow-[0_24px_60px_rgba(0,0,0,0.22)]">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-semibold">Рекомендации по объектам</h2>
          <p className="text-xs text-slate-400">Адресные действия для инспекции и профилактики по зданиям города</p>
        </div>
        <button
          onClick={() => city && void load(city.id, { background: visibleItems.length > 0, keepItems: visibleItems.length > 0 })}
          disabled={loading || refreshing}
          className="flex items-center gap-1.5 rounded-xl border border-white/8 bg-white/4 px-3 py-2 text-xs text-gray-300 hover:bg-white/8 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading || refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Обновляем...' : 'Обновить'}
        </button>
      </div>

      {showSkeleton ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {refreshing && (
            <div className="rounded-2xl border border-sky-400/12 bg-sky-400/8 px-3 py-2 text-xs text-sky-50/90">
              Показываем последние сохранённые рекомендации и тихо обновляем данные в фоне.
            </div>
          )}
          {visibleItems.map((rec, i) => {
            const { label, color, Icon } = PRIORITY_CONFIG[rec.priority]
            return (
              <div key={i} className="rounded-2xl border border-white/8 bg-white/4 p-4 space-y-3 shadow-[0_12px_32px_rgba(0,0,0,0.18)]">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-white text-sm font-medium leading-6">{rec.title}</span>
                  <span className={clsx('flex items-center gap-1 text-xs px-2 py-0.5 rounded border shrink-0', color)}>
                    <Icon size={11} />
                    {label}
                  </span>
                </div>
                <p className="text-slate-300 text-sm leading-6">{rec.description}</p>
                <div className="rounded-2xl border border-emerald-400/12 bg-emerald-400/8 px-3 py-2 text-xs text-emerald-50/90">
                  Эффект: {rec.expected_impact}
                </div>
              </div>
            )
          })}
          {!visibleItems.length && (
            <div className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-gray-500">
              Рекомендации недоступны.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

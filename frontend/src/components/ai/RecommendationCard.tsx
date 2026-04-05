'use client'

import { useEffect, useState } from 'react'
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

export function RecommendationsPanel() {
  const { city } = useCity()
  const [items, setItems] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)

  function load() {
    if (!city) return
    setLoading(true)
    api.recommendations.get(city.id)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!city) return
    api.recommendations.get(city.id)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [city])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-white font-semibold">AI Рекомендации</h2>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Обновить
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((rec, i) => {
            const { label, color, Icon } = PRIORITY_CONFIG[rec.priority]
            return (
              <div key={i} className="border border-gray-800 rounded-lg p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-white text-sm font-medium">{rec.title}</span>
                  <span className={clsx('flex items-center gap-1 text-xs px-2 py-0.5 rounded border shrink-0', color)}>
                    <Icon size={11} />
                    {label}
                  </span>
                </div>
                <p className="text-gray-400 text-xs leading-relaxed">{rec.description}</p>
                <p className="text-gray-500 text-xs">Эффект: {rec.expected_impact}</p>
              </div>
            )
          })}
          {!items.length && (
            <div className="border border-dashed border-gray-800 rounded-lg p-4 text-sm text-gray-500">
              Рекомендации недоступны.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

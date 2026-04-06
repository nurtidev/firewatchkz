'use client'

import { useEffect, useState } from 'react'
import { RefreshCw, CheckCircle, Circle, AlertTriangle, AlertCircle, Info, ShieldCheck } from 'lucide-react'
import { clsx } from 'clsx'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { InspectorAlert } from '@/lib/types'

const PRIORITY_CONFIG = {
  critical: {
    label: 'Критический',
    badge: 'bg-red-500/10 text-red-400 border-red-500/30',
    border: 'border-red-500/30',
    icon: AlertTriangle,
    iconColor: 'text-red-400',
  },
  high: {
    label: 'Высокий',
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    border: 'border-orange-500/20',
    icon: AlertCircle,
    iconColor: 'text-orange-400',
  },
  medium: {
    label: 'Средний',
    badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
    border: 'border-yellow-500/20',
    icon: Info,
    iconColor: 'text-yellow-400',
  },
  low: {
    label: 'Низкий',
    badge: 'bg-green-500/10 text-green-400 border-green-500/30',
    border: 'border-gray-700',
    icon: ShieldCheck,
    iconColor: 'text-green-400',
  },
}

function formatTenge(v: number) {
  if (v >= 1_000_000_000) return `₸${(v / 1_000_000_000).toFixed(1)} млрд`
  if (v >= 1_000_000) return `₸${(v / 1_000_000).toFixed(0)} млн`
  return `₸${v.toLocaleString('ru-RU')}`
}

function FactorDots({ matched, total }: { matched: number; total: number }) {
  return (
    <div className="flex gap-1 items-center">
      {Array.from({ length: total }).map((_, i) => (
        i < matched
          ? <CheckCircle key={i} size={13} className="text-orange-400" />
          : <Circle key={i} size={13} className="text-gray-700" />
      ))}
      <span className="text-gray-500 text-xs ml-1">{matched}/{total} факторов</span>
    </div>
  )
}

function AlertCard({ alert }: { alert: InspectorAlert }) {
  const [open, setOpen] = useState(alert.priority === 'critical' || alert.priority === 'high')
  const cfg = PRIORITY_CONFIG[alert.priority]
  const Icon = cfg.icon

  return (
    <div className={clsx('bg-gray-900 border rounded-xl overflow-hidden', cfg.border)}>
      {/* Header */}
      <button
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-gray-800/40 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <Icon size={20} className={cfg.iconColor} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-white font-semibold">{alert.district}</span>
            <span className={clsx('text-xs px-2 py-0.5 rounded-full border font-medium', cfg.badge)}>
              {cfg.label}
            </span>
          </div>
          <div className="mt-1.5">
            <FactorDots matched={alert.matched_factors} total={alert.total_factors} />
          </div>
        </div>

        <div className="text-right shrink-0 hidden sm:block">
          <div className="text-white text-sm font-medium">{alert.risk_score.toFixed(0)}/100</div>
          <div className="text-gray-500 text-xs">индекс риска</div>
        </div>

        <span className={clsx('text-gray-500 transition-transform', open && 'rotate-180')}>▾</span>
      </button>

      {/* Expanded */}
      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-800">
          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4">
            <div className="bg-gray-950 rounded-lg px-3 py-2">
              <div className="text-gray-500 text-xs">Средний ущерб</div>
              <div className="text-white text-sm font-medium mt-0.5">{formatTenge(alert.avg_damage_tenge)}</div>
            </div>
            <div className="bg-gray-950 rounded-lg px-3 py-2">
              <div className="text-gray-500 text-xs">Последний пожар</div>
              <div className="text-white text-sm font-medium mt-0.5">
                {alert.days_since_last_incident !== null ? `${alert.days_since_last_incident} дн. назад` : 'нет данных'}
              </div>
            </div>
            <div className="bg-gray-950 rounded-lg px-3 py-2 col-span-2 sm:col-span-1">
              <div className="text-gray-500 text-xs">Индекс риска</div>
              <div className="text-white text-sm font-medium mt-0.5">{alert.risk_score.toFixed(1)} / 100</div>
            </div>
          </div>

          {/* Factors */}
          <div className="space-y-2">
            <div className="text-gray-400 text-xs font-medium uppercase tracking-wide">Факторы риска</div>
            {alert.factors.map((f, i) => (
              <div key={i} className="flex items-start gap-2.5">
                {f.matched
                  ? <CheckCircle size={15} className="text-orange-400 mt-0.5 shrink-0" />
                  : <Circle size={15} className="text-gray-700 mt-0.5 shrink-0" />
                }
                <span className={clsx('text-sm', f.matched ? 'text-gray-200' : 'text-gray-500')}>
                  {f.label}
                </span>
              </div>
            ))}
          </div>

          {/* Recommendation */}
          <div className="bg-orange-500/5 border border-orange-500/20 rounded-lg p-4">
            <div className="text-orange-400 text-xs font-medium uppercase tracking-wide mb-1.5">
              Рекомендация
            </div>
            <p className="text-gray-200 text-sm leading-relaxed">{alert.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function InspectorPage() {
  const { city } = useCity()
  const [alerts, setAlerts] = useState<InspectorAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  function load() {
    if (!city) return
    setLoading(true)
    api.inspector.get(city.id)
      .then((data) => {
        setAlerts(data)
        setLastUpdated(new Date())
      })
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!city) return

    async function syncInspector() {
      setLoading(true)
      try {
        const data = await api.inspector.get(city!.id)
        setAlerts(data)
        setLastUpdated(new Date())
      } catch {
        setAlerts([])
      } finally {
        setLoading(false)
      }
    }

    syncInspector()
  }, [city])

  const critical = alerts.filter(a => a.priority === 'critical').length
  const high = alerts.filter(a => a.priority === 'high').length

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-white font-semibold text-lg">Инспектор</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Анализ факторов риска по районам — приоритеты для превентивных проверок
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Обновить
        </button>
      </div>

      {/* Summary */}
      {!loading && alerts.length > 0 && (
        <div className="flex gap-3 flex-wrap text-sm">
          {critical > 0 && (
            <span className="flex items-center gap-1.5 bg-red-500/10 text-red-400 border border-red-500/20 px-3 py-1.5 rounded-full">
              <AlertTriangle size={13} />
              {critical} критических
            </span>
          )}
          {high > 0 && (
            <span className="flex items-center gap-1.5 bg-orange-500/10 text-orange-400 border border-orange-500/20 px-3 py-1.5 rounded-full">
              <AlertCircle size={13} />
              {high} высоких
            </span>
          )}
          {lastUpdated && (
            <span className="text-gray-600 text-xs self-center ml-auto">
              Обновлено: {lastUpdated.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
      )}

      {/* Cards */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <AlertCard key={alert.district} alert={alert} />
          ))}
        </div>
      )}
    </div>
  )
}

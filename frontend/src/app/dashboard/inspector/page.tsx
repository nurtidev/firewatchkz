'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  RefreshCw,
  CheckCircle,
  Circle,
  AlertTriangle,
  AlertCircle,
  Info,
  ShieldCheck,
  Navigation,
  MapPin,
  Clock,
  Route,
  Loader2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { InspectorAlert, InspectorBuilding, InspectorRoute } from '@/lib/types'

const InspectorRouteMap = dynamic(
  () => import('@/components/map/InspectorRouteMap'),
  { ssr: false }
)

// ─── v1 helpers ────────────────────────────────────────────────────────────

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
      {Array.from({ length: total }).map((_, i) =>
        i < matched
          ? <CheckCircle key={i} size={13} className="text-orange-400" />
          : <Circle key={i} size={13} className="text-gray-700" />
      )}
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

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-800">
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

// ─── v1 mode panel ─────────────────────────────────────────────────────────

function V1Panel({ city }: { city: string }) {
  const [alerts, setAlerts] = useState<InspectorAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  function load() {
    setLoading(true)
    api.inspector.get(city)
      .then((data) => {
        setAlerts(data)
        setLastUpdated(new Date())
      })
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city])

  const critical = alerts.filter(a => a.priority === 'critical').length
  const high = alerts.filter(a => a.priority === 'high').length

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <p className="text-gray-500 text-sm">
          Анализ факторов риска по районам — приоритеты для превентивных проверок
        </p>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Обновить
        </button>
      </div>

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

// ─── v2 helpers ────────────────────────────────────────────────────────────

const RISK_LEVEL_CONFIG = {
  high: {
    label: 'HIGH',
    dot: 'bg-red-500',
    text: 'text-red-400',
    badge: 'bg-red-500/10 text-red-400 border border-red-500/30',
  },
  medium: {
    label: 'MEDIUM',
    dot: 'bg-yellow-400',
    text: 'text-yellow-400',
    badge: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30',
  },
  low: {
    label: 'LOW',
    dot: 'bg-green-500',
    text: 'text-green-400',
    badge: 'bg-green-500/10 text-green-400 border border-green-500/30',
  },
}

const TOP_N_OPTIONS = [10, 20, 50, 100]

// ─── v2 mode panel ─────────────────────────────────────────────────────────

function V2Panel({ city }: { city: string }) {
  const router = useRouter()
  const [topN, setTopN] = useState(50)
  const [minRisk, setMinRisk] = useState(0.5)
  const [minRiskInput, setMinRiskInput] = useState('0.5')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [route, setRoute] = useState<InspectorRoute | null>(null)
  const [buildings, setBuildings] = useState<InspectorBuilding[]>([])

  // Map waypoints — use route.waypoints when available, else derive from buildings list
  const mapWaypoints = route
    ? route.waypoints
    : buildings
        .filter((b) => b.lat !== null && b.lon !== null)
        .slice(0, 10)
        .map((b) => ({
          building_id: b.building_id,
          lat: b.lat as number,
          lon: b.lon as number,
          address: b.address,
          final_score: b.final_score,
        }))

  async function handleCalculate() {
    setLoading(true)
    setError(null)
    setRoute(null)
    setBuildings([])
    try {
      const bList = await api.inspector.list(city, topN, minRisk)
      setBuildings(bList)
      if (bList.length === 0) {
        setError('Нет зданий, удовлетворяющих условиям фильтра.')
        return
      }
      const ids = bList.map((b) => b.building_id)
      const r = await api.inspector.route(ids)
      setRoute(r)
    } catch {
      setError('Не удалось загрузить данные. Проверьте подключение к серверу.')
    } finally {
      setLoading(false)
    }
  }

  // Ordered building list: use route order when available
  const orderedBuildings: InspectorBuilding[] = route
    ? route.ordered_buildings
        .map((id) => buildings.find((b) => b.building_id === id))
        .filter((b): b is InspectorBuilding => Boolean(b))
    : buildings

  return (
    <div className="space-y-5">
      {/* Controls + map grid */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Left: controls */}
        <div className="lg:w-64 shrink-0 space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
            {/* Top N */}
            <div>
              <label className="text-gray-400 text-xs uppercase tracking-wide block mb-1.5">
                Топ-N зданий
              </label>
              <div className="flex gap-2 flex-wrap">
                {TOP_N_OPTIONS.map((n) => (
                  <button
                    key={n}
                    onClick={() => setTopN(n)}
                    className={clsx(
                      'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                      topN === n
                        ? 'bg-orange-500 text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            {/* Min risk */}
            <div>
              <label className="text-gray-400 text-xs uppercase tracking-wide block mb-1.5">
                Мин. риск
              </label>
              <input
                type="number"
                min={0}
                max={10}
                step={0.1}
                value={minRiskInput}
                onChange={(e) => {
                  setMinRiskInput(e.target.value)
                  const v = parseFloat(e.target.value)
                  if (!isNaN(v)) setMinRisk(v)
                }}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-orange-500"
              />
            </div>

            {/* Calculate button */}
            <button
              onClick={handleCalculate}
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-orange-500 text-white font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-50 hover:bg-orange-600 transition-colors"
            >
              {loading
                ? <><Loader2 size={15} className="animate-spin" /> Загрузка...</>
                : <><Navigation size={15} /> Рассчитать маршрут</>
              }
            </button>
          </div>

          {/* Route summary */}
          {route && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
              <div className="text-gray-400 text-xs uppercase tracking-wide">Маршрут</div>
              <div className="flex items-center gap-2">
                <Route size={14} className="text-orange-400" />
                <span className="text-white text-sm font-medium">
                  {route.total_distance_km.toFixed(1)} км
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-orange-400" />
                <span className="text-white text-sm font-medium">
                  ~{route.estimated_time_min.toFixed(0)} мин
                </span>
              </div>
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-orange-400" />
                <span className="text-white text-sm font-medium">
                  {route.ordered_buildings.length} объектов
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Right: map */}
        <div className="flex-1 min-h-64 lg:min-h-80 rounded-xl overflow-hidden bg-gray-900 border border-gray-800">
          {mapWaypoints.length > 0 ? (
            <InspectorRouteMap
              waypoints={mapWaypoints}
              defaultCenter={[51.1282, 71.43]}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-2 p-6 text-center">
              <MapPin size={28} />
              <p className="text-sm">Нажмите «Рассчитать маршрут» для отображения карты</p>
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Building list */}
      {orderedBuildings.length > 0 && (
        <div className="space-y-2">
          <div className="text-gray-400 text-xs uppercase tracking-wide font-medium px-1">
            Список объектов (порядок маршрута)
          </div>

          {/* Desktop table */}
          <div className="hidden sm:block bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left text-gray-500 text-xs uppercase tracking-wide px-4 py-3 w-10">#</th>
                  <th className="text-left text-gray-500 text-xs uppercase tracking-wide px-4 py-3">Адрес</th>
                  <th className="text-left text-gray-500 text-xs uppercase tracking-wide px-4 py-3 hidden md:table-cell">Тип</th>
                  <th className="text-right text-gray-500 text-xs uppercase tracking-wide px-4 py-3">Риск</th>
                  <th className="text-right text-gray-500 text-xs uppercase tracking-wide px-4 py-3">Уровень</th>
                </tr>
              </thead>
              <tbody>
                {orderedBuildings.map((b, i) => {
                  const cfg = RISK_LEVEL_CONFIG[b.risk_level]
                  return (
                    <tr
                      key={b.building_id}
                      className="border-b border-gray-800/50 last:border-0 hover:bg-gray-800/40 cursor-pointer transition-colors"
                      onClick={() => router.push(`/dashboard/buildings/${b.building_id}`)}
                    >
                      <td className="px-4 py-3 text-gray-500 text-xs">{i + 1}</td>
                      <td className="px-4 py-3">
                        <span className="text-white">{b.address || '—'}</span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-gray-400 text-xs">
                        {b.building_type || '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-gray-300 font-medium tabular-nums">
                          {b.final_score.toFixed(2)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', cfg.badge)}>
                          <span className={clsx('inline-block w-1.5 h-1.5 rounded-full mr-1', cfg.dot)} />
                          {cfg.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="sm:hidden space-y-2">
            {orderedBuildings.map((b, i) => {
              const cfg = RISK_LEVEL_CONFIG[b.risk_level]
              return (
                <div
                  key={b.building_id}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-start gap-3 cursor-pointer active:bg-gray-800/60"
                  onClick={() => router.push(`/dashboard/buildings/${b.building_id}`)}
                >
                  <div className="shrink-0 w-7 h-7 rounded-full bg-gray-800 flex items-center justify-center text-gray-400 text-xs font-bold">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium truncate">{b.address || '—'}</p>
                    {b.building_type && (
                      <p className="text-gray-500 text-xs mt-0.5">{b.building_type}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', cfg.badge)}>
                        <span className={clsx('inline-block w-1.5 h-1.5 rounded-full mr-1', cfg.dot)} />
                        {cfg.label}
                      </span>
                      <span className="text-gray-500 text-xs">риск: {b.final_score.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Root page ──────────────────────────────────────────────────────────────

type Mode = 'v1' | 'v2'

export default function InspectorPage() {
  const { city } = useCity()
  const [mode, setMode] = useState<Mode>('v1')

  const cityId = city?.id ?? 'astana'

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-white font-semibold text-lg">Инспектор</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {mode === 'v1'
              ? 'Анализ факторов риска по районам — приоритеты для превентивных проверок'
              : 'Обход зданий с высоким риском — оптимальный маршрут инспектора'}
          </p>
        </div>

        {/* Mode switcher */}
        <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 shrink-0 self-start">
          <button
            onClick={() => setMode('v1')}
            className={clsx(
              'px-4 py-1.5 rounded-lg text-sm font-medium transition-colors',
              mode === 'v1'
                ? 'bg-orange-500 text-white'
                : 'text-gray-400 hover:text-white'
            )}
          >
            v1 Районы
          </button>
          <button
            onClick={() => setMode('v2')}
            className={clsx(
              'px-4 py-1.5 rounded-lg text-sm font-medium transition-colors',
              mode === 'v2'
                ? 'bg-orange-500 text-white'
                : 'text-gray-400 hover:text-white'
            )}
          >
            v2 Здания
          </button>
        </div>
      </div>

      {/* Panel */}
      {mode === 'v1'
        ? <V1Panel city={cityId} />
        : <V2Panel city={cityId} />
      }
    </div>
  )
}

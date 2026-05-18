'use client'

import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts'
import { Flame, AlertOctagon, Heart, Clock } from 'lucide-react'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { OperationsAnalytics } from '@/lib/types'

const CAUSE_RU: Record<string, string> = {
  electrical: 'электропроводка',
  open_flame: 'открытый огонь',
  arson: 'поджог',
  children: 'детская шалость',
  heating: 'отопление',
  smoking: 'курение',
  other: 'прочее',
}

const SEVERITY_RU: Record<string, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
  critical: 'Критический',
}

const SEVERITY_COLORS: Record<string, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
}

function formatTenge(value: number): string {
  if (value >= 1_000_000_000) return `₸${(value / 1_000_000_000).toFixed(1)} млрд`
  if (value >= 1_000_000) return `₸${(value / 1_000_000).toFixed(0)} млн`
  if (value >= 1000) return `₸${(value / 1000).toFixed(0)} тыс.`
  return `₸${value.toLocaleString('ru-RU')}`
}

function StatCard({
  icon,
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  icon: React.ReactNode
  label: string
  value: string
  hint?: string
  tone?: 'neutral' | 'critical' | 'warn'
}) {
  const toneCls =
    tone === 'critical'
      ? 'border-red-500/30 bg-red-500/5'
      : tone === 'warn'
      ? 'border-yellow-500/30 bg-yellow-500/5'
      : 'border-gray-700 bg-gray-900/50'
  return (
    <div className={`rounded-xl border px-4 py-3 ${toneCls}`}>
      <div className="flex items-center gap-2 text-gray-400 text-xs uppercase tracking-wide">
        <span className="opacity-80">{icon}</span>
        <span>{label}</span>
      </div>
      <div className="text-white font-semibold text-xl mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-gray-500 text-xs mt-1">{hint}</div>}
    </div>
  )
}

export default function OperationsPage() {
  const { city } = useCity()
  const cityId = city?.id ?? 'astana'
  const [data, setData] = useState<OperationsAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api.operations
      .analytics(cityId)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch(() => {
        if (!cancelled) setError('Не удалось загрузить аналитику.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [cityId])

  const causeData = (data?.by_cause ?? []).slice(0, 6).map((c) => ({
    name: CAUSE_RU[c.cause] ?? c.cause,
    count: c.count,
    damage: c.damage_tenge,
  }))

  const monthlyData = (data?.monthly ?? []).map((m) => ({
    name: m.month,
    incidents: m.count,
  }))

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-white text-xl font-bold">Аналитика последствий</h1>
        <p className="text-gray-400 text-sm mt-1">
          Сводка по инцидентам, ущербу, жертвам и времени реагирования. Источник —
          таблицы incidents и operations.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 text-red-300 text-sm px-4 py-3">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-xl bg-gray-900 border border-gray-800 animate-pulse" />
          ))}
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              icon={<Flame size={14} />}
              label="Инцидентов"
              value={data.totals.incidents.toLocaleString('ru-RU')}
              tone="warn"
            />
            <StatCard
              icon={<AlertOctagon size={14} />}
              label="Ущерб"
              value={formatTenge(data.totals.damage_tenge)}
              tone="critical"
            />
            <StatCard
              icon={<Heart size={14} />}
              label="Пострадавшие"
              value={data.totals.casualties.toLocaleString('ru-RU')}
              tone={data.totals.casualties > 0 ? 'critical' : 'neutral'}
            />
            <StatCard
              icon={<Clock size={14} />}
              label="Сред. время реагирования"
              value={data.totals.avg_response_min ? `${data.totals.avg_response_min} мин` : '—'}
              hint={data.totals.avg_response_min ? 'по таблице operations' : 'нет данных'}
            />
          </div>

          {/* By cause */}
          <section className="bg-gray-800 rounded-xl border border-gray-700 p-5">
            <h2 className="text-white font-semibold text-sm uppercase tracking-wide mb-4">
              Причины пожаров (топ-6 по числу инцидентов)
            </h2>
            {causeData.length === 0 ? (
              <p className="text-gray-500 text-sm">Нет данных.</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={causeData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#374151" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#374151' }} tickLine={false} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#374151' }} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, color: '#f9fafb', fontSize: 12 }}
                    formatter={(value, name, entry) => {
                      const damage = (entry?.payload as { damage?: number } | undefined)?.damage
                      const valueStr = typeof value === 'number' ? value.toLocaleString('ru-RU') : String(value)
                      return [`${valueStr}${damage ? ` · ущерб ${formatTenge(damage)}` : ''}`, 'Инцидентов'] as [string, string]
                    }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]} fill="#f97316" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </section>

          {/* Severity */}
          <section className="bg-gray-800 rounded-xl border border-gray-700 p-5">
            <h2 className="text-white font-semibold text-sm uppercase tracking-wide mb-4">
              По степени тяжести
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {(['critical', 'high', 'medium', 'low'] as const).map((sev) => {
                const row = data.by_severity.find((r) => r.severity === sev)
                const count = row?.count ?? 0
                return (
                  <div
                    key={sev}
                    className="rounded-lg border px-3 py-2.5"
                    style={{ borderColor: `${SEVERITY_COLORS[sev]}40`, backgroundColor: `${SEVERITY_COLORS[sev]}0d` }}
                  >
                    <div className="text-[10px] uppercase tracking-wide" style={{ color: SEVERITY_COLORS[sev] }}>
                      {SEVERITY_RU[sev]}
                    </div>
                    <div className="text-white font-semibold text-lg tabular-nums">{count.toLocaleString('ru-RU')}</div>
                  </div>
                )
              })}
            </div>
          </section>

          {/* Monthly trend */}
          <section className="bg-gray-800 rounded-xl border border-gray-700 p-5">
            <h2 className="text-white font-semibold text-sm uppercase tracking-wide mb-4">
              Динамика инцидентов (12 месяцев)
            </h2>
            {monthlyData.length === 0 ? (
              <p className="text-gray-500 text-sm">Нет данных за последний год.</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={monthlyData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#374151" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#374151' }} tickLine={false} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#374151' }} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, color: '#f9fafb', fontSize: 12 }}
                    formatter={(value) => [
                      typeof value === 'number' ? value.toLocaleString('ru-RU') : String(value),
                      'Инцидентов',
                    ]}
                  />
                  <Line type="monotone" dataKey="incidents" stroke="#f97316" strokeWidth={2} dot={{ r: 3, fill: '#f97316' }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </section>
        </>
      ) : null}
    </div>
  )
}


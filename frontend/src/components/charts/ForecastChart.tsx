'use client'

import { useEffect, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { ForecastPoint } from '@/lib/types'

type Months = 3 | 6 | 12

function mergePoints(historical: ForecastPoint[], forecast: ForecastPoint[]): ForecastPoint[] {
  const map = new Map<string, ForecastPoint>()
  for (const point of historical) map.set(point.period, { ...point })
  for (const point of forecast) map.set(point.period, { ...map.get(point.period), ...point })
  return Array.from(map.values()).sort((a, b) => a.period.localeCompare(b.period))
}

function formatPeriod(period: string): string {
  const [year, month] = period.split('-')
  return `${month}.${year.slice(2)}`
}

export function ForecastChart() {
  const { city } = useCity()
  const [months, setMonths] = useState<Months>(6)
  const [data, setData] = useState<ForecastPoint[]>([])
  const [r2, setR2] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!city) return
    let cancelled = false

    api.forecast
      .get(city.id, months)
      .then((response) => {
        if (cancelled) return
        setData(mergePoints(response.historical, response.forecast))
        setR2(response.r_squared)
      })
      .catch(() => {
        if (cancelled) return
        setData([])
        setR2(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [city, months])

  const forecastStart = data.find((point) => typeof point.predicted === 'number')?.period
  const forecastEnd = data[data.length - 1]?.period
  const lastActual = [...data].reverse().find((point) => typeof point.actual === 'number')
  const nextForecast = data.find((point) => typeof point.predicted === 'number')

  return (
    <div className="rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] p-5 flex flex-col gap-4 shadow-[0_24px_60px_rgba(0,0,0,0.22)]">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-semibold">Прогноз инцидентов</h2>
          {r2 !== null && (
            <span className="text-gray-500 text-xs">Точность модели: R² = {r2.toFixed(2)}</span>
          )}
        </div>
        <div className="flex gap-1 rounded-2xl border border-white/8 bg-white/4 p-1">
          {([3, 6, 12] as Months[]).map((value) => (
            <button
              key={value}
              onClick={() => {
                setLoading(true)
                setMonths(value)
              }}
              className={`px-3 py-1 rounded-xl text-xs font-medium transition-colors ${
                months === value ? 'bg-orange-500 text-white shadow-sm' : 'text-gray-400 hover:bg-white/6 hover:text-white'
              }`}
            >
              {value}М
            </button>
          ))}
        </div>
      </div>

      {!loading && (lastActual || nextForecast) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-2xl border border-white/8 bg-white/4 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">Последний факт</div>
            <div className="mt-1 text-lg font-semibold text-white">{lastActual?.actual ?? '—'}</div>
            <div className="text-xs text-gray-500">{lastActual ? formatPeriod(lastActual.period) : '—'}</div>
          </div>
          <div className="rounded-2xl border border-orange-400/15 bg-orange-500/6 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-orange-200/70">Следующий прогноз</div>
            <div className="mt-1 text-lg font-semibold text-white">{nextForecast?.predicted ?? '—'}</div>
            <div className="text-xs text-gray-500">{nextForecast ? formatPeriod(nextForecast.period) : '—'}</div>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/4 px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">Диапазон 80%</div>
            <div className="mt-1 text-lg font-semibold text-white">
              {nextForecast ? `${nextForecast.lower_80}-${nextForecast.upper_80}` : '—'}
            </div>
            <div className="text-xs text-gray-500">Для ближайшего прогнозного периода</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="h-72 bg-white/6 rounded-2xl animate-pulse" />
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data}>
            <defs>
              <linearGradient id="actualFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            {forecastStart && forecastEnd && (
              <ReferenceArea x1={forecastStart} x2={forecastEnd} fill="#f97316" fillOpacity={0.06} />
            )}
            <XAxis
              dataKey="period"
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              tickFormatter={(value, index) => (index % 2 === 0 ? formatPeriod(String(value)) : '')}
              tickLine={false}
              axisLine={false}
            />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 12 }}
              labelStyle={{ color: '#f9fafb' }}
              itemStyle={{ color: '#d1d5db' }}
              labelFormatter={(value) => `Период: ${formatPeriod(String(value))}`}
            />
            <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 12 }} />

            <Area
              type="monotone"
              dataKey="actual"
              fill="url(#actualFill)"
              stroke="none"
              connectNulls={false}
              legendType="none"
            />
            <Area dataKey="lower_80" stackId="interval" fillOpacity={0} stroke="none" legendType="none" />
            <Area
              dataKey={(point) => {
                if (typeof point.upper_80 !== 'number' || typeof point.lower_80 !== 'number') return undefined
                return Math.max(point.upper_80 - point.lower_80, 0)
              }}
              stackId="interval"
              fill="#f97316"
              fillOpacity={0.12}
              stroke="none"
              name="Диапазон 80%"
              legendType="none"
            />
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#3b82f6"
              strokeWidth={2.5}
              dot={{ r: 2, fill: '#bfdbfe', stroke: '#3b82f6', strokeWidth: 1 }}
              name="Факт"
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="predicted"
              stroke="#f97316"
              strokeWidth={2.5}
              strokeDasharray="5 4"
              dot={{ r: 2, fill: '#fed7aa', stroke: '#f97316', strokeWidth: 1 }}
              name="Прогноз"
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

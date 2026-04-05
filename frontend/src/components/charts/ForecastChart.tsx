'use client'

import { useState, useEffect } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { ForecastPoint } from '@/lib/types'

type Months = 3 | 6 | 12

function mergePoints(historical: ForecastPoint[], forecast: ForecastPoint[]): ForecastPoint[] {
  const map = new Map<string, ForecastPoint>()
  for (const p of historical) map.set(p.period, { ...p })
  for (const p of forecast) map.set(p.period, { ...map.get(p.period), ...p })
  return Array.from(map.values()).sort((a, b) => a.period.localeCompare(b.period))
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

    api.forecast.get(city.id, months)
      .then((res) => {
        if (cancelled) return
        setData(mergePoints(res.historical, res.forecast))
        setR2(res.r_squared)
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

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-semibold">Прогноз инцидентов</h2>
          {r2 !== null && (
            <span className="text-gray-500 text-xs">Точность модели: R² = {r2.toFixed(2)}</span>
          )}
        </div>
        <div className="flex gap-1">
          {([3, 6, 12] as Months[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setLoading(true)
                setMonths(m)
              }}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                months === m
                  ? 'bg-orange-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {m}М
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-64 bg-gray-800 rounded animate-pulse" />
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="period"
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              tickFormatter={(v) => v.slice(0, 7)}
            />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
              labelStyle={{ color: '#f9fafb' }}
              itemStyle={{ color: '#d1d5db' }}
            />
            <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 12 }} />

            {/* Confidence interval */}
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

            {/* Historical */}
            <Line
              dataKey="actual"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="Факт"
              connectNulls={false}
            />

            {/* Forecast */}
            <Line
              dataKey="predicted"
              stroke="#f97316"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              name="Прогноз"
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

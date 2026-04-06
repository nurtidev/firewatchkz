'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
  ComposedChart,
} from 'recharts'
import { useCity } from '@/context/CityContext'

type OperationItem = {
  id: string
  date: string
  city: string
  district: string
  station_id: string
  incident_id: string
  response_time_min: number
  outcome: string
  notes: string
}

type OperationsResponse = {
  total: number
  items: OperationItem[]
}

type OperationsKpiResponse = {
  city: string
  avg_response_time_min: number
  operations_count: number
  fastest_station: string | null
  slowest_district: string | null
}

type PanelPoint = {
  date: string
  avg_response_time_min: number
  operations_count: number
}

type Props = {
  cityId?: string
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`)
  }
  return response.json()
}

function formatMinutes(value: number): string {
  return `${value.toFixed(1)} мин`
}

function aggregateOperations(items: OperationItem[]): PanelPoint[] {
  const grouped = new Map<string, { totalResponse: number; count: number }>()

  for (const item of items) {
    const bucket = grouped.get(item.date) ?? { totalResponse: 0, count: 0 }
    bucket.totalResponse += item.response_time_min
    bucket.count += 1
    grouped.set(item.date, bucket)
  }

  return Array.from(grouped.entries())
    .map(([date, value]) => ({
      date,
      avg_response_time_min: value.count > 0 ? value.totalResponse / value.count : 0,
      operations_count: value.count,
    }))
    .sort((a, b) => a.date.localeCompare(b.date))
}

export function ResponseTimeChart({ cityId }: Props) {
  const { city } = useCity()
  const resolvedCityId = cityId ?? city?.id
  const [history, setHistory] = useState<PanelPoint[]>([])
  const [kpi, setKpi] = useState<OperationsKpiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!resolvedCityId) {
      setLoading(false)
      setHistory([])
      setKpi(null)
      setError(null)
      return
    }
    let cancelled = false

    async function loadData() {
      setLoading(true)
      setError(null)

      try {
        const [operations, operationsKpi] = await Promise.all([
          fetchJson<OperationsResponse>(`/api/v1/operations?city=${resolvedCityId}`),
          fetchJson<OperationsKpiResponse>(`/api/v1/operations/kpi?city=${resolvedCityId}`),
        ])

        if (cancelled) return

        setHistory(aggregateOperations(operations.items))
        setKpi(operationsKpi)
      } catch (loadError) {
        if (cancelled) return
        setHistory([])
        setKpi(null)
        setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить данные операций')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadData()

    return () => {
      cancelled = true
    }
  }, [resolvedCityId])

  const summary = useMemo(() => {
    if (!history.length) return null
    const maxResponse = Math.max(...history.map((item) => item.avg_response_time_min))
    const minResponse = Math.min(...history.map((item) => item.avg_response_time_min))
    return { maxResponse, minResponse }
  }, [history])

  return (
    <div className="rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] p-5 flex flex-col gap-4 shadow-[0_24px_60px_rgba(0,0,0,0.22)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-white font-semibold">Время реагирования</h2>
          <p className="text-gray-500 text-sm">
            KPI и динамика операций по выбранному городу
          </p>
        </div>

        {kpi && !loading && (
          <div className="text-right text-xs text-gray-400 space-y-1">
            <div>Среднее: <span className="text-gray-200">{formatMinutes(kpi.avg_response_time_min)}</span></div>
            <div>Быстрее всего: <span className="text-gray-200">{kpi.fastest_station ?? '—'}</span></div>
            <div>Медленнее всего: <span className="text-gray-200">{kpi.slowest_district ?? '—'}</span></div>
          </div>
        )}
      </div>

      {loading ? (
        <div className="h-72 bg-white/6 rounded-2xl animate-pulse" />
      ) : error ? (
        <div className="rounded-lg border border-dashed border-gray-700 bg-gray-950/40 px-4 py-8 text-sm text-gray-400">
          {error}
        </div>
      ) : history.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-700 bg-gray-950/40 px-4 py-8 text-sm text-gray-400">
          Нет данных по операциям для выбранного города.
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickFormatter={(value: string) => value.slice(5)}
              />
              <YAxis
                yAxisId="left"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickFormatter={(value: number) => `${value.toFixed(0)}м`}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#f9fafb' }}
                formatter={(value, name) => {
                  const v = value as number
                  if (name === 'Среднее время') return [formatMinutes(v), name]
                  return [v, name]
                }}
              />
              <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 12 }} />
              <Bar
                yAxisId="right"
                dataKey="operations_count"
                name="Количество операций"
                fill="#334155"
                radius={[4, 4, 0, 0]}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="avg_response_time_min"
                name="Среднее время"
                stroke="#f97316"
                strokeWidth={2.5}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>

          {summary && (
            <div className="grid grid-cols-2 gap-3 text-xs text-gray-400">
              <div className="rounded-lg bg-gray-950/50 border border-gray-800 px-3 py-2">
                Пик времени: <span className="text-gray-200">{formatMinutes(summary.maxResponse)}</span>
              </div>
              <div className="rounded-lg bg-gray-950/50 border border-gray-800 px-3 py-2">
                Минимум времени: <span className="text-gray-200">{formatMinutes(summary.minResponse)}</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

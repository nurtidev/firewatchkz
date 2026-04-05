'use client'

import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { DistrictRisk } from '@/lib/types'

function riskColor(score: number) {
  if (score >= 67) return '#ef4444'
  if (score >= 34) return '#eab308'
  return '#22c55e'
}

export function IncidentsByDistrict() {
  const { city } = useCity()
  const [data, setData] = useState<DistrictRisk[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!city) return
    let cancelled = false

    api.riskMap.get(city.id)
      .then((items) => {
        if (!cancelled) setData(items)
      })
      .catch(() => {
        if (!cancelled) setData([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [city])

  return (
    <div className="rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] p-5 flex flex-col gap-4 shadow-[0_24px_60px_rgba(0,0,0,0.22)]">
      <div>
        <h2 className="text-white font-semibold">Инциденты по районам</h2>
        <p className="text-xs text-gray-500 mt-1">Сравнение районов по частоте инцидентов и уровню риска</p>
      </div>

      {loading ? (
        <div className="h-48 bg-white/6 rounded-2xl animate-pulse" />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
            <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <YAxis
              dataKey="district"
              type="category"
              tick={{ fill: '#cbd5e1', fontSize: 11 }}
              width={72}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
              labelStyle={{ color: '#f9fafb' }}
              formatter={(val, _name, props) => [
                `${val} (риск: ${props.payload.risk_score})`,
                'Инцидентов',
              ]}
            />
            <Bar dataKey="total_incidents" radius={[0, 10, 10, 0]} barSize={18}>
              {data.map((entry) => (
                <Cell key={entry.district} fill={riskColor(entry.risk_score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

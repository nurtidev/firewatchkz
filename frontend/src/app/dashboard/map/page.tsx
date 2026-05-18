'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { Building2, Flame, MapPin } from 'lucide-react'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { BuildingRiskItem, DistrictRisk } from '@/lib/types'

const RiskMap = dynamic(
  () => import('@/components/map/RiskMap').then((m) => m.RiskMap),
  {
    ssr: false,
    loading: () => <div className="h-[calc(100vh-220px)] rounded-[28px] bg-gray-900 border border-gray-800 animate-pulse" />,
  }
)

function StatChip({
  icon,
  label,
  value,
  tone = 'neutral',
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  tone?: 'neutral' | 'critical' | 'ok'
}) {
  const toneClass =
    tone === 'critical'
      ? 'border-red-400/30 bg-red-500/10 text-red-200'
      : tone === 'ok'
      ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200'
      : 'border-white/10 bg-slate-900/60 text-gray-200'
  return (
    <div className={`flex items-center gap-3 rounded-2xl border px-4 py-2.5 backdrop-blur ${toneClass}`}>
      <div className="opacity-80">{icon}</div>
      <div className="leading-tight">
        <div className="text-[11px] uppercase tracking-wide opacity-70">{label}</div>
        <div className="text-base font-semibold">{value}</div>
      </div>
    </div>
  )
}

export default function MapPage() {
  const { city } = useCity()
  const [districts, setDistricts] = useState<DistrictRisk[]>([])
  const [topBuildings, setTopBuildings] = useState<BuildingRiskItem[]>([])
  const [visibleCount, setVisibleCount] = useState<number>(0)

  useEffect(() => {
    if (!city) return
    let cancelled = false

    api.riskMap
      .get(city.id)
      .then((data) => {
        if (!cancelled) setDistricts(data)
      })
      .catch(() => {
        if (!cancelled) setDistricts([])
      })

    api.buildings
      .listRisk(city.id, undefined, 500)
      .then((data) => {
        if (!cancelled) setTopBuildings(data)
      })
      .catch(() => {
        if (!cancelled) setTopBuildings([])
      })

    return () => {
      cancelled = true
    }
  }, [city])

  const highRiskBuildings = topBuildings.filter((b) => b.risk_level === 'high').length
  const highRiskDistricts = districts.filter((d) => d.risk_score >= 67).length

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-white font-semibold text-xl">Карта риска по зданиям</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Здания подсвечены по риск-баллу ML-модели. Кликните по точке для детального разбора.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatChip
            icon={<Building2 size={16} />}
            label="Зданий на экране"
            value={visibleCount.toLocaleString('ru-RU')}
          />
          <StatChip
            icon={<Flame size={16} />}
            label="Высокий риск"
            value={highRiskBuildings.toLocaleString('ru-RU')}
            tone={highRiskBuildings > 0 ? 'critical' : 'ok'}
          />
          <StatChip
            icon={<MapPin size={16} />}
            label="Опасные районы"
            value={`${highRiskDistricts}/${districts.length || '—'}`}
            tone={highRiskDistricts > 0 ? 'critical' : 'neutral'}
          />
        </div>
      </div>

      {city ? (
        <RiskMap
          key={city.id}
          height="calc(100vh - 220px)"
          showFilters
          defaultLayers={{ buildings: true, districts: false, stations: true, hydrants: false }}
          onCounts={({ buildingsVisible }) => setVisibleCount(buildingsVisible)}
        />
      ) : (
        <div className="h-[calc(100vh-220px)] rounded-[28px] bg-gray-900 border border-gray-800 animate-pulse" />
      )}
    </div>
  )
}

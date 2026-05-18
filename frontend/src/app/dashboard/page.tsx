'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { Flame, TrendingDown, TrendingUp, ShieldAlert } from 'lucide-react'
import { InspectionPlanPanel } from '@/components/ai/InspectionPlanPanel'
import { IncidentsByDistrict } from '@/components/charts/IncidentsByDistrict'
import { ResponseTimeChart } from '@/components/charts/ResponseTimeChart'
import { StatCard } from '@/components/layout/StatCard'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { KPI } from '@/lib/types'

const CAUSE_RU: Record<string, string> = {
  electrical: 'электропроводка',
  open_flame: 'открытый огонь',
  arson: 'поджог',
  children: 'детская шалость',
  other: 'прочее',
}

const RiskMap = dynamic(() => import('@/components/map/RiskMap').then((m) => m.RiskMap), {
  ssr: false,
  loading: () => <div className="h-[420px] bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />,
})

function translateCause(cause: string): string {
  return CAUSE_RU[cause] ?? cause
}

function formatTenge(value: number): string {
  if (value >= 1_000_000_000) return `₸${(value / 1_000_000_000).toFixed(1)} млрд`
  if (value >= 1_000_000) return `₸${(value / 1_000_000).toFixed(0)} млн`
  return `₸${value.toLocaleString('ru-RU')}`
}

function DashboardContent({ cityId }: { cityId: string }) {
  const [kpi, setKpi] = useState<KPI | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    api.kpi
      .get(cityId)
      .then(setKpi)
      .catch(() => setKpi(null))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [cityId])

  const trendDir = kpi ? (kpi.vs_last_year_pct > 0 ? 'up' : 'down') : 'neutral'

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Пожаров с начала года"
          value={kpi ? String(kpi.total_incidents_ytd) : '—'}
          sub={
            kpi
              ? `${kpi.vs_last_year_pct > 0 ? '+' : ''}${kpi.vs_last_year_pct.toFixed(1)}% к прошлому году`
              : undefined
          }
          subTrend={trendDir}
          icon={<Flame size={18} />}
          loading={loading}
        />
        <StatCard
          title="Ущерб с начала года"
          value={kpi ? formatTenge(kpi.total_damage_tenge) : '—'}
          icon={<TrendingUp size={18} />}
          loading={loading}
        />
        <StatCard
          title="Можно предотвратить"
          value={kpi ? formatTenge(kpi.prevention_potential_tenge) : '—'}
          sub={kpi ? `~${kpi.prevention_potential_incidents} пожаров в год` : undefined}
          subTrend="down"
          icon={<TrendingDown size={18} />}
          loading={loading}
        />
        <StatCard
          title="Самый опасный район"
          value={kpi?.highest_risk_district ?? '—'}
          sub={kpi ? `Основная причина: ${translateCause(kpi.top_cause)}` : undefined}
          icon={<ShieldAlert size={18} />}
          loading={loading}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <RiskMap key={`map-${cityId}`} />
        </div>
        <IncidentsByDistrict key={`districts-${cityId}`} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <InspectionPlanPanel key={`inspection-plan-${cityId}`} cityId={cityId} />
        <ResponseTimeChart key={`operations-${cityId}`} cityId={cityId} />
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { city } = useCity()

  if (!city) {
    return <div className="h-32 rounded-xl bg-gray-900 border border-gray-800 animate-pulse" />
  }

  return <DashboardContent key={city.id} cityId={city.id} />
}

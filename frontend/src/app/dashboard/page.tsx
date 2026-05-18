'use client'

import dynamic from 'next/dynamic'
import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Flame, TrendingDown, TrendingUp, ShieldAlert, ArrowRight, Cpu } from 'lucide-react'
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

function today(): string {
  return new Date().toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function Hero({ cityName }: { cityName: string }) {
  const dateLabel = useMemo(() => today(), [])
  return (
    <section className="relative overflow-hidden rounded-[28px] border border-white/8 bg-[linear-gradient(135deg,rgba(249,115,22,0.08)_0%,rgba(17,27,46,0.95)_55%,rgba(10,17,30,0.92)_100%)] p-6 sm:p-8">
      <div className="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-orange-500/10 blur-3xl" />
      <div className="relative flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-orange-300/80 text-xs uppercase tracking-[0.18em]">FireWatch · {dateLabel}</p>
          <h1 className="text-white text-2xl sm:text-3xl font-semibold mt-2">
            Сводка пожарной обстановки — {cityName}
          </h1>
          <p className="text-gray-400 text-sm mt-2 max-w-xl">
            Риски, инциденты и инспекции с начала года. Источник — единая база ДЧС с подключёнными
            ML- и ИИ-моделями.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Link
            href="/dashboard/map"
            className="text-xs px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-white hover:bg-white/10 transition-colors flex items-center gap-1"
          >
            Открыть карту риска <ArrowRight size={12} />
          </Link>
          <Link
            href="/dashboard/inspector"
            className="text-xs px-3 py-1.5 rounded-full border border-orange-400/30 bg-orange-500/15 text-orange-200 hover:bg-orange-500/25 transition-colors flex items-center gap-1"
          >
            План на сегодня <ArrowRight size={12} />
          </Link>
        </div>
      </div>
    </section>
  )
}

function ModelStripe() {
  return (
    <div className="rounded-2xl border border-white/8 bg-gray-900/50 px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-gray-400">
      <span className="flex items-center gap-2 text-gray-300">
        <Cpu size={13} className="text-purple-300" />
        ML-модель: <span className="text-white">XGBoost (Poisson)</span>
      </span>
      <span>SHAP-объяснения · 9 базовых признаков</span>
      <span>ИИ для документов и аналитика: <span className="text-white">Claude Haiku 4.5</span></span>
      <span>Обновление риска: <span className="text-white">ежедневно</span></span>
    </div>
  )
}

function DashboardContent({ cityId, cityName }: { cityId: string; cityName: string }) {
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
      <Hero cityName={cityName} />

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

      <ModelStripe />

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

  return <DashboardContent key={city.id} cityId={city.id} cityName={city.name} />
}

'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { ArrowLeft, Building2, Layers, Calendar, AlertTriangle, FileText } from 'lucide-react'
import { api } from '@/lib/api'
import type { BuildingDetail, RiskBreakdown, RiskExplanation, Incident } from '@/lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OBJECT_TYPE_RU: Record<string, string> = {
  residential: 'Жилой',
  commercial: 'Коммерческий',
  industrial: 'Промышленный',
  construction: 'Стройплощадка',
  other: 'Прочее',
}

const SEVERITY_RU: Record<string, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
  critical: 'Критический',
}

const SEVERITY_COLORS: Record<string, string> = {
  low: 'text-green-400',
  medium: 'text-yellow-400',
  high: 'text-orange-400',
  critical: 'text-red-400',
}

function riskColor(score: number): string {
  if (score < 0.5) return 'text-green-400'
  if (score <= 1.5) return 'text-yellow-400'
  return 'text-red-400'
}

function riskBgColor(score: number): string {
  if (score < 0.5) return 'bg-green-400/10 border-green-500/30'
  if (score <= 1.5) return 'bg-yellow-400/10 border-yellow-500/30'
  return 'bg-red-400/10 border-red-500/30'
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function featureLabel(feature: string): string {
  const labels: Record<string, string> = {
    floors_count: 'Этажей',
    total_area: 'Площадь (м²)',
    fire_resistance_degree: 'Огнестойкость',
    distance_to_fire_department: 'Расстояние до ПЧ (км)',
    arrival_time_minutes: 'Время прибытия (мин)',
    building_age: 'Возраст здания',
    construction_type: 'Тип конструкции',
    object_type: 'Тип объекта',
    days_since_last_incident: 'Дней с последнего инцидента',
    incident_count_1y: 'Инцидентов за год',
  }
  return labels[feature] ?? feature
}

// ---------------------------------------------------------------------------
// Skeleton loaders
// ---------------------------------------------------------------------------

function SkeletonHeader() {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 animate-pulse">
      <div className="h-6 w-64 bg-gray-700 rounded mb-3" />
      <div className="h-4 w-48 bg-gray-700 rounded mb-6" />
      <div className="flex gap-3 flex-wrap">
        <div className="h-8 w-28 bg-gray-700 rounded-full" />
        <div className="h-8 w-24 bg-gray-700 rounded-full" />
        <div className="h-8 w-20 bg-gray-700 rounded-full" />
      </div>
    </div>
  )
}

function SkeletonCard({ rows = 4 }: { rows?: number }) {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 animate-pulse">
      <div className="h-4 w-36 bg-gray-700 rounded mb-4" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 bg-gray-700 rounded mb-3" />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Incident history table
// ---------------------------------------------------------------------------

function IncidentTable({ incidents, loading }: { incidents: Incident[]; loading: boolean }) {
  if (loading) return <SkeletonCard rows={5} />

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-white font-semibold text-sm uppercase tracking-wide mb-4">
        История инцидентов
      </h2>
      {incidents.length === 0 ? (
        <p className="text-gray-500 text-sm">Инциденты не найдены</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wide border-b border-gray-700">
                <th className="text-left pb-2 pr-4">Дата</th>
                <th className="text-left pb-2 pr-4">Тип</th>
                <th className="text-left pb-2 pr-4">Причина</th>
                <th className="text-left pb-2">Тяжесть</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id} className="border-b border-gray-700/50 last:border-0">
                  <td className="py-2.5 pr-4 text-gray-400 whitespace-nowrap">
                    {formatDate(inc.date)}
                  </td>
                  <td className="py-2.5 pr-4 text-gray-300">
                    {inc.building_type}
                  </td>
                  <td className="py-2.5 pr-4 text-gray-300">
                    {inc.cause}
                  </td>
                  <td className="py-2.5">
                    <span className={`text-xs font-medium ${SEVERITY_COLORS[inc.severity] ?? 'text-gray-400'}`}>
                      {SEVERITY_RU[inc.severity] ?? inc.severity}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// SHAP bar chart
// ---------------------------------------------------------------------------

interface ShapChartProps {
  factors: RiskExplanation['shap_factors']
  explanation: string
}

function ShapChart({ factors, explanation }: ShapChartProps) {
  const data = factors
    .slice()
    .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
    .slice(0, 8)
    .map((f) => ({
      name: featureLabel(f.feature),
      value: Number(f.shap_value.toFixed(3)),
    }))

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 flex flex-col gap-4">
      <h2 className="text-white font-semibold text-sm uppercase tracking-wide">
        Ключевые факторы риска
      </h2>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
        >
          <XAxis
            type="number"
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            axisLine={{ stroke: '#374151' }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={160}
            tick={{ fill: '#d1d5db', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: '#1f2937',
              border: '1px solid #374151',
              borderRadius: 8,
              color: '#f9fafb',
              fontSize: 12,
            }}
            formatter={(value) => {
              const v = typeof value === 'number' ? value.toFixed(3) : String(value ?? '')
              return [v, 'SHAP'] as [string, string]
            }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.value >= 0 ? '#f97316' : '#60a5fa'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {explanation && (
        <p className="text-gray-400 text-sm italic leading-relaxed">
          {explanation}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Risk breakdown panel
// ---------------------------------------------------------------------------

function RiskBreakdownPanel({ risk, loading }: { risk: RiskBreakdown | null; loading: boolean }) {
  if (loading) return <SkeletonCard rows={4} />

  if (!risk) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-white font-semibold text-sm uppercase tracking-wide mb-4">
          Оценка риска (30 дней)
        </h2>
        <p className="text-gray-500 text-sm">Данные недоступны</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-white font-semibold text-sm uppercase tracking-wide mb-5">
        Оценка риска (30 дней)
      </h2>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-gray-400 text-sm">Базовый балл</span>
          <span className="text-gray-200 font-medium tabular-nums">
            {risk.baseline_score.toFixed(2)}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-400 text-sm">Динамический модификатор</span>
          <span className="text-gray-200 font-medium tabular-nums">
            ×{risk.dynamic_modifier.toFixed(2)}
          </span>
        </div>

        <div className="h-px bg-gray-700" />

        <div className="flex items-center justify-between">
          <span className="text-gray-300 text-sm font-medium">Итоговый балл</span>
          <span className={`text-lg font-bold tabular-nums ${riskColor(risk.final_score)}`}>
            {risk.final_score.toFixed(2)}
          </span>
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="text-gray-400 text-sm">Ожидаемых инцидентов</span>
          <span className="text-gray-200 font-medium tabular-nums">
            {risk.expected_incidents.toFixed(1)}
          </span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function BuildingDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = Array.isArray(params.id) ? params.id[0] : (params.id ?? '')

  const [building, setBuilding] = useState<BuildingDetail | null>(null)
  const [risk, setRisk] = useState<RiskBreakdown | null>(null)
  const [factors, setFactors] = useState<RiskExplanation | null>(null)
  const [incidents, setIncidents] = useState<Incident[]>([])

  const [loadingBuilding, setLoadingBuilding] = useState(true)
  const [loadingRisk, setLoadingRisk] = useState(true)
  const [loadingFactors, setLoadingFactors] = useState(true)
  const [loadingIncidents, setLoadingIncidents] = useState(true)

  const [notFound, setNotFound] = useState(false)
  const [errorBuilding, setErrorBuilding] = useState(false)

  useEffect(() => {
    if (!id) return

    // Building detail
    setLoadingBuilding(true)
    api.buildings
      .getDetail(id)
      .then(setBuilding)
      .catch((err: Error) => {
        if (err.message.includes('404')) {
          setNotFound(true)
        } else {
          setErrorBuilding(true)
        }
      })
      .finally(() => setLoadingBuilding(false))

    // Risk breakdown
    setLoadingRisk(true)
    api.buildings
      .getRisk(id, 30)
      .then(setRisk)
      .catch(() => {
        // non-fatal: risk panel shows "unavailable"
      })
      .finally(() => setLoadingRisk(false))

    // SHAP factors
    setLoadingFactors(true)
    api.buildings
      .getFactors(id)
      .then(setFactors)
      .catch(() => {
        // non-fatal
      })
      .finally(() => setLoadingFactors(false))
  }, [id])

  // Fetch incidents once we have the building's city
  useEffect(() => {
    if (!building) return
    const city = building.city ?? 'astana'
    setLoadingIncidents(true)
    api.buildings
      .getIncidents(city, id, 10)
      .then((res) => setIncidents(res.items))
      .catch(() => {
        setIncidents([])
      })
      .finally(() => setLoadingIncidents(false))
  }, [building, id])

  // ---------------------------------------------------------------------------
  // Not found
  // ---------------------------------------------------------------------------

  if (!loadingBuilding && (notFound || errorBuilding)) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            onClick={() => router.push('/dashboard/buildings')}
            className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft size={16} />
            Здания
          </button>
        </div>
        <div className="text-center py-20 text-gray-500">
          <Building2 size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-lg text-white">
            {notFound ? 'Здание не найдено' : 'Ошибка загрузки данных'}
          </p>
          <button
            type="button"
            onClick={() => router.push('/dashboard/buildings')}
            className="mt-4 px-4 py-2 rounded-lg bg-gray-800 text-gray-300 hover:text-white text-sm transition-colors"
          >
            Вернуться к списку
          </button>
        </div>
      </div>
    )
  }

  const finalScore = risk?.final_score ?? building?.risk_score ?? null

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Back navigation */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push('/dashboard/buildings')}
          className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors text-sm"
        >
          <ArrowLeft size={16} />
          Здания
        </button>
        {!loadingBuilding && building && (
          <span className="text-gray-600">/</span>
        )}
        {!loadingBuilding && building && (
          <span className="text-gray-300 text-sm truncate">{building.address ?? building.name}</span>
        )}
      </div>

      {/* Header card */}
      {loadingBuilding ? (
        <SkeletonHeader />
      ) : building ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            {/* Left: building info */}
            <div className="flex-1 min-w-0">
              <h1 className="text-white text-xl font-bold leading-snug mb-1">
                {building.address ?? building.name}
              </h1>
              {building.name !== (building.address ?? '') && (
                <p className="text-gray-400 text-sm mb-3">{building.name}</p>
              )}

              <div className="flex flex-wrap gap-2 mt-3">
                {building.object_type && (
                  <span className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-gray-700 text-gray-200">
                    <Building2 size={11} />
                    {OBJECT_TYPE_RU[building.object_type] ?? building.object_type}
                  </span>
                )}
                {building.floors_count != null && (
                  <span className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-gray-700 text-gray-200">
                    <Layers size={11} />
                    {building.floors_count} эт.
                  </span>
                )}
                {building.district && (
                  <span className="text-xs px-3 py-1.5 rounded-full bg-gray-700 text-gray-200">
                    {building.district}
                  </span>
                )}
                {building.fire_resistance_degree && (
                  <span className="text-xs px-3 py-1.5 rounded-full bg-gray-700 text-gray-200">
                    {building.fire_resistance_degree}
                  </span>
                )}
                {building.construction_type && (
                  <span className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-gray-700 text-gray-200">
                    <Calendar size={11} />
                    {building.construction_type}
                  </span>
                )}
              </div>
            </div>

            {/* Right: risk score badge */}
            {finalScore != null && (
              <div
                className={`shrink-0 flex flex-col items-center justify-center px-6 py-4 rounded-xl border ${riskBgColor(finalScore)}`}
              >
                <span className="text-gray-400 text-xs uppercase tracking-wide mb-1">
                  Риск
                </span>
                <span className={`text-4xl font-bold tabular-nums ${riskColor(finalScore)}`}>
                  {finalScore.toFixed(2)}
                </span>
                <span className="text-gray-500 text-xs mt-1">итоговый балл</span>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* Middle row: risk breakdown + SHAP factors */}
      <div className="grid md:grid-cols-2 gap-5">
        <RiskBreakdownPanel risk={risk} loading={loadingRisk} />

        {loadingFactors ? (
          <SkeletonCard rows={6} />
        ) : factors && factors.shap_factors.length > 0 ? (
          <ShapChart factors={factors.shap_factors} explanation={factors.explanation} />
        ) : (
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 flex items-center justify-center text-gray-500 text-sm">
            <div className="text-center">
              <AlertTriangle size={32} className="mx-auto mb-2 opacity-30" />
              <p>Факторы риска недоступны</p>
            </div>
          </div>
        )}
      </div>

      {/* Incident history */}
      <IncidentTable incidents={incidents} loading={loadingIncidents} />

      {/* Operational card link */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <FileText size={18} className="text-blue-400" />
            </div>
            <div>
              <p className="text-white text-sm font-medium">Оперативные документы</p>
              <p className="text-gray-400 text-xs mt-0.5">
                Планы эвакуации, карточки тушения и другие документы по объекту
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => router.push(`/dashboard/documents?building_id=${id}`)}
            className="shrink-0 px-4 py-2 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors text-sm font-medium"
          >
            Открыть
          </button>
        </div>
      </div>
    </div>
  )
}

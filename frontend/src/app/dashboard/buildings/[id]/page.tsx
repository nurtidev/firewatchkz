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
import { ArrowLeft, Building2, Layers, Calendar, AlertTriangle, FileText, Cpu, Info } from 'lucide-react'
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

const FEATURE_LABELS: Record<string, string> = {
  nearest_hydrant_m: 'Расстояние до ближайшего гидранта',
  nearest_station_m: 'Расстояние до пожарной части',
  incidents_500m_3y: 'Пожары в радиусе 500 м (3 года)',
  incidents_on_building_3y: 'Пожары на объекте (3 года)',
  building_density_500m: 'Плотность застройки в радиусе 500 м',
  age_years: 'Возраст здания',
  population_estimate: 'Оценочная численность жителей',
  days_since_last_incident: 'Дней с последнего пожара',
  days_since_last_inspection: 'Дней с последней проверки',
  building_type: 'Тип объекта',
}

const FEATURE_UNITS: Record<string, string> = {
  nearest_hydrant_m: 'м',
  nearest_station_m: 'м',
  age_years: 'лет',
  days_since_last_incident: 'дн.',
  days_since_last_inspection: 'дн.',
}

function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature
}

function formatFeatureValue(feature: string, value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const unit = FEATURE_UNITS[feature]
  if (typeof value === 'number') {
    const rounded = Number.isInteger(value) ? value.toString() : value.toFixed(1)
    return unit ? `${rounded} ${unit}` : rounded
  }
  return String(value)
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
  const sorted = factors
    .slice()
    .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
    .slice(0, 8)

  const data = sorted.map((f) => ({
    name: featureLabel(f.feature),
    feature: f.feature,
    rawValue: f.value,
    value: Number(f.shap_value.toFixed(3)),
  }))

  const increased = sorted.filter((f) => f.shap_value > 0).length
  const decreased = sorted.filter((f) => f.shap_value < 0).length

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-white font-semibold text-sm uppercase tracking-wide">
            Ключевые факторы риска
          </h2>
          <p className="text-gray-500 text-xs mt-1">
            ML-модель XGBoost · SHAP-разложение по топ-{sorted.length} признакам
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <span className="text-[11px] px-2 py-1 rounded-md bg-orange-500/10 text-orange-300">
            ↑ повышают: {increased}
          </span>
          <span className="text-[11px] px-2 py-1 rounded-md bg-blue-500/10 text-blue-300">
            ↓ снижают: {decreased}
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 28, left: 0, bottom: 0 }}
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
            width={180}
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
            formatter={(value, _name, entry) => {
              const v = typeof value === 'number' ? value.toFixed(3) : String(value ?? '')
              const datum = (entry?.payload ?? {}) as { feature?: string; rawValue?: number | string | null }
              const sign = typeof value === 'number' && value >= 0 ? 'повышает риск' : 'снижает риск'
              const featureValue = datum.feature
                ? formatFeatureValue(datum.feature, datum.rawValue ?? null)
                : ''
              return [
                `${v} (${sign})${featureValue ? ` · значение: ${featureValue}` : ''}`,
                'SHAP',
              ] as [string, string]
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
        <div className="rounded-lg border border-gray-700 bg-gray-900/40 p-3 flex gap-2 text-sm">
          <Info size={14} className="text-orange-400 mt-0.5 shrink-0" />
          <p className="text-gray-300 leading-relaxed">{explanation}</p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ML Model Card — explains where the risk score comes from
// ---------------------------------------------------------------------------

function ModelCard() {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 bg-purple-500/10 rounded-lg shrink-0">
          <Cpu size={18} className="text-purple-300" />
        </div>
        <div>
          <h2 className="text-white font-semibold text-sm uppercase tracking-wide">
            Модель оценки риска
          </h2>
          <p className="text-gray-500 text-xs mt-0.5">
            Откуда берётся итоговый балл этого здания
          </p>
        </div>
      </div>
      <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-gray-400">Алгоритм</dt>
          <dd className="text-gray-200 text-right">XGBoost (Poisson)</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-gray-400">Тип задачи</dt>
          <dd className="text-gray-200 text-right">Регрессия частоты пожаров</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-gray-400">Признаков</dt>
          <dd className="text-gray-200 text-right">{Object.keys(FEATURE_LABELS).length} базовых</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-gray-400">Объяснимость</dt>
          <dd className="text-gray-200 text-right">SHAP (per-feature contributions)</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-gray-400">Корректировка</dt>
          <dd className="text-gray-200 text-right">Динамический модификатор (погода, сезонность)</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-gray-400">Горизонт прогноза</dt>
          <dd className="text-gray-200 text-right">30 дней (можно 7 / 90)</dd>
        </div>
      </dl>
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

      {/* Model card — what produced this risk score */}
      <ModelCard />

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

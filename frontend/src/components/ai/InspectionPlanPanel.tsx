'use client'

import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, ShieldAlert } from 'lucide-react'
import { clsx } from 'clsx'
import { useCity } from '@/context/CityContext'

type InspectionPriority = 'high' | 'medium' | 'low'

interface InspectionPlanItem {
  district: string
  priority: InspectionPriority
  reason: string
  recommended_actions: string[]
}

interface InspectionPlanResponse {
  city: string
  generated_at: string
  items: InspectionPlanItem[]
}

interface InspectionPlanPanelProps {
  cityId?: string
  className?: string
  title?: string
}

const PRIORITY_META: Record<
  InspectionPriority,
  { label: string; icon: typeof AlertTriangle; className: string; order: number }
> = {
  high: {
    label: 'Высокий',
    icon: AlertTriangle,
    className: 'text-red-400 bg-red-400/10 border-red-400/20',
    order: 0,
  },
  medium: {
    label: 'Средний',
    icon: ShieldAlert,
    className: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    order: 1,
  },
  low: {
    label: 'Низкий',
    icon: CheckCircle2,
    className: 'text-green-400 bg-green-400/10 border-green-400/20',
    order: 2,
  },
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

async function fetchInspectionPlan(cityId: string, signal?: AbortSignal): Promise<InspectionPlanResponse> {
  const response = await fetch(`${API_BASE}/api/v2/inspection-plan?city=${encodeURIComponent(cityId)}`, {
    signal,
  })
  if (!response.ok) throw new Error(`Inspection plan request failed: ${response.status}`)
  return response.json() as Promise<InspectionPlanResponse>
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'обновлено недавно'
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function PlanSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(3)].map((_, index) => (
        <div key={index} className="rounded-xl border border-gray-800 bg-gray-800/40 p-4 space-y-3 animate-pulse">
          <div className="flex items-center justify-between gap-3">
            <div className="h-4 w-40 rounded bg-gray-700" />
            <div className="h-6 w-20 rounded-full bg-gray-700" />
          </div>
          <div className="h-3 w-full rounded bg-gray-700" />
          <div className="space-y-2">
            <div className="h-3 w-5/6 rounded bg-gray-700" />
            <div className="h-3 w-2/3 rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  )
}

function EmptyState({ loading }: { loading: boolean }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-800 bg-gray-950/40 p-5 text-sm text-gray-500">
      {loading ? 'Загружаем план проверок...' : 'План проверок пока недоступен для выбранного города.'}
    </div>
  )
}

export function InspectionPlanPanel({ cityId, className, title = 'План проверок' }: InspectionPlanPanelProps) {
  const { city } = useCity()
  const activeCityId = cityId ?? city?.id
  const [payload, setPayload] = useState<InspectionPlanResponse | null>(null)
  const [loading, setLoading] = useState(Boolean(activeCityId))
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!activeCityId) return

    const controller = new AbortController()

    async function runLoad() {
      setLoading(true)
      setError(false)

      try {
        const data = await fetchInspectionPlan(activeCityId!, controller.signal)
        setPayload(data)
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setPayload(null)
        setError(true)
      } finally {
        setLoading(false)
      }
    }

    runLoad()

    return () => controller.abort()
  }, [activeCityId])

  const groupedItems = useMemo(() => {
    const items = payload?.items ?? []
    return [...items].sort((a, b) => PRIORITY_META[a.priority].order - PRIORITY_META[b.priority].order)
  }, [payload])

  const groupedCounts = useMemo(() => {
    return groupedItems.reduce(
      (acc, item) => {
        acc[item.priority] += 1
        return acc
      },
      { high: 0, medium: 0, low: 0 } as Record<InspectionPriority, number>
    )
  }, [groupedItems])

  const sections: InspectionPriority[] = ['high', 'medium', 'low']

  return (
    <div className={clsx('rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] p-5 flex flex-col gap-4 shadow-[0_24px_60px_rgba(0,0,0,0.22)]', className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Clock3 size={16} className="text-orange-400" />
            <h2 className="text-white font-semibold">{title}</h2>
          </div>
          <p className="text-xs text-gray-500">
            {payload?.generated_at ? `Обновлено ${formatUpdatedAt(payload.generated_at)}` : 'Основано на текущих KPI и рисках районов'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            if (!activeCityId) return
            setLoading(true)
            setError(false)
            fetchInspectionPlan(activeCityId)
              .then((data) => setPayload(data))
              .catch(() => setError(true))
              .finally(() => setLoading(false))
          }}
          disabled={loading || !activeCityId}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Обновить
        </button>
      </div>

      {loading ? (
        <PlanSkeleton />
      ) : error ? (
        <div className="rounded-xl border border-dashed border-red-500/30 bg-red-500/5 p-4 text-sm text-red-300">
          Не удалось загрузить план проверок.
        </div>
      ) : !groupedItems.length ? (
        <EmptyState loading={loading} />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {sections.map((priority) => {
              const meta = PRIORITY_META[priority]
              const Icon = meta.icon
              return (
                <div key={priority} className={clsx('rounded-xl border px-3 py-2', meta.className)}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 text-xs font-medium">
                      <Icon size={12} />
                      {meta.label}
                    </div>
                    <div className="text-sm font-semibold">{groupedCounts[priority]}</div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="space-y-3">
            {sections.map((priority) => {
              const meta = PRIORITY_META[priority]
              const Icon = meta.icon
              const items = groupedItems.filter((item) => item.priority === priority)

              if (!items.length) return null

              return (
                <section key={priority} className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Icon size={15} className={clsx(priority === 'high' ? 'text-red-400' : priority === 'medium' ? 'text-yellow-400' : 'text-green-400')} />
                    <h3 className="text-sm font-semibold text-white">{meta.label} приоритет</h3>
                    <span className="text-xs text-gray-500">{items.length}</span>
                  </div>

                  <div className="space-y-3">
                    {items.map((item) => (
                      <article key={`${priority}-${item.district}-${item.reason}`} className="rounded-xl border border-gray-800 bg-gray-950/40 p-4 space-y-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-white font-medium">{item.district}</div>
                            <div className="text-xs text-gray-500 mt-1">{item.reason}</div>
                          </div>
                          <span className={clsx('shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium', meta.className)}>
                            {meta.label}
                          </span>
                        </div>

                        <div className="space-y-2">
                          <div className="text-xs uppercase tracking-wide text-gray-500">Рекомендуемые действия</div>
                          <ul className="space-y-1.5">
                            {item.recommended_actions.map((action) => (
                              <li key={action} className="flex gap-2 text-sm text-gray-300">
                                <span className="mt-2 h-1.5 w-1.5 rounded-full bg-orange-400 shrink-0" />
                                <span>{action}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

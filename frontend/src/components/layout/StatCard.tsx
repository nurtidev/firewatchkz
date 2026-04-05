import { clsx } from 'clsx'
import type { ReactNode } from 'react'

interface StatCardProps {
  title: string
  value: string
  sub?: string
  subTrend?: 'up' | 'down' | 'neutral'
  icon?: ReactNode
  loading?: boolean
}

export function StatCard({ title, value, sub, subTrend = 'neutral', icon, loading }: StatCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-gray-400 text-sm">{title}</span>
        {icon && <span className="text-gray-600">{icon}</span>}
      </div>

      {loading ? (
        <div className="h-8 w-28 bg-gray-800 rounded animate-pulse" />
      ) : (
        <span className="text-white text-2xl font-bold tracking-tight">{value}</span>
      )}

      {sub && (
        <span
          className={clsx('text-xs', {
            'text-green-400': subTrend === 'down',
            'text-red-400': subTrend === 'up',
            'text-gray-500': subTrend === 'neutral',
          })}
        >
          {sub}
        </span>
      )}
    </div>
  )
}

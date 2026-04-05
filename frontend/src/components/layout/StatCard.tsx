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
    <div className="relative overflow-hidden rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] p-5 flex flex-col gap-3 shadow-[0_24px_60px_rgba(0,0,0,0.22)]">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
      <div className="absolute -right-10 -top-10 h-24 w-24 rounded-full bg-orange-500/8 blur-2xl" />
      <div className="flex items-center justify-between">
        <span className="text-gray-400 text-sm">{title}</span>
        {icon && <span className="flex h-9 w-9 items-center justify-center rounded-2xl border border-white/10 bg-white/4 text-gray-300">{icon}</span>}
      </div>

      {loading ? (
        <div className="h-8 w-28 bg-white/7 rounded animate-pulse" />
      ) : (
        <span className="text-white text-[30px] leading-none font-semibold tracking-tight">{value}</span>
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

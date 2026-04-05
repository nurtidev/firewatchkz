'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Map, TrendingUp, Lightbulb, MessageSquare, Bell, ClipboardCheck } from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { href: '/dashboard', label: 'Обзор', icon: LayoutDashboard },
  { href: '/dashboard/inspector', label: 'Инспектор', icon: ClipboardCheck, highlight: true },
  { href: '/dashboard/map', label: 'Карта рисков', icon: Map },
  { href: '/dashboard/forecast', label: 'Прогноз', icon: TrendingUp },
  { href: '/dashboard/recommendations', label: 'Рекомендации', icon: Lightbulb },
  { href: '/dashboard/chat', label: 'AI Аналитик', icon: MessageSquare },
  { href: '/dashboard/alerts', label: 'Уведомления', icon: Bell },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV.map(({ href, label, icon: Icon, highlight }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
              pathname === href
                ? 'bg-orange-500/10 text-orange-400 font-medium'
                : highlight
                  ? 'text-orange-300 hover:bg-orange-500/10 hover:text-orange-400'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}

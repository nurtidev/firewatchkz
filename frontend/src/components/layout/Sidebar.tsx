'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Map, MessageSquare, Bell, ClipboardCheck, Building2, Droplets, Navigation, FileText } from 'lucide-react'
import { clsx } from 'clsx'
import { useAuth } from '@/context/AuthContext'

const NAV = [
  { href: '/dashboard', label: 'Обзор', icon: LayoutDashboard },
  { href: '/dashboard/inspector', label: 'План инспекций', icon: ClipboardCheck, highlight: true },
  { href: '/dashboard/routing', label: 'Маршрутизация', icon: Navigation, highlight: true },
  { href: '/dashboard/map', label: 'Карта рисков', icon: Map },
  { href: '/dashboard/buildings', label: 'Здания / Планы', icon: Building2 },
  { href: '/dashboard/documents', label: 'Документы', icon: FileText },
  { href: '/dashboard/hydrants', label: 'Гидранты', icon: Droplets },
  { href: '/dashboard/chat', label: 'AI Аналитик', icon: MessageSquare },
  { href: '/dashboard/alerts', label: 'Уведомления', icon: Bell, adminOnly: true },
]

export function Sidebar() {
  const pathname = usePathname()
  const { isAdmin } = useAuth()

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV.filter((item) => !item.adminOnly || isAdmin).map(({ href, label, icon: Icon, highlight }) => (
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

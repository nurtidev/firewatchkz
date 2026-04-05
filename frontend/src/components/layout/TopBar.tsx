'use client'

import { Flame } from 'lucide-react'
import { useCity } from '@/context/CityContext'

export function TopBar() {
  const { city, cities, setCity } = useCity()

  return (
    <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-2">
        <Flame className="text-orange-500" size={22} />
        <span className="font-semibold text-white text-lg tracking-tight">FireWatch</span>
      </div>

      <div className="flex items-center gap-3">
        <label className="text-gray-400 text-sm">Город:</label>
        <select
          className="bg-gray-800 text-white text-sm border border-gray-700 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-orange-500"
          value={city?.id ?? ''}
          onChange={(e) => {
            const selected = cities.find((c) => c.id === e.target.value)
            if (selected) setCity(selected)
          }}
        >
          {cities.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        <span className="text-gray-500 text-xs hidden sm:block">
          Обновлено: {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </header>
  )
}

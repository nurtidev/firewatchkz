'use client'

import { ForecastChart } from '@/components/charts/ForecastChart'
import { useCity } from '@/context/CityContext'

export default function ForecastPage() {
  const { city } = useCity()

  return (
    <div className="space-y-4">
      <h1 className="text-white font-semibold text-lg">Прогноз</h1>
      {city ? <ForecastChart key={city.id} /> : <div className="h-64 rounded-xl bg-gray-900 border border-gray-800 animate-pulse" />}
    </div>
  )
}

'use client'

import { RecommendationsPanel } from '@/components/ai/RecommendationCard'
import { useCity } from '@/context/CityContext'

export default function RecommendationsPage() {
  const { city } = useCity()

  return (
    <div className="space-y-4">
      <h1 className="text-white font-semibold text-lg">AI Рекомендации</h1>
      {city ? <RecommendationsPanel key={city.id} /> : <div className="h-80 rounded-xl bg-gray-900 border border-gray-800 animate-pulse" />}
    </div>
  )
}

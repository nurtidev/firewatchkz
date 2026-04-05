'use client'

import dynamic from 'next/dynamic'
import { useCity } from '@/context/CityContext'

const RiskMap = dynamic(
  () => import('@/components/map/RiskMap').then((m) => m.RiskMap),
  {
    ssr: false,
    loading: () => <div className="h-[420px] rounded-xl bg-gray-900 border border-gray-800 animate-pulse" />,
  }
)

export default function MapPage() {
  const { city } = useCity()

  return (
    <div className="space-y-4">
      <h1 className="text-white font-semibold text-lg">Карта рисков</h1>
      {city ? <RiskMap key={city.id} /> : <div className="h-[420px] rounded-xl bg-gray-900 border border-gray-800 animate-pulse" />}
    </div>
  )
}

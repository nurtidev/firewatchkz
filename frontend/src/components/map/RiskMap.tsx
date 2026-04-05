'use client'

import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { DistrictRisk } from '@/lib/types'
import 'leaflet/dist/leaflet.css'

function riskColor(score: number): string {
  if (score >= 67) return '#ef4444'
  if (score >= 34) return '#eab308'
  return '#22c55e'
}

const DISTRICT_CENTROIDS: Record<string, [number, number]> = {
  'Есіл': [51.185, 71.475],
  'Алматы': [51.21, 71.35],
  'Байқоңыр': [51.145, 71.4],
  'Сарыарқа': [51.235, 71.505],
  'Нұра': [51.12, 71.525],
}

export function RiskMap() {
  const { city } = useCity()
  const [districtData, setDistrictData] = useState<DistrictRisk[]>([])

  useEffect(() => {
    if (!city) return
    let cancelled = false

    api.riskMap.get(city.id).then((risks) => {
      if (!cancelled) setDistrictData(risks)
    }).catch(() => {
      if (!cancelled) setDistrictData([])
    })

    return () => {
      cancelled = true
    }
  }, [city])

  if (!city) return null

  return (
    <div className="relative bg-gray-900 border border-gray-800 rounded-xl overflow-hidden" style={{ height: 420 }}>
      <MapContainer
        center={city.center}
        zoom={city.zoom}
        style={{ height: '100%', width: '100%', background: '#111827' }}
        zoomControl={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />
        {districtData.map((risk) => {
          const center = DISTRICT_CENTROIDS[risk.district]
          if (!center) return null

          return (
            <CircleMarker
              key={risk.district}
              center={center}
              radius={10}
              pathOptions={{
                color: '#111827',
                weight: 2,
                fillColor: riskColor(risk.risk_score),
                fillOpacity: 0.85,
              }}
            >
              <Tooltip direction="top">
                <div className="text-sm">
                  <div className="font-semibold">{risk.district}</div>
                  <div>Риск: <b>{risk.risk_score}/100</b></div>
                  <div>Инцидентов: {risk.total_incidents}</div>
                  <div>Причина: {risk.top_cause}</div>
                </div>
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-8 right-4 bg-gray-900/90 border border-gray-700 rounded-lg p-3 text-xs space-y-1.5 z-[1000]">
        <div className="text-gray-400 font-medium mb-1">Уровень риска</div>
        {[
          { label: 'Высокий (67–100)', color: '#ef4444' },
          { label: 'Средний (34–66)', color: '#eab308' },
          { label: 'Низкий (0–33)', color: '#22c55e' },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: color }} />
            <span className="text-gray-300">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

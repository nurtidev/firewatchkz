'use client'

import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from 'react-leaflet'
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

type Station = {
  id: string
  city: string
  name: string
  district: string
  lat: number
  lon: number
  units: number
  staff_count: number
}

type Hydrant = {
  id: string
  city: string
  district: string
  address: string
  lat: number
  lon: number
  status: 'working' | 'maintenance' | 'out_of_service'
}

type LayerKey = 'districts' | 'stations' | 'hydrants'

const HYDRANT_STATUS_COLORS: Record<Hydrant['status'], string> = {
  working: '#3b82f6',
  maintenance: '#eab308',
  out_of_service: '#ef4444',
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}${path}`, { signal })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function RiskMap() {
  const { city } = useCity()
  const [districtData, setDistrictData] = useState<DistrictRisk[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [hydrants, setHydrants] = useState<Hydrant[]>([])
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    districts: true,
    stations: true,
    hydrants: false,
  })

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

  useEffect(() => {
    if (!city) return

    const controller = new AbortController()
    const loadMapLayers = async () => {
      try {
        const [stationData, hydrantData] = await Promise.all([
          fetchJson<Station[]>(`/api/v1/stations?city=${city.id}`, controller.signal),
          fetchJson<Hydrant[]>(`/api/v1/hydrants?city=${city.id}`, controller.signal),
        ])
        setStations(stationData)
        setHydrants(hydrantData)
      } catch {
        if (!controller.signal.aborted) {
          setStations([])
          setHydrants([])
        }
      }
    }

    loadMapLayers()

    return () => {
      controller.abort()
    }
  }, [city])

  if (!city) return null

  return (
    <div className="relative rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] overflow-hidden shadow-[0_24px_60px_rgba(0,0,0,0.22)]" style={{ height: 420 }}>
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
          {layers.districts && districtData.map((risk) => {
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
          {layers.stations && stations.map((station) => (
            <CircleMarker
              key={station.id}
              center={[station.lat, station.lon]}
              radius={7}
              pathOptions={{
                color: '#1d4ed8',
                weight: 2,
                fillColor: '#60a5fa',
                fillOpacity: 0.95,
              }}
            >
              <Popup>
                <div className="space-y-1 text-sm">
                  <div className="font-semibold text-gray-900">{station.name}</div>
                  <div className="text-gray-700">Район: {station.district}</div>
                  <div className="text-gray-700">Техники: {station.units}</div>
                  <div className="text-gray-700">Личный состав: {station.staff_count}</div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
          {layers.hydrants && hydrants.map((hydrant) => (
            <CircleMarker
              key={hydrant.id}
              center={[hydrant.lat, hydrant.lon]}
              radius={5}
              pathOptions={{
                color: HYDRANT_STATUS_COLORS[hydrant.status],
                weight: 2,
                fillColor: HYDRANT_STATUS_COLORS[hydrant.status],
                fillOpacity: 0.95,
              }}
            >
              <Popup>
                <div className="space-y-1 text-sm">
                  <div className="font-semibold text-gray-900">Гидрант</div>
                  <div className="text-gray-700">Адрес: {hydrant.address}</div>
                  <div className="text-gray-700">Район: {hydrant.district}</div>
                  <div className="text-gray-700">Статус: {hydrant.status}</div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

      <div className="absolute top-4 left-4 z-[1000] flex flex-wrap gap-2">
        {([
          ['districts', 'Районы'],
          ['stations', 'Пожарные части'],
          ['hydrants', 'Гидранты'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setLayers((current) => ({ ...current, [key]: !current[key] }))}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition shadow-sm ${
              layers[key]
                ? 'border-orange-400/30 bg-orange-500/18 text-orange-100 backdrop-blur'
                : 'border-white/10 bg-slate-950/72 text-gray-300 backdrop-blur hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div className="absolute bottom-8 right-4 bg-slate-950/78 border border-white/10 rounded-2xl p-3 text-xs space-y-2 z-[1000] backdrop-blur">
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
        <div className="pt-1 border-t border-gray-700/80">
          <div className="text-gray-400 font-medium mb-1">Слои</div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full inline-block bg-blue-400" />
            <span className="text-gray-300">Пожарные части</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: HYDRANT_STATUS_COLORS.working }} />
            <span className="text-gray-300">Гидранты</span>
          </div>
        </div>
      </div>
    </div>
  )
}

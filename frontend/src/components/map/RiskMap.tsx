'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { useRouter } from 'next/navigation'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { BuildingRiskItem, DistrictRisk } from '@/lib/types'
import 'leaflet/dist/leaflet.css'

function riskColor(score: number): string {
  if (score >= 67) return '#ef4444'
  if (score >= 34) return '#eab308'
  return '#22c55e'
}

function buildingRiskColor(score: number): string {
  if (score > 1.5) return '#ef4444'
  if (score > 0.5) return '#eab308'
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

type LayerKey = 'districts' | 'stations' | 'hydrants' | 'buildings'

const HYDRANT_STATUS_COLORS: Record<Hydrant['status'], string> = {
  working: '#3b82f6',
  maintenance: '#eab308',
  out_of_service: '#ef4444',
}

const BUILDING_TYPE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: '', label: 'Все типы' },
  { value: 'residential', label: 'Жилые' },
  { value: 'commercial', label: 'Коммерческие' },
  { value: 'industrial', label: 'Производственные' },
  { value: 'public', label: 'Общественные' },
]

const RISK_LEVEL_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: '', label: 'Все уровни' },
  { value: 'high', label: 'Высокий' },
  { value: 'medium', label: 'Средний' },
  { value: 'low', label: 'Низкий' },
]

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}${path}`, { signal })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

// Стабильный токен фильтров — чтобы хук пересоздавал fetch только на реальные изменения,
// а не на каждом ререндере (объект-литерал считается новой ссылкой).
function BuildingsLayer({
  city,
  enabled,
  buildingType,
  riskLevel,
  onCount,
}: {
  city: string
  enabled: boolean
  buildingType: string
  riskLevel: string
  onCount?: (n: number) => void
}) {
  const [buildings, setBuildings] = useState<BuildingRiskItem[]>([])
  const map = useMap()
  const router = useRouter()

  const fetchBuildings = useCallback(
    (signal: AbortSignal) => {
      if (!enabled) {
        setBuildings([])
        onCount?.(0)
        return
      }
      const bounds = map.getBounds()
      const bbox = `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`
      const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
      const params = new URLSearchParams({ city, bbox, limit: '500' })
      if (buildingType) params.set('building_type', buildingType)
      if (riskLevel) params.set('risk_level', riskLevel)
      fetch(`${BASE_URL}/api/v2/buildings?${params.toString()}`, { signal })
        .then((res) => {
          if (res.status === 401 || res.status === 403) return []
          if (!res.ok) throw new Error(`Buildings API error ${res.status}`)
          return res.json() as Promise<BuildingRiskItem[]>
        })
        .then((data) => {
          if (!signal.aborted) {
            setBuildings(data)
            onCount?.(data.length)
          }
        })
        .catch(() => {
          if (!signal.aborted) {
            setBuildings([])
            onCount?.(0)
          }
        })
    },
    [enabled, city, map, buildingType, riskLevel, onCount]
  )

  useEffect(() => {
    const controller = new AbortController()
    fetchBuildings(controller.signal)
    return () => {
      controller.abort()
    }
  }, [fetchBuildings])

  useMapEvents({
    moveend: () => {
      const controller = new AbortController()
      fetchBuildings(controller.signal)
    },
  })

  return (
    <>
      {buildings.map((building) => {
        if (building.lat == null || building.lon == null) return null
        return (
          <CircleMarker
            key={building.building_id}
            center={[building.lat, building.lon]}
            radius={4}
            pathOptions={{
              color: 'transparent',
              weight: 0,
              fillColor: buildingRiskColor(building.final_score),
              fillOpacity: 0.7,
            }}
            eventHandlers={{
              click: () => {
                router.push(`/dashboard/buildings/${building.building_id}`)
              },
            }}
          >
            <Popup>
              <div className="space-y-1 text-sm">
                <div className="font-semibold text-gray-900">{building.address || 'Адрес не указан'}</div>
                <div className="text-gray-700">
                  Риск: <b>{building.final_score.toFixed(2)}</b>
                </div>
                {building.building_type && (
                  <div className="text-gray-700">Тип: {building.building_type}</div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}

export interface RiskMapProps {
  /** Высота карты в пикселях. По умолчанию 420 — для дашборда; на странице карты передавай больше. */
  height?: number | string
  /** Какие слои включать по умолчанию. */
  defaultLayers?: Partial<Record<LayerKey, boolean>>
  /** Показывать ли фильтры (тип здания / уровень риска). */
  showFilters?: boolean
  /** Колбэк со счётчиками для шапки страницы. */
  onCounts?: (counts: { buildingsVisible: number }) => void
}

export function RiskMap({
  height = 420,
  defaultLayers,
  showFilters = false,
  onCounts,
}: RiskMapProps = {}) {
  const { city } = useCity()
  const [districtData, setDistrictData] = useState<DistrictRisk[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [hydrants, setHydrants] = useState<Hydrant[]>([])
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    districts: true,
    stations: true,
    hydrants: false,
    buildings: true,
    ...defaultLayers,
  })
  const [buildingType, setBuildingType] = useState<string>('')
  const [riskLevel, setRiskLevel] = useState<string>('')

  const handleCount = useCallback(
    (n: number) => {
      onCounts?.({ buildingsVisible: n })
    },
    [onCounts]
  )

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
          fetchJson<Station[]>(`/api/v2/stations?city=${city.id}`, controller.signal),
          fetchJson<Hydrant[]>(`/api/v2/hydrants?city=${city.id}`, controller.signal),
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

  const containerStyle = useMemo(() => ({ height: typeof height === 'number' ? `${height}px` : height }), [height])

  if (!city) return null

  return (
    <div
      className="relative rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(17,27,46,0.95)_0%,rgba(10,17,30,0.92)_100%)] overflow-hidden shadow-[0_24px_60px_rgba(0,0,0,0.22)]"
      style={containerStyle}
    >
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
        <BuildingsLayer
          city={city.id}
          enabled={layers.buildings}
          buildingType={buildingType}
          riskLevel={riskLevel}
          onCount={handleCount}
        />
      </MapContainer>

      <div className="absolute top-4 left-4 z-[1000] flex flex-wrap gap-2 max-w-[calc(100%-2rem)]">
        {([
          ['districts', 'Районы'],
          ['stations', 'Пожарные части'],
          ['hydrants', 'Гидранты'],
          ['buildings', 'Здания (риск)'],
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

      {showFilters && layers.buildings && (
        <div className="absolute top-16 left-4 z-[1000] flex flex-wrap gap-2 max-w-[calc(100%-2rem)]">
          <select
            value={buildingType}
            onChange={(event) => setBuildingType(event.target.value)}
            className="rounded-full border border-white/10 bg-slate-950/72 text-gray-200 backdrop-blur px-3 py-1.5 text-xs font-medium focus:outline-none focus:border-orange-400/40"
          >
            {BUILDING_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-slate-950 text-gray-200">
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={riskLevel}
            onChange={(event) => setRiskLevel(event.target.value)}
            className="rounded-full border border-white/10 bg-slate-950/72 text-gray-200 backdrop-blur px-3 py-1.5 text-xs font-medium focus:outline-none focus:border-orange-400/40"
          >
            {RISK_LEVEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-slate-950 text-gray-200">
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="absolute bottom-8 right-4 bg-slate-950/78 border border-white/10 rounded-2xl p-3 text-xs space-y-2 z-[1000] backdrop-blur">
        <div className="text-gray-400 font-medium mb-1">Уровень риска</div>
        {[
          { label: 'Высокий', color: '#ef4444' },
          { label: 'Средний', color: '#eab308' },
          { label: 'Низкий', color: '#22c55e' },
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

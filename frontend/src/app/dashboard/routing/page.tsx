'use client'

import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { Navigation, Flame, Clock, Minus, AlertCircle, ChevronDown } from 'lucide-react'
import { api } from '@/lib/api'
import type { RouteEstimate, RoutingStation } from '@/lib/types'
import { useCity } from '@/context/CityContext'

const RouteMap = dynamic(() => import('@/components/map/RouteMap'), { ssr: false })

// Known Astana addresses with coords for demo
const DEMO_DESTINATIONS = [
  { label: 'ЖК Хайвилл-Астана', lat: 51.1345, lon: 71.4335 },
  { label: 'ЖК Аланда, пр. Независимости 33', lat: 51.1608, lon: 71.4664 },
  { label: 'ТРЦ Хан Шатыр', lat: 51.1282, lon: 71.4213 },
  { label: 'Площадь ЭКСПО', lat: 51.0900, lon: 71.3956 },
  { label: 'ЖК Triumph Astana', lat: 51.1734, lon: 71.4503 },
  { label: 'Байтерек', lat: 51.1283, lon: 71.4300 },
]

function TimeDiff({ normal, emergency }: { normal: number; emergency: number }) {
  const diff = normal - emergency
  return (
    <div className="flex items-center gap-1 text-green-400 text-sm font-medium">
      <Minus size={12} />
      {diff.toFixed(1)} мин
    </div>
  )
}

export default function RoutingPage() {
  const { city } = useCity()
  const cityId = city?.id ?? 'astana'

  const [stations, setStations] = useState<RoutingStation[]>([])
  const [selectedStation, setSelectedStation] = useState<RoutingStation | null>(null)
  const [selectedDest, setSelectedDest] = useState(DEMO_DESTINATIONS[0])
  const [result, setResult] = useState<RouteEstimate | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.routing.stations(cityId).then((data) => {
      setStations(data)
      if (data.length > 0) setSelectedStation(data[0])
    })
  }, [cityId])

  const handleCalculate = async () => {
    if (!selectedStation) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.routing.estimate({
        from_lat: selectedStation.lat,
        from_lon: selectedStation.lon,
        to_lat: selectedDest.lat,
        to_lon: selectedDest.lon,
        city: cityId,
        station_id: selectedStation.id,
      })
      setResult(res)
    } catch {
      setError('Не удалось рассчитать маршрут. Проверьте подключение к серверу.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-5">
        <h1 className="text-white text-xl font-bold">Экстренная маршрутизация</h1>
        <p className="text-gray-400 text-sm mt-1">
          Расчёт времени прибытия с учётом спецправил: выделенные полосы, встречное движение
        </p>
      </div>

      {/* Форма выбора */}
      <div className="bg-gray-800 rounded-xl p-4 mb-4 space-y-3">
        {/* Пожарная часть */}
        <div>
          <label className="text-gray-400 text-xs uppercase tracking-wide block mb-1.5">
            Откуда — пожарная часть
          </label>
          <div className="relative">
            <select
              value={selectedStation?.id ?? ''}
              onChange={(e) => {
                const s = stations.find((st) => st.id === e.target.value)
                if (s) setSelectedStation(s)
              }}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm appearance-none focus:outline-none focus:border-orange-500 pr-8"
            >
              {stations.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} — {s.district}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Адрес назначения */}
        <div>
          <label className="text-gray-400 text-xs uppercase tracking-wide block mb-1.5">
            Куда — адрес вызова
          </label>
          <div className="relative">
            <select
              value={selectedDest.label}
              onChange={(e) => {
                const d = DEMO_DESTINATIONS.find((x) => x.label === e.target.value)
                if (d) setSelectedDest(d)
              }}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm appearance-none focus:outline-none focus:border-orange-500 pr-8"
            >
              {DEMO_DESTINATIONS.map((d) => (
                <option key={d.label} value={d.label}>{d.label}</option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <button
          onClick={handleCalculate}
          disabled={loading || !selectedStation}
          className="w-full py-3 rounded-xl bg-orange-500 text-white font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-50 hover:bg-orange-600 transition-colors"
        >
          <Navigation size={16} />
          {loading ? 'Рассчитываю...' : 'Рассчитать маршрут'}
        </button>
      </div>

      {/* Ошибка */}
      {error && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-xl p-4 mb-4 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Результат */}
      {result && (
        <>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {/* Обычное время */}
            <div className="bg-gray-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock size={14} className="text-gray-400" />
                <span className="text-gray-400 text-xs uppercase tracking-wide">Обычный маршрут</span>
              </div>
              <p className="text-white text-3xl font-bold">{result.normal_min}</p>
              <p className="text-gray-500 text-xs">мин · {result.distance_km} км</p>
            </div>

            {/* Экстренное время */}
            <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Flame size={14} className="text-orange-400" />
                <span className="text-orange-400 text-xs uppercase tracking-wide">Экстренный режим</span>
              </div>
              <p className="text-orange-400 text-3xl font-bold">{result.emergency_min}</p>
              <p className="text-orange-400/60 text-xs">мин</p>
            </div>
          </div>

          {/* Экономия */}
          <div className="bg-green-900/20 border border-green-700/40 rounded-xl p-4 mb-4 flex items-center justify-between">
            <div>
              <p className="text-green-400 font-semibold text-sm">Экономия времени</p>
              <p className="text-gray-400 text-xs mt-0.5">{result.route_notes}</p>
            </div>
            <TimeDiff normal={result.normal_min} emergency={result.emergency_min} />
          </div>

          {result.source === 'haversine' && (
            <p className="text-gray-600 text-xs text-center mb-3">
              * Расчёт приближённый (прямолинейное расстояние)
            </p>
          )}

          {/* Карта */}
          {selectedStation && (
            <div className="rounded-xl overflow-hidden h-64 sm:h-80">
              <RouteMap
                from={{ lat: selectedStation.lat, lon: selectedStation.lon, label: selectedStation.name }}
                to={{ lat: selectedDest.lat, lon: selectedDest.lon, label: selectedDest.label }}
                geometry={result.geometry}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}

'use client'

import { useEffect, useRef, useState } from 'react'
import { Building2, MapPin, Layers, Phone, ChevronRight, QrCode, X } from 'lucide-react'
import QRCode from 'qrcode'
import { api } from '@/lib/api'
import type { Building } from '@/lib/types'
import { useCity } from '@/context/CityContext'

const OBJECT_TYPE_RU: Record<string, string> = {
  residential: 'Жилой',
  commercial: 'Коммерческий',
  industrial: 'Промышленный',
  construction: 'Стройплощадка',
  other: 'Прочее',
}

function QrModal({ building, onClose }: { building: Building; onClose: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current) return
    const planUrl = `${window.location.origin}/plan/${building.id}`
    QRCode.toCanvas(canvasRef.current, planUrl, { width: 220, margin: 2 })
  }, [building.id])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 rounded-2xl p-6 w-full max-w-xs flex flex-col items-center gap-4">
        <div className="flex items-center justify-between w-full">
          <span className="text-white font-semibold text-sm">{building.name}</span>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-1">
            <X size={20} />
          </button>
        </div>
        <canvas ref={canvasRef} className="rounded-xl bg-white p-2" />
        <p className="text-gray-400 text-xs text-center">
          Направьте камеру телефона для просмотра оперативного плана
        </p>
      </div>
    </div>
  )
}

function BuildingCard({ building, onQr }: { building: Building; onQr: (b: Building) => void }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700">
      {/* Header — tap to expand */}
      <button
        className="w-full text-left p-4 flex items-start gap-3"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="mt-0.5 p-2 bg-orange-500/10 rounded-lg shrink-0">
          <Building2 size={18} className="text-orange-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white font-medium text-sm truncate">{building.name}</p>
          {building.address && (
            <p className="text-gray-400 text-xs mt-0.5 truncate">{building.address}</p>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {building.object_type && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">
                {OBJECT_TYPE_RU[building.object_type] ?? building.object_type}
              </span>
            )}
            {building.floors_count && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 flex items-center gap-1">
                <Layers size={10} />
                {building.floors_count} эт.
              </span>
            )}
            {building.district && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 flex items-center gap-1">
                <MapPin size={10} />
                {building.district}
              </span>
            )}
          </div>
        </div>
        <ChevronRight
          size={16}
          className={`text-gray-500 shrink-0 mt-1 transition-transform ${expanded ? 'rotate-90' : ''}`}
        />
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-700 pt-3 space-y-3">
          {/* Контакты */}
          {(building.owner_name || building.owner_phone) && (
            <div>
              <p className="text-gray-500 text-xs mb-1 uppercase tracking-wide">Владелец</p>
              {building.owner_name && <p className="text-gray-200 text-sm">{building.owner_name}</p>}
              {building.owner_phone && (
                <a
                  href={`tel:${building.owner_phone}`}
                  className="text-orange-400 text-sm flex items-center gap-1 mt-0.5"
                >
                  <Phone size={12} />
                  {building.owner_phone}
                </a>
              )}
            </div>
          )}

          {/* Прибытие */}
          {(building.nearest_fire_department || building.arrival_time_minutes) && (
            <div>
              <p className="text-gray-500 text-xs mb-1 uppercase tracking-wide">Ближайшая ПЧ</p>
              <p className="text-gray-200 text-sm">
                {building.nearest_fire_department ?? '—'}
                {building.arrival_time_minutes != null && (
                  <span className="text-gray-400"> · {building.arrival_time_minutes} мин</span>
                )}
              </p>
              {building.route_description && (
                <p className="text-gray-400 text-xs mt-0.5">{building.route_description}</p>
              )}
            </div>
          )}

          {/* Риски */}
          {building.potential_hazards && (
            <div>
              <p className="text-gray-500 text-xs mb-1 uppercase tracking-wide">Опасные факторы</p>
              <p className="text-gray-300 text-sm">{building.potential_hazards}</p>
            </div>
          )}

          {/* Системы пожаротушения */}
          {building.fire_extinguishing_systems &&
            Object.keys(building.fire_extinguishing_systems).length > 0 && (
              <div>
                <p className="text-gray-500 text-xs mb-1 uppercase tracking-wide">Системы тушения</p>
                {Object.values(building.fire_extinguishing_systems).map((v, i) => (
                  <p key={i} className="text-gray-300 text-sm">· {v}</p>
                ))}
              </div>
            )}

          {/* QR кнопка */}
          <button
            onClick={() => onQr(building)}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-orange-500/10 text-orange-400 text-sm font-medium hover:bg-orange-500/20 transition-colors"
          >
            <QrCode size={16} />
            Показать QR-код плана
          </button>
        </div>
      )}
    </div>
  )
}

export default function BuildingsPage() {
  const { city } = useCity()
  const cityId = city?.id ?? 'astana'
  const [buildings, setBuildings] = useState<Building[]>([])
  const [loading, setLoading] = useState(true)
  const [qrBuilding, setQrBuilding] = useState<Building | null>(null)

  useEffect(() => {
    setLoading(true)
    api.buildings.list(cityId).then(setBuildings).finally(() => setLoading(false))
  }, [cityId])

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-white text-xl font-bold">Оперативные планы зданий</h1>
        <p className="text-gray-400 text-sm mt-1">
          QR-коды для быстрого доступа к плану на месте пожара
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-800 rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : buildings.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Building2 size={40} className="mx-auto mb-3 opacity-30" />
          <p>Здания не найдены</p>
        </div>
      ) : (
        <div className="space-y-3">
          {buildings.map((b) => (
            <BuildingCard key={b.id} building={b} onQr={setQrBuilding} />
          ))}
        </div>
      )}

      {qrBuilding && <QrModal building={qrBuilding} onClose={() => setQrBuilding(null)} />}
    </div>
  )
}

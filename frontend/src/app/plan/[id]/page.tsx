'use client'

import { useEffect, useState } from 'react'
import { use } from 'react'
import { Flame, MapPin, Phone, Layers, ShieldAlert, Zap, Droplets, Wind, Bell, Users } from 'lucide-react'
import { api } from '@/lib/api'
import type { Building } from '@/lib/types'

function InfoRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null || value === '') return null
  return (
    <div className="py-2.5 border-b border-gray-800 last:border-0">
      <p className="text-gray-500 text-xs uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-gray-100 text-sm">{value}</p>
    </div>
  )
}

function Section({ title, icon: Icon, children }: {
  title: string
  icon: React.ElementType
  children: React.ReactNode
}) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 mb-3">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className="text-orange-400" />
        <h2 className="text-orange-400 text-sm font-semibold uppercase tracking-wide">{title}</h2>
      </div>
      {children}
    </div>
  )
}

export default function PlanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [building, setBuilding] = useState<Building | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    api.buildings.get(id)
      .then(setBuilding)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 text-sm animate-pulse">Загрузка плана...</div>
      </div>
    )
  }

  if (error || !building) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center gap-3 p-6">
        <Flame size={40} className="text-red-500 opacity-50" />
        <p className="text-gray-400 text-center">Оперативный план не найден.<br />Обратитесь к дежурному.</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 pb-8">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-800 px-4 py-4 sticky top-0 z-10">
        <div className="flex items-center gap-2 mb-1">
          <Flame size={18} className="text-orange-400" />
          <span className="text-orange-400 text-xs font-bold uppercase tracking-widest">FireWatch</span>
        </div>
        <h1 className="text-white font-bold text-lg leading-tight">{building.name}</h1>
        {building.address && (
          <p className="text-gray-400 text-sm mt-0.5 flex items-center gap-1">
            <MapPin size={12} />
            {building.address}
          </p>
        )}
        <div className="flex flex-wrap gap-2 mt-2">
          {building.floors_count != null && (
            <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-300 rounded-full flex items-center gap-1">
              <Layers size={10} /> {building.floors_count} этажей
            </span>
          )}
          {building.fire_rank && (
            <span className="text-xs px-2 py-0.5 bg-red-900/40 text-red-300 rounded-full">
              Ранг пожара: {building.fire_rank}
            </span>
          )}
          {building.fire_resistance_degree && (
            <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-300 rounded-full">
              {building.fire_resistance_degree}
            </span>
          )}
        </div>
      </div>

      <div className="px-4 pt-4">
        {/* Прибытие */}
        <Section title="Прибытие и маршрут" icon={MapPin}>
          <InfoRow label="Ближайшая часть" value={building.nearest_fire_department} />
          <InfoRow label="Расстояние" value={building.distance_to_fire_department != null ? `${building.distance_to_fire_department} км` : null} />
          <InfoRow label="Время прибытия" value={building.arrival_time_minutes != null ? `${building.arrival_time_minutes} мин` : null} />
          <InfoRow label="Маршрут" value={building.route_description} />
        </Section>

        {/* Контакты */}
        {(building.owner_name || building.owner_phone || building.technical_manager_name || building.dispatcher_phone || building.security_phone) && (
          <Section title="Контакты" icon={Phone}>
            <InfoRow label="Владелец" value={building.owner_name} />
            {building.owner_phone && (
              <div className="py-2.5 border-b border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide mb-0.5">Телефон владельца</p>
                <a href={`tel:${building.owner_phone}`} className="text-orange-400 text-sm font-medium">{building.owner_phone}</a>
              </div>
            )}
            <InfoRow label="Технический директор" value={building.technical_manager_name} />
            {building.technical_manager_phone && (
              <div className="py-2.5 border-b border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide mb-0.5">Телефон тех. директора</p>
                <a href={`tel:${building.technical_manager_phone}`} className="text-orange-400 text-sm font-medium">{building.technical_manager_phone}</a>
              </div>
            )}
            {building.dispatcher_phone && (
              <div className="py-2.5 border-b border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide mb-0.5">Диспетчер</p>
                <a href={`tel:${building.dispatcher_phone}`} className="text-orange-400 text-sm font-medium">{building.dispatcher_phone}</a>
              </div>
            )}
            {building.security_phone && (
              <div className="py-2.5 border-b border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide mb-0.5">Охрана</p>
                <a href={`tel:${building.security_phone}`} className="text-orange-400 text-sm font-medium">{building.security_phone}</a>
              </div>
            )}
          </Section>
        )}

        {/* Риски и особенности */}
        {(building.potential_hazards || building.complexity_features) && (
          <Section title="Риски и особенности" icon={ShieldAlert}>
            <InfoRow label="Опасные факторы" value={building.potential_hazards} />
            <InfoRow label="Сложность тушения" value={building.complexity_features} />
            <InfoRow label="Вспомогательные средства" value={building.auxiliary_means} />
            <InfoRow label="Пути эвакуации (кол-во)" value={building.evacuation_routes_count} />
          </Section>
        )}

        {/* Инженерные системы */}
        {(building.power_supply_info || building.heating_info || building.water_supply_info) && (
          <Section title="Инженерные системы" icon={Zap}>
            <InfoRow label="Электроснабжение" value={building.power_supply_info} />
            <InfoRow label="Отопление" value={building.heating_info} />
            <InfoRow label="Водоснабжение" value={building.water_supply_info} />
          </Section>
        )}

        {/* Вентиляция и дымоудаление */}
        {(building.ventilation_info || building.smoke_removal_info) && (
          <Section title="Вентиляция и дымоудаление" icon={Wind}>
            <InfoRow label="Вентиляция" value={building.ventilation_info} />
            <InfoRow label="Дымоудаление" value={building.smoke_removal_info} />
          </Section>
        )}

        {/* Пожаротушение */}
        {building.fire_extinguishing_systems && Object.keys(building.fire_extinguishing_systems).length > 0 && (
          <Section title="Системы пожаротушения" icon={Droplets}>
            {Object.entries(building.fire_extinguishing_systems).map(([k, v]) => (
              <InfoRow key={k} label={k.replace(/_/g, ' ')} value={v} />
            ))}
          </Section>
        )}

        {/* Сигнализация */}
        {building.fire_alarm_info && (
          <Section title="Пожарная сигнализация" icon={Bell}>
            <InfoRow label="Система" value={building.fire_alarm_info} />
          </Section>
        )}

        {/* Расчёт сил */}
        {building.estimated_forces && Object.keys(building.estimated_forces).length > 0 && (
          <Section title="Расчёт сил и средств" icon={Users}>
            {Object.entries(building.estimated_forces).map(([k, v]) => (
              <InfoRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
            ))}
          </Section>
        )}

        <p className="text-center text-gray-600 text-xs mt-4">
          FireWatch · Оперативный план
        </p>
      </div>
    </div>
  )
}

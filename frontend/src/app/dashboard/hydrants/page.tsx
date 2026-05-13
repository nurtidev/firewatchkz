'use client'

import { useEffect, useState } from 'react'
import { Droplets, MapPin, AlertTriangle, CheckCircle, Clock, Snowflake, Edit2, X, Check } from 'lucide-react'
import { api } from '@/lib/api'
import type { Hydrant, HydrantUpdate } from '@/lib/types'
import { useCity } from '@/context/CityContext'

const STATUS_CONFIG = {
  working: { label: 'Рабочий', color: 'text-green-400', bg: 'bg-green-500/10', icon: CheckCircle },
  maintenance: { label: 'Обслуживание', color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Clock },
  out_of_service: { label: 'Не работает', color: 'text-red-400', bg: 'bg-red-500/10', icon: AlertTriangle },
}

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

function UpdateForm({
  hydrant,
  city,
  onSaved,
  onCancel,
}: {
  hydrant: Hydrant
  city: string
  onSaved: (updated: Hydrant) => void
  onCancel: () => void
}) {
  const [status, setStatus] = useState<Hydrant['status']>(hydrant.status)
  const [lastChecked, setLastChecked] = useState(hydrant.last_checked ?? '')
  const [winterAccessible, setWinterAccessible] = useState<boolean>(hydrant.winter_accessible ?? true)
  const [pressureBar, setPressureBar] = useState(hydrant.pressure_bar?.toString() ?? '')
  const [notes, setNotes] = useState(hydrant.notes ?? '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    const update: HydrantUpdate = { status, winter_accessible: winterAccessible, notes: notes || undefined }
    if (lastChecked) update.last_checked = lastChecked
    if (pressureBar) update.pressure_bar = parseFloat(pressureBar)
    try {
      const updated = await api.hydrants.update(city, hydrant.id, update)
      onSaved(updated)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="px-4 pb-4 pt-3 border-t border-gray-700 space-y-3">
      <div>
        <p className="text-gray-500 text-xs mb-1.5">Статус</p>
        <div className="flex gap-2 flex-wrap">
          {(['working', 'maintenance', 'out_of_service'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                status === s
                  ? `${STATUS_CONFIG[s].bg} ${STATUS_CONFIG[s].color} border-current`
                  : 'border-gray-700 text-gray-400'
              }`}
            >
              {STATUS_CONFIG[s].label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-gray-500 text-xs block mb-1">Дата проверки</label>
          <input
            type="date"
            value={lastChecked}
            onChange={(e) => setLastChecked(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-orange-500"
          />
        </div>
        <div>
          <label className="text-gray-500 text-xs block mb-1">Давление (бар)</label>
          <input
            type="number"
            step="0.1"
            value={pressureBar}
            onChange={(e) => setPressureBar(e.target.value)}
            placeholder="4.0"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-orange-500"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setWinterAccessible((v) => !v)}
          className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border transition-colors ${
            winterAccessible
              ? 'border-blue-500/50 text-blue-400 bg-blue-500/10'
              : 'border-gray-700 text-gray-500'
          }`}
        >
          <Snowflake size={14} />
          Зимой доступен
        </button>
      </div>

      <div>
        <label className="text-gray-500 text-xs block mb-1">Примечание</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="Описание проблемы..."
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm resize-none focus:outline-none focus:border-orange-500"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-orange-500 text-white text-sm font-medium disabled:opacity-50"
        >
          <Check size={14} />
          {saving ? 'Сохранение...' : 'Сохранить'}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2.5 rounded-lg border border-gray-700 text-gray-400 text-sm"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}

function HydrantCard({ hydrant, city, onUpdated }: { hydrant: Hydrant; city: string; onUpdated: (h: Hydrant) => void }) {
  const [editing, setEditing] = useState(false)
  const cfg = STATUS_CONFIG[hydrant.status]
  const StatusIcon = cfg.icon
  const days = daysSince(hydrant.last_checked)
  const overdueWarning = days != null && days > 180

  return (
    <div className={`bg-gray-800 rounded-xl border ${overdueWarning ? 'border-yellow-600/50' : 'border-gray-700'}`}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-3 min-w-0">
            <div className={`mt-0.5 p-2 rounded-lg shrink-0 ${cfg.bg}`}>
              <Droplets size={16} className={cfg.color} />
            </div>
            <div className="min-w-0">
              <p className="text-white text-sm font-medium truncate">{hydrant.address}</p>
              <p className="text-gray-400 text-xs flex items-center gap-1 mt-0.5">
                <MapPin size={10} />
                {hydrant.district}
              </p>
            </div>
          </div>
          <button
            onClick={() => setEditing((v) => !v)}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 transition-colors shrink-0"
          >
            <Edit2 size={14} />
          </button>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${cfg.bg} ${cfg.color}`}>
            <StatusIcon size={10} />
            {cfg.label}
          </span>
          {hydrant.pressure_bar != null && (
            <span className="text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-300">
              {hydrant.pressure_bar} бар
            </span>
          )}
          {hydrant.winter_accessible != null && (
            <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${
              hydrant.winter_accessible ? 'bg-blue-500/10 text-blue-400' : 'bg-gray-700 text-gray-500'
            }`}>
              <Snowflake size={10} />
              {hydrant.winter_accessible ? 'Зима ✓' : 'Зима ✗'}
            </span>
          )}
        </div>

        {hydrant.last_checked && (
          <p className={`text-xs mt-2 flex items-center gap-1 ${overdueWarning ? 'text-yellow-400' : 'text-gray-500'}`}>
            {overdueWarning && <AlertTriangle size={10} />}
            Проверен: {hydrant.last_checked}
            {days != null && ` (${days} дн. назад)`}
            {overdueWarning && ' — давно не проверялся'}
          </p>
        )}

        {hydrant.notes && (
          <p className="text-gray-400 text-xs mt-2 italic">{hydrant.notes}</p>
        )}
      </div>

      {editing && (
        <UpdateForm
          hydrant={hydrant}
          city={city}
          onSaved={(updated) => { onUpdated(updated); setEditing(false) }}
          onCancel={() => setEditing(false)}
        />
      )}
    </div>
  )
}

export default function HydrantsPage() {
  const { city } = useCity()
  const cityId = city?.id ?? 'astana'
  const [hydrants, setHydrants] = useState<Hydrant[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')

  useEffect(() => {
    setLoading(true)
    api.hydrants.list(cityId).then(setHydrants).finally(() => setLoading(false))
  }, [cityId])

  const handleUpdated = (updated: Hydrant) => {
    setHydrants((prev) => prev.map((h) => (h.id === updated.id ? updated : h)))
  }

  const filtered = filter === 'all' ? hydrants : hydrants.filter((h) => h.status === filter)
  const counts = {
    working: hydrants.filter((h) => h.status === 'working').length,
    maintenance: hydrants.filter((h) => h.status === 'maintenance').length,
    out_of_service: hydrants.filter((h) => h.status === 'out_of_service').length,
    overdue: hydrants.filter((h) => {
      const d = daysSince(h.last_checked)
      return d != null && d > 180
    }).length,
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-5">
        <h1 className="text-white text-xl font-bold">Гидранты</h1>
        <p className="text-gray-400 text-sm mt-1">Состояние и проверки пожарных гидрантов</p>
      </div>

      {/* Сводка */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-5">
        <div className="bg-green-500/10 rounded-xl p-3 text-center">
          <p className="text-green-400 text-xl font-bold">{counts.working}</p>
          <p className="text-green-400/70 text-xs">Рабочих</p>
        </div>
        <div className="bg-yellow-500/10 rounded-xl p-3 text-center">
          <p className="text-yellow-400 text-xl font-bold">{counts.maintenance}</p>
          <p className="text-yellow-400/70 text-xs">Обслуживание</p>
        </div>
        <div className="bg-red-500/10 rounded-xl p-3 text-center">
          <p className="text-red-400 text-xl font-bold">{counts.out_of_service}</p>
          <p className="text-red-400/70 text-xs">Не работают</p>
        </div>
        <div className="bg-orange-500/10 rounded-xl p-3 text-center">
          <p className="text-orange-400 text-xl font-bold">{counts.overdue}</p>
          <p className="text-orange-400/70 text-xs">Просрочены</p>
        </div>
      </div>

      {/* Фильтр */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {[
          { key: 'all', label: 'Все' },
          { key: 'working', label: 'Рабочие' },
          { key: 'maintenance', label: 'Обслуживание' },
          { key: 'out_of_service', label: 'Не работают' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors ${
              filter === key
                ? 'bg-orange-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-800 rounded-xl h-28 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((h) => (
            <HydrantCard key={h.id} hydrant={h} city={cityId} onUpdated={handleUpdated} />
          ))}
        </div>
      )}
    </div>
  )
}

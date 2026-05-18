'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { FileText, Trash2, Upload, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import type { OperationalCard } from '@/lib/types'
import UploadModal from '@/components/documents/UploadModal'

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Загружен',
  processing: 'Обрабатывается',
  ready_for_extraction: 'Готов к извлечению',
  extracted: 'Извлечено',
  approved: 'Утверждено',
  rejected: 'Отклонено',
  deleted: 'Удалён',
}

const STATUS_CHIP: Record<string, string> = {
  uploaded: 'bg-gray-700 text-gray-300',
  processing: 'bg-yellow-500/10 text-yellow-400',
  ready_for_extraction: 'bg-yellow-500/10 text-yellow-400',
  extracted: 'bg-blue-500/10 text-blue-400',
  approved: 'bg-green-500/10 text-green-400',
  rejected: 'bg-red-500/10 text-red-400',
  deleted: 'bg-gray-700 text-gray-500',
}

const TERMINAL_STATUSES = new Set(['extracted', 'approved', 'rejected', 'deleted'])

const ACTIVE_STATUSES = ['uploaded', 'processing', 'ready_for_extraction']

const FILTER_OPTIONS = [
  { key: 'all', label: 'Все' },
  { key: 'uploaded', label: 'Загружен' },
  { key: 'processing', label: 'Обрабатывается' },
  { key: 'ready_for_extraction', label: 'Готов к извлечению' },
  { key: 'extracted', label: 'Извлечено' },
  { key: 'approved', label: 'Утверждено' },
  { key: 'rejected', label: 'Отклонено' },
]

const MOCK_CARDS: OperationalCard[] = [
  {
    id: 'mock-1',
    status: 'approved',
    file_name: 'plan_respublika_2024.pdf',
    file_mime: 'application/pdf',
    uploaded_at: '2024-11-15T10:30:00Z',
    building_id: 'bld-001',
    uploaded_by: 'admin',
    thumbnail_key: null,
    converted_key: null,
  },
  {
    id: 'mock-2',
    status: 'processing',
    file_name: 'karta_baiterek.pdf',
    file_mime: 'application/pdf',
    uploaded_at: '2024-12-01T08:00:00Z',
    building_id: null,
    uploaded_by: 'operator',
    thumbnail_key: null,
    converted_key: null,
  },
]

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_CHIP[status] ?? 'bg-gray-700 text-gray-400'}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

function SkeletonRows() {
  return (
    <>
      {[1, 2, 3].map((i) => (
        <tr key={i}>
          {[1, 2, 3, 4, 5, 6].map((j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 bg-gray-700 rounded animate-pulse" style={{ width: j === 1 ? '80%' : '60%' }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

function MobileCard({
  card,
  onDelete,
  onClick,
}: {
  card: OperationalCard
  onDelete: (id: string) => void
  onClick: (id: string) => void
}) {
  return (
    <div
      className="bg-gray-800 rounded-xl border border-gray-700 p-4 cursor-pointer hover:border-gray-600 transition-colors"
      onClick={() => onClick(card.id)}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="p-2 bg-orange-500/10 rounded-lg shrink-0">
            <FileText size={16} className="text-orange-400" />
          </div>
          <p className="text-white text-sm font-medium truncate">{card.file_name}</p>
        </div>
        <StatusChip status={card.status} />
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{formatDate(card.uploaded_at)}</span>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(card.id) }}
          className="flex items-center gap-1 text-red-400 hover:text-red-300 transition-colors px-2 py-1 rounded"
        >
          <Trash2 size={12} />
          Удалить
        </button>
      </div>
      {(card.building_id || card.uploaded_by) && (
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
          {card.building_id && <span>Здание: {card.building_id}</span>}
          {card.uploaded_by && <span>Загрузил: {card.uploaded_by}</span>}
        </div>
      )}
    </div>
  )
}

export default function DocumentsPage() {
  const router = useRouter()
  const [cards, setCards] = useState<OperationalCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [filter, setFilter] = useState<string>('all')
  const [toast, setToast] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const fetchCards = async (initial = false) => {
    try {
      const data = await api.documents.list()
      setCards(data)
      setError(false)
    } catch {
      if (initial) {
        setCards(MOCK_CARDS)
        setError(false)
      } else {
        setError(true)
      }
    } finally {
      if (initial) setLoading(false)
    }
  }

  // Start or stop polling based on whether any card is in an active (non-terminal) status
  useEffect(() => {
    const hasActive = cards.some((c) => ACTIVE_STATUSES.includes(c.status))
    if (hasActive && !pollingRef.current) {
      pollingRef.current = setInterval(() => { fetchCards() }, 5000)
    } else if (!hasActive && pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    return () => {
      // cleanup handled by the condition above; full cleanup on unmount below
    }
  }, [cards])

  // Unmount cleanup
  useEffect(() => {
    fetchCards(true)
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const handleDelete = async (id: string) => {
    try {
      await api.documents.delete(id)
      setCards((prev) => prev.filter((c) => c.id !== id))
      showToast('Документ удалён')
    } catch {
      showToast('Ошибка при удалении. Попробуйте снова.')
    } finally {
      setConfirmDelete(null)
    }
  }

  const handleRowClick = (id: string) => {
    router.push(`/dashboard/documents/${id}`)
  }

  const filtered = filter === 'all' ? cards : cards.filter((c) => c.status === filter)

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-white text-xl font-bold">Оперативные карточки</h1>
          <p className="text-gray-400 text-sm mt-1">
            ИИ-обработка карточек по форме МЧС РК — загрузите PDF, проверьте поля, утвердите.
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors shrink-0"
        >
          <Upload size={15} />
          Загрузить документ
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-5">
        {(() => {
          const total = cards.length
          const inProgress = cards.filter((c) => ACTIVE_STATUSES.includes(c.status)).length
          const ready = cards.filter((c) => c.status === 'extracted').length
          const approved = cards.filter((c) => c.status === 'approved').length
          return [
            { label: 'Всего', value: total, tone: 'border-gray-700 bg-gray-900/50 text-white' },
            { label: 'В обработке', value: inProgress, tone: 'border-yellow-500/30 bg-yellow-500/5 text-yellow-300' },
            { label: 'Ждут ревью', value: ready, tone: 'border-blue-500/30 bg-blue-500/5 text-blue-300' },
            { label: 'Утверждено', value: approved, tone: 'border-green-500/30 bg-green-500/5 text-green-300' },
          ].map(({ label, value, tone }) => (
            <div key={label} className={`rounded-lg border px-3 py-2.5 ${tone}`}>
              <div className="text-[10px] uppercase tracking-wide opacity-70">{label}</div>
              <div className="font-semibold text-base">{value}</div>
            </div>
          ))
        })()}
      </div>

      {/* Filter bar */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
        {FILTER_OPTIONS.map(({ key, label }) => (
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

      {/* Error state */}
      {error && (
        <div className="flex items-center justify-between gap-3 mb-4 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
          <span>Ошибка загрузки документов. Повторите попытку.</span>
          <button
            onClick={() => fetchCards(true)}
            className="flex items-center gap-1.5 hover:text-red-300 transition-colors"
          >
            <RefreshCw size={14} />
            Повторить
          </button>
        </div>
      )}

      {/* Desktop table */}
      <div className="hidden md:block bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="px-4 py-3 text-left text-gray-400 font-medium">Файл</th>
              <th className="px-4 py-3 text-left text-gray-400 font-medium">Статус</th>
              <th className="px-4 py-3 text-left text-gray-400 font-medium">Дата загрузки</th>
              <th className="px-4 py-3 text-left text-gray-400 font-medium">Здание</th>
              <th className="px-4 py-3 text-left text-gray-400 font-medium">Загрузил</th>
              <th className="px-4 py-3 text-left text-gray-400 font-medium">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {loading ? (
              <SkeletonRows />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-500">
                  <FileText size={36} className="mx-auto mb-3 opacity-30" />
                  <p>Документы не найдены. Загрузите первую карточку.</p>
                </td>
              </tr>
            ) : (
              filtered.map((card) => (
                <tr
                  key={card.id}
                  className="hover:bg-gray-700/40 cursor-pointer transition-colors"
                  onClick={() => handleRowClick(card.id)}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText size={14} className="text-orange-400 shrink-0" />
                      <span className="text-white truncate max-w-[200px]">{card.file_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusChip status={card.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-400">{formatDate(card.uploaded_at)}</td>
                  <td className="px-4 py-3 text-gray-400">{card.building_id ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-400">{card.uploaded_by ?? '—'}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); setConfirmDelete(card.id) }}
                      className="flex items-center gap-1.5 text-red-400 hover:text-red-300 transition-colors text-xs px-2 py-1 rounded hover:bg-red-500/10"
                    >
                      <Trash2 size={13} />
                      Удалить
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {loading ? (
          [1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-800 rounded-xl h-24 animate-pulse" />
          ))
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <FileText size={36} className="mx-auto mb-3 opacity-30" />
            <p>Документы не найдены. Загрузите первую карточку.</p>
          </div>
        ) : (
          filtered.map((card) => (
            <MobileCard
              key={card.id}
              card={card}
              onDelete={(id) => setConfirmDelete(id)}
              onClick={handleRowClick}
            />
          ))
        )}
      </div>

      {/* Confirm delete dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="bg-gray-900 rounded-2xl p-6 w-full max-w-sm border border-gray-700">
            <h2 className="text-white font-semibold text-base mb-2">Удалить документ?</h2>
            <p className="text-gray-400 text-sm mb-5">
              Это действие необратимо. Документ будет помечен как удалённый.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleDelete(confirmDelete)}
                className="flex-1 py-2.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors"
              >
                Удалить
              </button>
              <button
                onClick={() => setConfirmDelete(null)}
                className="flex-1 py-2.5 rounded-lg border border-gray-700 text-gray-400 hover:text-white text-sm transition-colors"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm shadow-xl">
          {toast}
        </div>
      )}

      {/* Upload modal */}
      <UploadModal
        open={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUploaded={() => {
          setShowUploadModal(false)
          fetchCards()
        }}
      />
    </div>
  )
}

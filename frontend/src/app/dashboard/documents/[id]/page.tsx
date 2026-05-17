'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '@/lib/api'
import type { ExtractionData, FieldValue, OperationalCard, Vulnerability } from '@/lib/types'
import PdfPreviewLoader from '@/components/documents/PdfPreviewLoader'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const FIELD_CONFIG: { key: keyof NonNullable<ExtractionData['extracted_data']>; label: string }[] = [
  { key: 'card_number', label: 'Номер карточки' },
  { key: 'approved_date', label: 'Дата утверждения' },
  { key: 'building_name', label: 'Название объекта' },
  { key: 'address', label: 'Адрес' },
  { key: 'city', label: 'Город' },
  { key: 'hazard_class', label: 'Категория (Ф1-Ф5)' },
  { key: 'floors_above', label: 'Этажей надземных' },
  { key: 'floors_below', label: 'Этажей подземных' },
  { key: 'total_area_sqm', label: 'Общая площадь, м²' },
  { key: 'height_m', label: 'Высота, м' },
  { key: 'year_built', label: 'Год постройки' },
  { key: 'wall_material', label: 'Материал стен' },
  { key: 'fire_resistance_degree', label: 'Степень огнестойкости' },
  { key: 'max_occupancy', label: 'Макс. вместимость' },
  { key: 'has_gas_systems', label: 'Газовые системы' },
]

const SEVERITY_ORDER: Record<Vulnerability['severity'], number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

const SEVERITY_STYLES: Record<Vulnerability['severity'], string> = {
  critical: 'bg-red-500/20 border-red-500 text-red-400',
  high: 'bg-orange-500/20 border-orange-500 text-orange-400',
  medium: 'bg-yellow-500/20 border-yellow-500 text-yellow-400',
  low: 'bg-gray-500/20 border-gray-500 text-gray-400',
}

const SEVERITY_LABELS: Record<Vulnerability['severity'], string> = {
  critical: 'Критично',
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fieldConfidenceClass(confidence: number): {
  ring: string
  label: string
  editable: boolean
} {
  if (confidence > 0.9) {
    return { ring: 'ring-2 ring-green-500', label: 'text-green-400', editable: false }
  }
  if (confidence >= 0.6) {
    return { ring: 'ring-2 ring-yellow-500', label: 'text-yellow-400', editable: true }
  }
  return { ring: 'ring-2 ring-red-500', label: 'text-red-400', editable: true }
}

function fieldValueToString(v: string | number | boolean | null | undefined): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'boolean') return v ? 'Да' : 'Нет'
  return String(v)
}

// ---------------------------------------------------------------------------
// VulnerabilityCard
// ---------------------------------------------------------------------------

function VulnerabilityCard({ vuln }: { vuln: Vulnerability }) {
  const [expanded, setExpanded] = useState(false)
  const styles = SEVERITY_STYLES[vuln.severity]

  return (
    <div className={`border rounded-xl overflow-hidden ${styles}`}>
      <button
        type="button"
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full border border-current shrink-0">
            {SEVERITY_LABELS[vuln.severity]}
          </span>
          <span className="text-sm font-medium truncate text-gray-100">{vuln.description}</span>
        </div>
        {expanded ? <ChevronUp size={16} className="shrink-0" /> : <ChevronDown size={16} className="shrink-0" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-2 border-t border-current/20">
          {vuln.regulation_violated && (
            <p className="text-xs text-gray-400 mt-3">
              <span className="font-medium text-gray-300">Нарушение: </span>
              {vuln.regulation_violated}
            </p>
          )}
          <p className="text-xs text-gray-300">
            <span className="font-medium">Рекомендация: </span>
            {vuln.recommended_action}
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ExtractedFields panel
// ---------------------------------------------------------------------------

interface ExtractedFieldsPanelProps {
  extraction: ExtractionData
  corrections: Record<string, string>
  onCorrection: (key: string, value: string) => void
  firstEditableRef: React.RefObject<HTMLInputElement | null>
}

function ExtractedFieldsPanel({
  extraction,
  corrections,
  onCorrection,
  firstEditableRef,
}: ExtractedFieldsPanelProps) {
  const data = extraction.extracted_data
  const isFirst = useRef(true)

  const vulnerabilities = (data.vulnerabilities ?? []).slice().sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  )

  return (
    <div className="space-y-4">
      <h2 className="text-white font-semibold text-sm uppercase tracking-wide">
        Извлечённые данные
      </h2>

      {data.overall_confidence !== undefined && (
        <p className="text-gray-400 text-xs">
          Общая уверенность: {Math.round(data.overall_confidence * 100)}%
        </p>
      )}

      <div className="space-y-3">
        {FIELD_CONFIG.map(({ key, label }) => {
          const fieldEntry = data[key]
          // Only handle FieldValue entries (skip special nested keys)
          if (!fieldEntry || typeof fieldEntry !== 'object' || Array.isArray(fieldEntry)) return null
          const fv = fieldEntry as FieldValue
          const { ring, label: labelClass, editable } = fieldConfidenceClass(fv.confidence)
          const currentValue = corrections[key] !== undefined
            ? corrections[key]
            : fieldValueToString(fv.value)

          if (!editable) {
            return (
              <div key={key}>
                <p className={`text-xs mb-1 ${labelClass}`}>{label}</p>
                <p className={`text-sm text-gray-100 px-3 py-2 rounded-lg bg-gray-800 ${ring}`}>
                  {currentValue || '—'}
                </p>
              </div>
            )
          }

          // Editable field
          const refCallback = (el: HTMLInputElement | null) => {
            if (el && isFirst.current) {
              isFirst.current = false
              firstEditableRef.current = el
            }
          }

          return (
            <div key={key}>
              <p className={`text-xs mb-1 ${labelClass}`}>{label}</p>
              <input
                ref={refCallback}
                type="text"
                value={currentValue}
                onChange={(e) => onCorrection(key, e.target.value)}
                className={`w-full text-sm text-gray-100 bg-gray-800 px-3 py-2 rounded-lg outline-none ${ring} focus:ring-offset-0 placeholder-gray-600`}
                placeholder={`Введите ${label.toLowerCase()}`}
              />
            </div>
          )
        })}
      </div>

      {data.extraction_notes && (
        <div className="mt-4 px-3 py-2 bg-gray-800 rounded-lg">
          <p className="text-gray-400 text-xs">{data.extraction_notes}</p>
        </div>
      )}

      {data.missing_fields && data.missing_fields.length > 0 && (
        <div className="mt-2 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <p className="text-yellow-400 text-xs font-medium mb-1">Не найдены поля:</p>
          <p className="text-yellow-300 text-xs">{data.missing_fields.join(', ')}</p>
        </div>
      )}

      {vulnerabilities.length > 0 && (
        <div className="pt-2">
          <h3 className="text-white font-semibold text-sm uppercase tracking-wide mb-3">
            Уязвимости
          </h3>
          <div className="space-y-2">
            {vulnerabilities.map((v, i) => (
              <VulnerabilityCard key={i} vuln={v} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonPanel() {
  return (
    <div className="space-y-4">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i}>
          <div className="h-3 w-24 bg-gray-700 rounded animate-pulse mb-1" />
          <div className="h-9 bg-gray-700 rounded-lg animate-pulse" />
        </div>
      ))}
    </div>
  )
}

function SkeletonPdf() {
  return <div className="h-full min-h-64 bg-gray-700 rounded-xl animate-pulse" />
}

// ---------------------------------------------------------------------------
// Approve/Reject confirm dialog
// ---------------------------------------------------------------------------

interface ConfirmDialogProps {
  message: string
  onConfirm: () => void
  onCancel: () => void
  confirmLabel: string
  confirmClass: string
}

function ConfirmDialog({ message, onConfirm, onCancel, confirmLabel, confirmClass }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 rounded-2xl p-6 w-full max-w-sm border border-gray-700">
        <p className="text-white text-sm mb-5">{message}</p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onConfirm}
            className={`flex-1 py-2.5 rounded-lg text-white text-sm font-medium transition-colors ${confirmClass}`}
          >
            {confirmLabel}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-lg border border-gray-700 text-gray-400 hover:text-white text-sm transition-colors"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type ActiveTab = 'pdf' | 'data'

export default function DocumentReviewPage() {
  const params = useParams()
  const router = useRouter()
  const id = Array.isArray(params.id) ? params.id[0] : params.id ?? ''

  const [card, setCard] = useState<OperationalCard | null>(null)
  const [extraction, setExtraction] = useState<ExtractionData | null>(null)
  const [loadingCard, setLoadingCard] = useState(true)
  const [loadingExtraction, setLoadingExtraction] = useState(true)
  const [errorCard, setErrorCard] = useState(false)
  const [errorExtraction, setErrorExtraction] = useState(false)
  const [noExtraction, setNoExtraction] = useState(false)

  const [corrections, setCorrections] = useState<Record<string, string>>({})
  const [activeTab, setActiveTab] = useState<ActiveTab>('pdf')

  const [confirm, setConfirm] = useState<'approve' | 'reject' | null>(null)
  const [acting, setActing] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const firstEditableRef = useRef<HTMLInputElement | null>(null)

  // Focus first editable field once extraction loads
  useEffect(() => {
    if (extraction && firstEditableRef.current) {
      firstEditableRef.current.focus()
    }
  }, [extraction])

  const showToast = useCallback((msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3500)
  }, [])

  useEffect(() => {
    if (!id) return
    setLoadingCard(true)
    api.documents.getDetail(id)
      .then(setCard)
      .catch(() => setErrorCard(true))
      .finally(() => setLoadingCard(false))

    setLoadingExtraction(true)
    api.documents.getExtraction(id)
      .then(setExtraction)
      .catch((err: Error) => {
        if (err.message.includes('404')) {
          setNoExtraction(true)
        } else {
          setErrorExtraction(true)
        }
      })
      .finally(() => setLoadingExtraction(false))
  }, [id])

  const handleCorrection = useCallback((key: string, value: string) => {
    setCorrections((prev) => ({ ...prev, [key]: value }))
  }, [])

  // Check if approve button should be disabled:
  // any red-confidence field (< 0.6) that is empty and not corrected by user
  const approveDisabled = (() => {
    if (!extraction) return true
    const data = extraction.extracted_data
    return FIELD_CONFIG.some(({ key }) => {
      const fieldEntry = data[key]
      if (!fieldEntry || typeof fieldEntry !== 'object' || Array.isArray(fieldEntry)) return false
      const fv = fieldEntry as FieldValue
      if (fv.confidence >= 0.6) return false
      // red field — check if has value
      const val = corrections[key] !== undefined ? corrections[key] : fieldValueToString(fv.value)
      return !val.trim()
    })
  })()

  const handleApprove = async () => {
    setActing(true)
    try {
      if (Object.keys(corrections).length > 0) {
        await api.documents.patchExtraction(id, corrections)
      }
      await api.documents.approve(id)
      router.push('/dashboard/documents')
    } catch {
      showToast('Ошибка при утверждении документа. Попробуйте снова.')
    } finally {
      setActing(false)
      setConfirm(null)
    }
  }

  const handleReject = async () => {
    setActing(true)
    try {
      await api.documents.reject(id)
      router.push('/dashboard/documents')
    } catch {
      showToast('Ошибка при отклонении документа. Попробуйте снова.')
    } finally {
      setActing(false)
      setConfirm(null)
    }
  }

  // Build PDF URL from card data
  const pdfUrl = card?.converted_key
    ? `${BASE_URL}/api/v2/documents/${id}/file`
    : null

  const isLoading = loadingCard || loadingExtraction

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!isLoading && errorCard) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            onClick={() => router.push('/dashboard/documents')}
            className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft size={16} />
            Документы
          </button>
        </div>
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg">Не удалось загрузить документ</p>
          <button
            type="button"
            onClick={() => router.push('/dashboard/documents')}
            className="mt-4 px-4 py-2 rounded-lg bg-gray-800 text-gray-300 hover:text-white text-sm transition-colors"
          >
            Вернуться к списку
          </button>
        </div>
      </div>
    )
  }

  if (!isLoading && noExtraction) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            onClick={() => router.push('/dashboard/documents')}
            className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft size={16} />
            Документы
          </button>
        </div>
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg text-white">Данные ещё не извлечены</p>
          <p className="mt-2 text-sm">Дождитесь завершения обработки.</p>
          <button
            type="button"
            onClick={() => router.push('/dashboard/documents')}
            className="mt-4 px-4 py-2 rounded-lg bg-gray-800 text-gray-300 hover:text-white text-sm transition-colors"
          >
            Вернуться к списку
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => router.push('/dashboard/documents')}
            className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors text-sm shrink-0"
          >
            <ArrowLeft size={16} />
            Документы
          </button>
          {card && (
            <span className="text-white font-medium text-sm truncate">
              {card.file_name}
            </span>
          )}
          {loadingCard && (
            <div className="h-4 w-40 bg-gray-700 rounded animate-pulse" />
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            disabled={acting || isLoading}
            onClick={() => setConfirm('reject')}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-500/50 text-red-400 hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed text-sm transition-colors"
          >
            <XCircle size={15} />
            Отклонить
          </button>
          <button
            type="button"
            disabled={acting || isLoading || approveDisabled}
            onClick={() => setConfirm('approve')}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            <CheckCircle size={15} />
            Утвердить
          </button>
        </div>
      </div>

      {/* Mobile tabs */}
      <div className="md:hidden flex gap-1 mb-4 bg-gray-800 rounded-xl p-1">
        <button
          type="button"
          onClick={() => setActiveTab('pdf')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'pdf'
              ? 'bg-gray-700 text-white'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          PDF
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('data')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'data'
              ? 'bg-gray-700 text-white'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Данные
        </button>
      </div>

      {/* Split layout — desktop: side by side, mobile: tabs */}
      <div className="flex-1 grid md:grid-cols-2 gap-4 min-h-0">
        {/* Left: PDF */}
        <div className={`${activeTab === 'data' ? 'hidden md:block' : 'block'} overflow-auto`}>
          {isLoading ? (
            <SkeletonPdf />
          ) : pdfUrl ? (
            <PdfPreviewLoader
              url={pdfUrl}
              mimeType={card?.file_mime ?? undefined}
              className="h-full"
            />
          ) : (
            <div className="flex items-center justify-center h-64 bg-gray-800 rounded-xl border border-gray-700 text-gray-500 text-sm">
              Предпросмотр недоступен
            </div>
          )}
        </div>

        {/* Right: Extracted fields */}
        <div
          className={`${activeTab === 'pdf' ? 'hidden md:block' : 'block'} overflow-y-auto`}
        >
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
            {isLoading ? (
              <SkeletonPanel />
            ) : errorExtraction ? (
              <div className="text-center py-10 text-gray-500 text-sm">
                Ошибка загрузки данных извлечения
              </div>
            ) : extraction ? (
              <ExtractedFieldsPanel
                extraction={extraction}
                corrections={corrections}
                onCorrection={handleCorrection}
                firstEditableRef={firstEditableRef}
              />
            ) : null}
          </div>
        </div>
      </div>

      {/* Confirm dialogs */}
      {confirm === 'reject' && (
        <ConfirmDialog
          message="Вы уверены, что хотите отклонить этот документ?"
          onConfirm={handleReject}
          onCancel={() => setConfirm(null)}
          confirmLabel="Отклонить"
          confirmClass="bg-red-600 hover:bg-red-500"
        />
      )}
      {confirm === 'approve' && (
        <ConfirmDialog
          message="Утвердить документ? Данные будут сохранены в систему."
          onConfirm={handleApprove}
          onCancel={() => setConfirm(null)}
          confirmLabel="Утвердить"
          confirmClass="bg-green-600 hover:bg-green-500"
        />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm shadow-xl">
          {toast}
        </div>
      )}
    </div>
  )
}

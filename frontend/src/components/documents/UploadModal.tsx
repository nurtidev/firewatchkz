'use client'

import { useCallback, useRef, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { useRouter } from 'next/navigation'
import { X, FileText, CheckCircle, XCircle, Loader2 } from 'lucide-react'

// ── Types ──────────────────────────────────────────────────────────────────────

interface UploadModalProps {
  open: boolean
  onClose: () => void
  onUploaded?: (cardId: string) => void
}

type FileStatus = 'pending' | 'uploading' | 'done' | 'error'

interface FileEntry {
  id: string
  file: File
  status: FileStatus
  progress: number
  errorMsg: string | null
  cardId: string | null
}

interface UploadResponse {
  card_id: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const MAX_SIZE_BYTES = 50 * 1024 * 1024 // 50 MB

const ACCEPTED_MIME: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
  'application/vnd.visio': ['.vsd'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function errorFromStatus(status: string): string {
  if (status === '413') return 'Файл слишком большой'
  if (status === '415') return 'Неподдерживаемый формат файла'
  if (status === 'network') return 'Ошибка соединения. Повторите попытку.'
  return `Ошибка загрузки (${status})`
}

function uploadWithProgress(
  file: File,
  onProgress: (pct: number) => void,
  signal?: AbortSignal,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const form = new FormData()
    form.append('file', file)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const parsed = JSON.parse(xhr.responseText) as UploadResponse
        resolve(parsed)
      } else {
        reject(new Error(String(xhr.status)))
      }
    }

    xhr.onerror = () => reject(new Error('network'))

    if (signal) {
      signal.addEventListener('abort', () => xhr.abort())
    }

    const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    xhr.open('POST', `${baseUrl}/api/v2/documents/upload`)
    xhr.send(form)
  })
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: FileStatus }) {
  if (status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-700 text-gray-300">
        Ожидание
      </span>
    )
  }
  if (status === 'uploading') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-500/10 text-blue-400">
        <Loader2 size={10} className="animate-spin" />
        Загрузка
      </span>
    )
  }
  if (status === 'done') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-500/10 text-green-400">
        <CheckCircle size={10} />
        Загружен
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-400">
      <XCircle size={10} />
      Ошибка
    </span>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function UploadModal({ open, onClose, onUploaded }: UploadModalProps) {
  const router = useRouter()
  const [files, setFiles] = useState<FileEntry[]>([])
  const [uploading, setUploading] = useState(false)
  const [allDone, setAllDone] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // ── Dropzone ─────────────────────────────────────────────────────────────────

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      const newEntries: FileEntry[] = accepted.map((f) => ({
        id: `${f.name}-${f.lastModified}-${Math.random()}`,
        file: f,
        status: 'pending',
        progress: 0,
        errorMsg: null,
        cardId: null,
      }))

      const oversized: FileEntry[] = rejected
        .filter((r) => r.errors.some((e) => e.code === 'file-too-large'))
        .map((r) => ({
          id: `${r.file.name}-${r.file.lastModified}-${Math.random()}`,
          file: r.file,
          status: 'error',
          progress: 0,
          errorMsg: 'Файл слишком большой (макс. 50 МБ)',
          cardId: null,
        }))

      const wrongType: FileEntry[] = rejected
        .filter((r) => r.errors.some((e) => e.code === 'file-invalid-type'))
        .map((r) => ({
          id: `${r.file.name}-${r.file.lastModified}-${Math.random()}`,
          file: r.file,
          status: 'error',
          progress: 0,
          errorMsg: 'Неподдерживаемый формат файла',
          cardId: null,
        }))

      setFiles((prev) => [...prev, ...newEntries, ...oversized, ...wrongType])
      setAllDone(false)
    },
    [],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_MIME,
    maxSize: MAX_SIZE_BYTES,
    multiple: true,
  })

  // ── File list helpers ─────────────────────────────────────────────────────────

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const updateFile = (id: string, patch: Partial<FileEntry>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)))
  }

  // ── Upload logic ──────────────────────────────────────────────────────────────

  const handleUpload = async () => {
    const pending = files.filter((f) => f.status === 'pending')
    if (pending.length === 0) return

    setUploading(true)
    const controller = new AbortController()
    abortRef.current = controller

    const uploadedIds: string[] = []

    for (const entry of pending) {
      if (controller.signal.aborted) break

      updateFile(entry.id, { status: 'uploading', progress: 0 })

      try {
        const result = await uploadWithProgress(
          entry.file,
          (pct) => updateFile(entry.id, { progress: pct }),
          controller.signal,
        )
        updateFile(entry.id, { status: 'done', progress: 100, cardId: result.card_id })
        uploadedIds.push(result.card_id)
        onUploaded?.(result.card_id)
      } catch (err) {
        const msg = err instanceof Error ? errorFromStatus(err.message) : 'Ошибка загрузки'
        updateFile(entry.id, { status: 'error', errorMsg: msg })
      }
    }

    setUploading(false)
    abortRef.current = null

    // Check if everything that could be uploaded is now done
    setFiles((prev) => {
      const stillPending = prev.some((f) => f.status === 'pending' || f.status === 'uploading')
      if (!stillPending) setAllDone(true)
      return prev
    })

    // Redirect if exactly 1 file succeeded
    if (uploadedIds.length === 1 && pending.length === 1) {
      router.push(`/dashboard/documents/${uploadedIds[0]}`)
    }
  }

  // ── Close guard ───────────────────────────────────────────────────────────────

  const handleClose = () => {
    if (uploading) return
    setFiles([])
    setAllDone(false)
    onClose()
  }

  // ── Derived state ─────────────────────────────────────────────────────────────

  const hasPending = files.some((f) => f.status === 'pending')
  const showUploadButton = !allDone && files.length > 0

  if (!open) return null

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-gray-700">
          <h2 className="text-white text-base font-semibold">Загрузка оперативной карточки</h2>
          <button
            onClick={handleClose}
            disabled={uploading}
            className="text-gray-400 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Закрыть"
          >
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">

          {/* Dropzone */}
          <div
            {...getRootProps()}
            className={[
              'border-2 border-dashed rounded-xl px-6 py-8 text-center cursor-pointer transition-colors',
              isDragActive
                ? 'border-blue-500 bg-blue-500/5'
                : 'border-gray-600 hover:border-gray-500 bg-gray-800/50',
            ].join(' ')}
          >
            <input {...getInputProps()} />
            <p className="text-gray-300 text-sm font-medium mb-1">
              Перетащите файлы сюда
            </p>
            <p className="text-gray-500 text-sm mb-3">или нажмите для выбора</p>
            <p className="text-gray-600 text-xs">
              Форматы: PDF, DOCX, DOC, VSD, JPG, PNG — до 50 МБ
            </p>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <ul className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {files.map((entry) => (
                <li
                  key={entry.id}
                  className="bg-gray-800 rounded-lg px-3 py-2.5 flex flex-col gap-1.5"
                >
                  <div className="flex items-center gap-2">
                    <FileText size={14} className="text-orange-400 shrink-0" />
                    <span className="text-white text-xs truncate flex-1">{entry.file.name}</span>
                    <span className="text-gray-500 text-xs shrink-0">{humanSize(entry.file.size)}</span>
                    <StatusChip status={entry.status} />
                    {entry.status !== 'uploading' && (
                      <button
                        onClick={() => removeFile(entry.id)}
                        className="text-gray-500 hover:text-gray-300 transition-colors shrink-0 ml-1"
                        aria-label="Убрать файл"
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>

                  {/* Progress bar */}
                  {(entry.status === 'uploading' || (entry.status === 'done' && entry.progress > 0)) && (
                    <div className="h-1 rounded-full bg-gray-700 overflow-hidden">
                      <div
                        className={[
                          'h-full rounded-full transition-all duration-300',
                          entry.status === 'done' ? 'bg-green-500' : 'bg-blue-500',
                        ].join(' ')}
                        style={{ width: `${entry.progress}%` }}
                      />
                    </div>
                  )}

                  {/* Error message */}
                  {entry.status === 'error' && entry.errorMsg && (
                    <p className="text-red-400 text-xs">{entry.errorMsg}</p>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* All-done banner */}
          {allDone && (
            <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/30 rounded-lg">
              <CheckCircle size={16} className="text-green-400 shrink-0" />
              <span className="text-green-400 text-sm">Все файлы загружены</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 pt-1">
            {showUploadButton && (
              <button
                onClick={handleUpload}
                disabled={uploading || !hasPending}
                className="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={14} className="animate-spin" />
                    Загрузка...
                  </span>
                ) : (
                  'Загрузить'
                )}
              </button>
            )}
            <button
              onClick={handleClose}
              disabled={uploading}
              className={[
                'py-2.5 rounded-lg border border-gray-700 text-gray-400 hover:text-white text-sm transition-colors',
                'disabled:opacity-40 disabled:cursor-not-allowed',
                showUploadButton ? 'px-4' : 'flex-1',
              ].join(' ')}
            >
              Закрыть
            </button>
          </div>

        </div>
      </div>
    </div>
  )
}

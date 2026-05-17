'use client'

import { useCallback, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

export interface PdfPreviewProps {
  url: string
  mimeType?: string
  onPageChange?: (page: number, total: number) => void
  highlightBbox?: {
    page: number
    x: number
    y: number
    width: number
    height: number
  } | null
  className?: string
}

const ZOOM_MIN = 0.5
const ZOOM_MAX = 3.0
const ZOOM_STEP = 0.25
const ZOOM_DEFAULT = 1.0

function isPdf(url: string, mimeType?: string): boolean {
  if (mimeType === 'application/pdf') return true
  if (mimeType && mimeType !== 'application/pdf') return false
  return url.toLowerCase().includes('.pdf')
}

export default function PdfPreview({
  url,
  mimeType,
  onPageChange,
  highlightBbox,
  className,
}: PdfPreviewProps) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [zoom, setZoom] = useState(ZOOM_DEFAULT)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [containerWidth, setContainerWidth] = useState<number>(600)

  const containerRef = useRef<HTMLDivElement>(null)

  const measuredRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return
    setContainerWidth(node.offsetWidth || 600)
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setContainerWidth(entry.contentRect.width || 600)
      }
    })
    observer.observe(node)
    containerRef.current = node
    return () => observer.disconnect()
  }, [])

  function handleLoadSuccess({ numPages: total }: { numPages: number }) {
    setNumPages(total)
    setLoading(false)
    setError(null)
    onPageChange?.(currentPage, total)
  }

  function handleLoadError(err: Error) {
    setError(err.message)
    setLoading(false)
  }

  function goToPrev() {
    if (currentPage <= 1) return
    const next = currentPage - 1
    setCurrentPage(next)
    onPageChange?.(next, numPages ?? 1)
  }

  function goToNext() {
    if (numPages === null || currentPage >= numPages) return
    const next = currentPage + 1
    setCurrentPage(next)
    onPageChange?.(next, numPages)
  }

  function zoomIn() {
    setZoom((z) => Math.min(ZOOM_MAX, parseFloat((z + ZOOM_STEP).toFixed(2))))
  }

  function zoomOut() {
    setZoom((z) => Math.max(ZOOM_MIN, parseFloat((z - ZOOM_STEP).toFixed(2))))
  }

  if (!isPdf(url, mimeType)) {
    return (
      <div className={className}>
        <img src={url} alt="Оперативная карточка" className="max-w-full" />
      </div>
    )
  }

  return (
    <div className={`flex flex-col ${className ?? ''}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 rounded-t-lg border border-b-0 border-gray-200 bg-gray-50 px-4 py-2">
        {/* Pagination */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goToPrev}
            disabled={currentPage <= 1 || numPages === null}
            className="flex h-7 w-7 items-center justify-center rounded border border-gray-300 bg-white text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Предыдущая страница"
          >
            &#9664;
          </button>
          <span className="min-w-[120px] text-center text-sm text-gray-700">
            {numPages === null ? 'Загрузка...' : `Страница ${currentPage} из ${numPages}`}
          </span>
          <button
            type="button"
            onClick={goToNext}
            disabled={numPages === null || currentPage >= numPages}
            className="flex h-7 w-7 items-center justify-center rounded border border-gray-300 bg-white text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Следующая страница"
          >
            &#9654;
          </button>
        </div>

        {/* Zoom */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={zoomOut}
            disabled={zoom <= ZOOM_MIN}
            className="flex h-7 w-7 items-center justify-center rounded border border-gray-300 bg-white text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Уменьшить масштаб"
          >
            &#8722;
          </button>
          <span className="min-w-[52px] text-center text-sm text-gray-700">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={zoomIn}
            disabled={zoom >= ZOOM_MAX}
            className="flex h-7 w-7 items-center justify-center rounded border border-gray-300 bg-white text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Увеличить масштаб"
          >
            &#43;
          </button>
        </div>
      </div>

      {/* Document area */}
      <div
        ref={measuredRef}
        className="relative overflow-auto rounded-b-lg border border-gray-200 bg-gray-100"
      >
        {/* Loading overlay */}
        {loading && !error && (
          <div className="flex h-64 items-center justify-center gap-3">
            <svg
              className="h-5 w-5 animate-spin text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8z"
              />
            </svg>
            <span className="text-sm text-gray-500">Загрузка документа...</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="flex h-64 items-center justify-center">
            <p className="text-sm text-red-600">
              Не удалось загрузить документ. Проверьте подключение.
            </p>
          </div>
        )}

        {/* PDF Document */}
        {!error && (
          <Document
            file={url}
            onLoadSuccess={handleLoadSuccess}
            onLoadError={handleLoadError}
            loading=""
          >
            <div className="relative inline-block">
              <Page
                pageNumber={currentPage}
                width={containerWidth}
                scale={zoom}
                loading=""
              />

              {/* Highlight bbox overlay */}
              {highlightBbox && highlightBbox.page === currentPage && (
                <div
                  className="pointer-events-none absolute"
                  style={{
                    left: `${highlightBbox.x}%`,
                    top: `${highlightBbox.y}%`,
                    width: `${highlightBbox.width}%`,
                    height: `${highlightBbox.height}%`,
                    backgroundColor: 'rgba(234, 179, 8, 0.35)',
                    border: '1px solid rgba(234, 179, 8, 0.7)',
                  }}
                  aria-hidden="true"
                />
              )}
            </div>
          </Document>
        )}
      </div>
    </div>
  )
}

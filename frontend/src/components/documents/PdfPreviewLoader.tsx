'use client'

import dynamic from 'next/dynamic'
import type { PdfPreviewProps } from './PdfPreview'

const PdfPreview = dynamic(() => import('./PdfPreview'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg">
      <span className="text-gray-500">Загрузка PDF...</span>
    </div>
  ),
})

export default function PdfPreviewLoader(props: PdfPreviewProps) {
  return <PdfPreview {...props} />
}

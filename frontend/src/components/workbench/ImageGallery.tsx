import { useState } from 'react'
import type { ResultImage } from '../../types'
import { ResultCard } from './ResultCard'

interface Props {
  images: ResultImage[]
  previewUrls?: string[]
}

export function ImageGallery({ images, previewUrls = [] }: Props) {
  const [preview, setPreview] = useState<string | null>(null)

  // Show preview URLs while waiting for final results
  const displayImages = images.length > 0
    ? images
    : previewUrls.map(url => ({ type: 'preview', path: url }))

  if (displayImages.length === 0) return null

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {displayImages.map((img, i) => (
          <ResultCard key={i} image={img} onPreview={setPreview} />
        ))}
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPreview(null)}
        >
          <img
            src={preview}
            alt="Preview"
            className="max-h-[90vh] max-w-[90vw] rounded-xl object-contain"
          />
        </div>
      )}
    </>
  )
}

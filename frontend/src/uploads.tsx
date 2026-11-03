import { useCallback, useState } from 'react'
import { guessMime, uploadFile } from './api'

export const MAX_ATTACHMENTS = 10
const MAX_FILE_SIZE = 100 * 1024 * 1024

export interface DraftFile {
  key: string
  file: File
  previewUrl: string
  status: 'uploading' | 'ready' | 'error'
  attachmentId?: number
}

export type MediaKind = 'image' | 'audio' | 'video' | 'other'

export function mimeKind(mime: string): MediaKind {
  if (mime.startsWith('image/')) return 'image'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime.startsWith('video/')) return 'video'
  return 'other'
}

export function fileKind(file: File): MediaKind {
  return mimeKind(file.type || guessMime(file.name))
}

export const KIND_ICON: Record<MediaKind, string> = {
  image: '🖼',
  audio: '🎵',
  video: '🎬',
  other: '📄',
}

/** Черновики вложений: выбранные файлы с фоновой загрузкой по presigned URL. */
export function useUploads() {
  const [drafts, setDrafts] = useState<DraftFile[]>([])

  const addFiles = (list: FileList | null) => {
    if (!list) return
    const free = MAX_ATTACHMENTS - drafts.length
    Array.from(list)
      .slice(0, Math.max(0, free))
      .forEach(async (file) => {
        const draft: DraftFile = {
          key: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          file,
          previewUrl: URL.createObjectURL(file),
          status: 'uploading',
        }
        setDrafts((prev) => [...prev, draft])
        try {
          if (file.size > MAX_FILE_SIZE) throw new Error('файл больше 100 МБ')
          if (fileKind(file) === 'other') throw new Error('разрешены фото, аудио и видео')
          const attachmentId = await uploadFile(file)
          setDrafts((prev) =>
            prev.map((d) => (d.key === draft.key ? { ...d, status: 'ready', attachmentId } : d)),
          )
        } catch {
          setDrafts((prev) => prev.map((d) => (d.key === draft.key ? { ...d, status: 'error' } : d)))
        }
      })
  }

  const remove = useCallback((key: string) => {
    setDrafts((prev) => {
      const draft = prev.find((d) => d.key === key)
      if (draft) URL.revokeObjectURL(draft.previewUrl)
      return prev.filter((d) => d.key !== key)
    })
  }, [])

  const clear = useCallback(() => {
    setDrafts((prev) => {
      prev.forEach((d) => URL.revokeObjectURL(d.previewUrl))
      return []
    })
  }, [])

  const readyIds = drafts
    .filter((d) => d.status === 'ready' && d.attachmentId != null)
    .map((d) => d.attachmentId as number)
  const uploading = drafts.some((d) => d.status === 'uploading')

  return { drafts, addFiles, remove, clear, readyIds: () => readyIds, uploading }
}

export function DraftsView({
  drafts,
  onRemove,
}: {
  drafts: DraftFile[]
  onRemove: (key: string) => void
}) {
  if (drafts.length === 0) return null
  return (
    <div className="drafts">
      {drafts.map((d) => (
        <div key={d.key} className={`draft ${d.status}`}>
          {fileKind(d.file) === 'image' ? (
            <img src={d.previewUrl} alt={d.file.name} />
          ) : (
            <span className="draft-icon">
              {KIND_ICON[fileKind(d.file)]} {d.file.name.slice(0, 12)}
            </span>
          )}
          <span className="draft-status">
            {d.status === 'uploading' ? 'загрузка...' : d.status === 'error' ? 'ошибка' : '✓'}
          </span>
          <button className="draft-remove" onClick={() => onRemove(d.key)}>✕</button>
        </div>
      ))}
    </div>
  )
}

export interface Participant {
  token: string
  nickname: string
}

export interface Attachment {
  id: number
  file_name: string
  mime_type: string
  size: number
}

export type ReactionKind = 'like' | 'dislike'

export interface ChatMessage {
  id: number
  text: string
  author_token: string
  author_nickname: string
  reply_to_id: number | null
  quote_message_id: number | null
  quote_excerpt: string | null
  created_at: string
  edited_at: string | null
  attachments: Attachment[]
  likes: number
  dislikes: number
  my_reaction: ReactionKind | null
  /** все потомки ветки плоским списком (только у корневых в GET /api/messages) */
  replies?: ChatMessage[]
}

export interface MessagePage {
  items: ChatMessage[]
  next_cursor: number | null
}

const TOKEN_KEY = 'chat-anon-token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(
    public status: number,
    body: string,
  ) {
    super(`HTTP ${status}: ${body}`)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['X-Participant-Token'] = token
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) throw new ApiError(response.status, await response.text())
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export interface SendMessagePayload {
  text: string
  reply_to_id?: number
  quote_message_id?: number
  quote_excerpt?: string
  attachment_ids?: number[]
}

export interface UpdateMessagePayload {
  text: string
  attachment_ids: number[]
}

export interface PresignResponse {
  attachment_id: number
  upload_url: string
}

// тип файла, если браузер не определил MIME (по расширению, белый список бэкенда)
const MIME_BY_EXT: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  webp: 'image/webp',
  bmp: 'image/bmp',
  mp3: 'audio/mpeg',
  ogg: 'audio/ogg',
  wav: 'audio/wav',
  m4a: 'audio/mp4',
  aac: 'audio/aac',
  flac: 'audio/flac',
  mp4: 'video/mp4',
  webm: 'video/webm',
  mov: 'video/quicktime',
  mkv: 'video/x-matroska',
  avi: 'video/x-msvideo',
}

export function guessMime(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return MIME_BY_EXT[ext] ?? 'application/octet-stream'
}

export const api = {
  register: (email: string, nickname?: string) =>
    request<Participant>('/api/participants', {
      method: 'POST',
      body: JSON.stringify({ email: email.trim(), nickname: nickname?.trim() || null }),
    }),
  me: () => request<Participant>('/api/participants/me'),
  updateMe: (nickname: string) =>
    request<Participant>('/api/participants/me', {
      method: 'PATCH',
      body: JSON.stringify({ nickname }),
    }),
  listMessages: (beforeId?: number, limit = 50) =>
    request<MessagePage>(`/api/messages?limit=${limit}${beforeId != null ? `&before_id=${beforeId}` : ''}`),
  sendMessage: (payload: SendMessagePayload) =>
    request<ChatMessage>('/api/messages', { method: 'POST', body: JSON.stringify(payload) }),
  updateMessage: (messageId: number, payload: UpdateMessagePayload) =>
    request<ChatMessage>(`/api/messages/${messageId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteMessage: (messageId: number) =>
    request<void>(`/api/messages/${messageId}`, { method: 'DELETE' }),
  setReaction: (messageId: number, kind: ReactionKind) =>
    request<ChatMessage>(`/api/messages/${messageId}/reactions`, {
      method: 'POST',
      body: JSON.stringify({ kind }),
    }),
  removeReaction: (messageId: number) =>
    request<ChatMessage>(`/api/messages/${messageId}/reactions/me`, { method: 'DELETE' }),
  presign: (meta: { file_name: string; mime_type: string; size: number }) =>
    request<PresignResponse>('/api/uploads/presign', { method: 'POST', body: JSON.stringify(meta) }),
}

/** Прямая загрузка файла по presigned URL (в MinIO через прокси Vite). Возвращает attachment_id. */
export async function uploadFile(file: File): Promise<number> {
  const mime = file.type || guessMime(file.name)
  const { attachment_id, upload_url } = await api.presign({
    file_name: file.name,
    mime_type: mime,
    size: file.size,
  })
  const response = await fetch(upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': mime } })
  if (!response.ok) throw new ApiError(response.status, await response.text())
  return attachment_id
}

/** URL отдачи вложения: inline (превью/плеер) или скачивание. */
export function attachmentUrl(id: number, download = false): string {
  return `/api/attachments/${id}/file${download ? '?download=true' : ''}`
}

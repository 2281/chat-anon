import { useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../api'
import { DraftsView, useUploads } from '../uploads'

interface Props {
  replyTo: ChatMessage | null
  quote: { message: ChatMessage; excerpt: string } | null
  onCancelReply: () => void
  onCancelQuote: () => void
  onSend: (text: string, attachmentIds: number[]) => Promise<void>
}

const EMOJIS = ['😀', '😂', '😍', '😮', '😢', '🔥', '👍', '👎', '🎉', '💀']

export function Composer({ replyTo, quote, onCancelReply, onCancelQuote, onSend }: Props) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [showEmoji, setShowEmoji] = useState(false)
  const uploads = useUploads()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // по умолчанию фокус всегда в поле ввода: при входе в чат
  // и при выборе «ответить»/цитирования — можно сразу печатать
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])
  useEffect(() => {
    if (replyTo || quote) textareaRef.current?.focus()
  }, [replyTo, quote])

  const canSend =
    (text.trim().length > 0 || uploads.readyIds.length > 0) && !uploads.uploading

  const send = async () => {
    if (!canSend || sending) return
    setSending(true)
    try {
      await onSend(text.trim(), uploads.readyIds())
      setText('')
      uploads.clear()
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }

  const insertEmoji = (emoji: string) => {
    const el = textareaRef.current
    if (!el) {
      setText((t) => t + emoji)
      return
    }
    const start = el.selectionStart ?? text.length
    const end = el.selectionEnd ?? text.length
    setText(text.slice(0, start) + emoji + text.slice(end))
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(start + emoji.length, start + emoji.length)
    })
  }

  return (
    <div className="composer">
      {(replyTo || quote) && (
        <div className="composer-context">
          {replyTo && (
            <span className="chip">
              ↪ ответ для {replyTo.author_nickname} (#{replyTo.id})
              <button onClick={onCancelReply}>✕</button>
            </span>
          )}
          {quote && (
            <span className="chip" title={quote.excerpt}>
              «{quote.excerpt.slice(0, 60)}{quote.excerpt.length > 60 ? '…' : ''}»
              <button onClick={onCancelQuote}>✕</button>
            </span>
          )}
        </div>
      )}
      <DraftsView drafts={uploads.drafts} onRemove={uploads.remove} />
      {showEmoji && (
        <div className="emoji-row">
          {EMOJIS.map((e) => (
            <button key={e} onClick={() => insertEmoji(e)}>{e}</button>
          ))}
        </div>
      )}
      <div className="composer-row">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,audio/*,video/*"
          style={{ display: 'none' }}
          onChange={(e) => {
            uploads.addFiles(e.target.files)
            e.target.value = ''
          }}
        />
        <button
          className="px-btn icon"
          title="прикрепить фото, аудио или видео"
          onClick={() => fileInputRef.current?.click()}
        >
          📎
        </button>
        <button
          className={showEmoji ? 'px-btn icon active' : 'px-btn icon'}
          title="эмодзи"
          onClick={() => setShowEmoji((v) => !v)}
        >
          ☺
        </button>
        <textarea
          ref={textareaRef}
          value={text}
          placeholder="сообщение... (Enter — отправить, Shift+Enter — новая строка)"
          rows={2}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
        />
        <button className="px-btn primary" onClick={send} disabled={sending || !canSend}>
          {sending ? '...' : '➤'}
        </button>
      </div>
    </div>
  )
}

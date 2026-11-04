import { useEffect, useRef, useState } from 'react'
import type { Attachment, ChatMessage } from '../api'
import { attachmentUrl } from '../api'
import { DraftsView, KIND_ICON, mimeKind, useUploads } from '../uploads'

interface Props {
  message: ChatMessage
  own: boolean
  replyAuthor?: string
  /** без onReply кнопка «ответ» скрыта (личные диалоги — плоская лента) */
  onReply?: () => void
  /** кнопка «✉ в лс» рядом с ником (общая лента, чужие сообщения) */
  onStartDm?: () => void
  onReaction: (kind: 'like' | 'dislike') => void
  onDelete: () => Promise<void>
  onEdit: (message: ChatMessage, text: string, attachmentIds: number[]) => Promise<void>
}

function AttachmentView({ attachment }: { attachment: Attachment }) {
  const [full, setFull] = useState(false)
  const url = attachmentUrl(attachment.id)
  const kind = mimeKind(attachment.mime_type)

  return (
    <div className="attachment">
      {kind === 'image' && (
        <img
          className="attachment-image"
          src={url}
          alt={attachment.file_name}
          loading="lazy"
          onClick={() => setFull(true)}
          title="нажмите, чтобы открыть в полном размере"
        />
      )}
      {kind === 'audio' && <audio controls preload="metadata" src={url} />}
      {kind === 'video' && (
        <video controls preload="metadata" className="attachment-video" src={url} />
      )}
      <div className="attachment-meta">
        <span className="attachment-name" title={attachment.file_name}>
          {attachment.file_name}
        </span>
        {kind === 'image' && (
          <button className="px-btn mini" onClick={() => setFull(true)} title="в полном размере">
            ⤢
          </button>
        )}
        <a
          className="px-btn mini"
          href={attachmentUrl(attachment.id, true)}
          title="скачать"
        >
          ⬇
        </a>
      </div>
      {full && (
        <div className="image-modal" onClick={() => setFull(false)}>
          <img src={url} alt={attachment.file_name} />
          <div className="modal-bar">
            <span>{attachment.file_name}</span>
            <a
              href={attachmentUrl(attachment.id, true)}
              onClick={(e) => e.stopPropagation()}
            >
              ⬇ скачать
            </a>
            <span>клик — закрыть</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function MessageItem({ message: m, own, replyAuthor, onReply, onStartDm, onReaction, onDelete, onEdit }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [keptAttachments, setKeptAttachments] = useState<Attachment[]>([])
  const [saving, setSaving] = useState(false)
  const uploads = useUploads()
  const editFileRef = useRef<HTMLInputElement>(null)
  const time = new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  // двухшаговое подтверждение удаления самосбрасывается через 3 секунды
  useEffect(() => {
    if (!confirming) return
    const timer = window.setTimeout(() => setConfirming(false), 3000)
    return () => window.clearTimeout(timer)
  }, [confirming])

  const startEdit = () => {
    setEditText(m.text)
    setKeptAttachments(m.attachments)
    uploads.clear()
    setEditing(true)
  }

  const cancelEdit = () => {
    uploads.clear()
    setEditing(false)
  }

  const canSave =
    !uploads.uploading &&
    (editText.trim().length > 0 || keptAttachments.length > 0 || uploads.readyIds.length > 0)

  const save = async () => {
    if (!canSave || saving) return
    setSaving(true)
    try {
      await onEdit(m, editText.trim(), [
        ...keptAttachments.map((a) => a.id),
        ...uploads.readyIds(),
      ])
      uploads.clear()
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <article className={own ? 'message own' : 'message'}>
      <header className="message-head">
        <span className="nickname">{m.author_nickname}</span>
        {own && <span className="you-tag">вы</span>}
        {onStartDm && !own && (
          <button className="px-btn mini" title="написать в личные сообщения" onClick={onStartDm}>
            ✉ в лс
          </button>
        )}
        <span className="time">{time}</span>
        {m.edited_at && !editing && <span className="edited-tag" title="сообщение изменено">изм.</span>}
      </header>

      {editing ? (
        <div className="editor">
          <textarea
            className="pixel-input"
            value={editText}
            rows={3}
            autoFocus
            placeholder="текст сообщения..."
            onChange={(e) => setEditText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                save()
              } else if (e.key === 'Escape') {
                cancelEdit()
              }
            }}
          />
          {keptAttachments.length > 0 && (
            <div className="drafts">
              {keptAttachments.map((a) => (
                <div key={a.id} className="draft kept">
                  {mimeKind(a.mime_type) === 'image' ? (
                    <img src={attachmentUrl(a.id)} alt={a.file_name} />
                  ) : (
                    <span className="draft-icon">
                      {KIND_ICON[mimeKind(a.mime_type)]} {a.file_name.slice(0, 12)}
                    </span>
                  )}
                  <button
                    className="draft-remove"
                    title="убрать файл"
                    onClick={() => setKeptAttachments((prev) => prev.filter((x) => x.id !== a.id))}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
          <DraftsView drafts={uploads.drafts} onRemove={uploads.remove} />
          <div className="editor-actions">
            <input
              ref={editFileRef}
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
              title="прикрепить файл"
              onClick={() => editFileRef.current?.click()}
            >
              📎
            </button>
            <button className="px-btn primary" onClick={save} disabled={!canSave || saving}>
              {saving ? '...' : '✓ сохранить'}
            </button>
            <button className="px-btn" onClick={cancelEdit}>отмена</button>
          </div>
        </div>
      ) : (
        <>
          {m.quote_excerpt && <blockquote className="quote">«{m.quote_excerpt}»</blockquote>}
          {m.reply_to_id != null && (
            <div className="reply-ref">↪ ответ для {replyAuthor ?? `#${m.reply_to_id}`}</div>
          )}
          {m.text && (
            <div className="message-text" data-message-id={m.id}>
              {m.text}
            </div>
          )}
          {m.attachments.map((a) => (
            <AttachmentView key={a.id} attachment={a} />
          ))}
          <footer className="message-actions">
            <button
              className={m.my_reaction === 'like' ? 'px-btn reaction liked' : 'px-btn reaction'}
              onClick={() => onReaction('like')}
            >
              👍 {m.likes}
            </button>
            <button
              className={m.my_reaction === 'dislike' ? 'px-btn reaction disliked' : 'px-btn reaction'}
              onClick={() => onReaction('dislike')}
            >
              👎 {m.dislikes}
            </button>
            {onReply && <button className="px-btn" onClick={onReply}>↪ ответ</button>}
            {own &&
              (confirming ? (
                <button className="px-btn danger" onClick={() => onDelete()}>
                  точно удалить?
                </button>
              ) : (
                <button className="px-btn" title="удалить сообщение" onClick={() => setConfirming(true)}>
                  🗑
                </button>
              ))}
            {own && (
              <button className="px-btn" title="редактировать сообщение" onClick={startEdit}>
                ✏️
              </button>
            )}
          </footer>
        </>
      )}
    </article>
  )
}

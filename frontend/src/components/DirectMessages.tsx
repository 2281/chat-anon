import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessage, ConversationSummary, Participant, ReactionKind } from '../api'
import { api } from '../api'
import { Composer } from './Composer'
import { MessageItem } from './MessageItem'

const PAGE_SIZE = 50

/** Обработчик WS-событий лички, которым App делится с открытым диалогом */
export type DmWsHandler = (event: string, data: unknown) => void

/** Обрезок последнего сообщения для строки списка диалогов */
function excerpt(c: ConversationSummary): string {
  const last = c.last_message
  if (!last) return 'сообщений пока нет'
  return last.text || '📎 вложение'
}

export function DmList({
  conversations,
  onOpen,
  onBack,
}: {
  conversations: ConversationSummary[]
  onOpen: (c: ConversationSummary) => void
  onBack: () => void
}) {
  return (
    <div className="dm-screen">
      <div className="dm-head">
        <button className="px-btn" onClick={onBack}>← в общий чат</button>
        <span className="dm-title">личные сообщения</span>
      </div>
      <div className="dm-list">
        {conversations.length === 0 && (
          <div className="empty">
            диалогов пока нет — нажми «✉ в лс» у чужого сообщения в общем чате
          </div>
        )}
        {conversations.map((c) => (
          <button key={c.id} className="dm-item" onClick={() => onOpen(c)}>
            <span className="dm-peer">{c.peer_nickname}</span>
            <span className="dm-excerpt">{excerpt(c)}</span>
            {c.unread_count > 0 && <span className="notif-badge">{c.unread_count}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

export function DmChat({
  me,
  conversation,
  jumpToId,
  onJumpHandled,
  onBack,
  onRead,
  registerHandler,
}: {
  me: Participant
  conversation: ConversationSummary
  /** переход из поиска: догрузить историю до сообщения и подсветить его */
  jumpToId?: number | null
  onJumpHandled?: () => void
  onBack: () => void
  /** диалог прочитан — обнулить его бейдж в шапке */
  onRead: (conversationId: number) => void
  /** подписка на dm.* события, пока диалог открыт */
  registerHandler: (fn: DmWsHandler | null) => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]) // от старых к новым
  const [nextCursor, setNextCursor] = useState<number | null>(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)
  const conversationIdRef = useRef(conversation.id)
  conversationIdRef.current = conversation.id

  const scrollToBottom = (smooth = false) => {
    const el = listRef.current
    el?.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  }

  const mergeMessage = useCallback((m: ChatMessage) => {
    setMessages((prev) => {
      const index = prev.findIndex((x) => x.id === m.id)
      if (index === -1) return [...prev, m]
      const updated = [...prev]
      updated[index] = { ...m, my_reaction: m.my_reaction ?? prev[index].my_reaction }
      return updated
    })
  }, [])

  const removeMessage = useCallback((messageId: number) => {
    setMessages((prev) => prev.filter((x) => x.id !== messageId))
  }, [])

  const updateReactionCounts = useCallback(
    (messageId: number, likes: number, dislikes: number) => {
      setMessages((prev) => prev.map((x) => (x.id === messageId ? { ...x, likes, dislikes } : x)))
    },
    [],
  )

  const markRead = useCallback(
    (lastMessageId: number) => {
      if (lastMessageId <= 0) return
      api.markConversationRead(conversationIdRef.current, lastMessageId).catch(() => {})
      onRead(conversationIdRef.current)
    },
    [onRead],
  )

  // начальная загрузка истории диалога; при переходе из поиска (jumpToId)
  // догружаем страницы, пока целевое сообщение не окажется в списке
  useEffect(() => {
    ;(async () => {
      try {
        const page = await api.listDmMessages(conversation.id)
        let items = [...page.items].reverse() // API отдаёт от новых — разворачиваем
        let cursor = page.next_cursor
        while (jumpToId != null && !items.some((m) => m.id === jumpToId) && cursor != null) {
          const older = await api.listDmMessages(conversation.id, cursor, PAGE_SIZE)
          items = [...[...older.items].reverse(), ...items]
          cursor = older.next_cursor
        }
        setMessages(items)
        setNextCursor(cursor)
        if (items.length > 0) markRead(items[items.length - 1].id)
        requestAnimationFrame(() => {
          const target = jumpToId != null ? document.getElementById(`msg-${jumpToId}`) : null
          if (target) {
            target.scrollIntoView({ block: 'center', behavior: 'smooth' })
            target.classList.add('flash')
            window.setTimeout(() => target.classList.remove('flash'), 2000)
          } else {
            scrollToBottom()
          }
          onJumpHandled?.()
        })
      } catch (e) {
        setError(String(e))
      }
    })()
    // jumpToId намеренно не в зависимостях: переход обрабатывается при открытии диалога
    // (App перемонтирует компонент ключом при новом переходе из поиска)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation.id, markRead])

  // подписка на события своего диалога, пока он открыт
  useEffect(() => {
    const handler: DmWsHandler = (event, data) => {
      if (event === 'dm.new' || event === 'dm.updated') {
        const m = data as ChatMessage & { conversation_id: number }
        if (m.conversation_id !== conversationIdRef.current) return
        mergeMessage(m)
        if (event === 'dm.new') {
          if (m.author_token !== me.token) markRead(m.id)
          if (stickToBottom.current) requestAnimationFrame(() => scrollToBottom(true))
        }
      } else if (event === 'dm.deleted') {
        const d = data as { conversation_id: number; message_id: number }
        if (d.conversation_id !== conversationIdRef.current) return
        removeMessage(d.message_id)
      } else if (event === 'dm.reaction') {
        const d = data as { conversation_id: number; message_id: number; likes: number; dislikes: number }
        if (d.conversation_id !== conversationIdRef.current) return
        updateReactionCounts(d.message_id, d.likes, d.dislikes)
      }
    }
    registerHandler(handler)
    return () => registerHandler(null)
  }, [me.token, mergeMessage, removeMessage, updateReactionCounts, markRead, registerHandler])

  const loadOlder = async () => {
    if (nextCursor == null || loadingOlder) return
    setLoadingOlder(true)
    const el = listRef.current
    const prevHeight = el?.scrollHeight ?? 0
    try {
      const page = await api.listDmMessages(conversation.id, nextCursor, PAGE_SIZE)
      setMessages((prev) => [...[...page.items].reverse(), ...prev])
      setNextCursor(page.next_cursor)
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - prevHeight
      })
    } finally {
      setLoadingOlder(false)
    }
  }

  const handleScroll = () => {
    const el = listRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  const handleSend = async (text: string, attachmentIds: number[]) => {
    const payload: { text: string; attachment_ids?: number[] } = { text }
    if (attachmentIds.length > 0) payload.attachment_ids = attachmentIds
    const created = await api.sendDm(conversation.id, payload)
    mergeMessage(created)
    stickToBottom.current = true
    requestAnimationFrame(() => scrollToBottom(true))
  }

  const handleReaction = async (message: ChatMessage, kind: ReactionKind) => {
    const updated =
      message.my_reaction === kind
        ? await api.removeReaction(message.id)
        : await api.setReaction(message.id, kind)
    mergeMessage(updated)
  }

  const handleDelete = async (message: ChatMessage) => {
    await api.deleteMessage(message.id)
    removeMessage(message.id)
  }

  const handleEdit = async (message: ChatMessage, text: string, attachmentIds: number[]) => {
    const updated = await api.updateMessage(message.id, { text, attachment_ids: attachmentIds })
    mergeMessage(updated)
  }

  return (
    <div className="dm-screen">
      <div className="dm-head">
        <button className="px-btn" onClick={onBack}>← к диалогам</button>
        <span className="dm-title">✉ {conversation.peer_nickname}</span>
      </div>
      {error && <div className="empty">ошибка: {error}</div>}
      <div className="message-list" ref={listRef} onScroll={handleScroll}>
        {nextCursor != null && (
          <button className="px-btn load-older" onClick={loadOlder} disabled={loadingOlder}>
            {loadingOlder ? 'загрузка...' : '↑ загрузить ранее'}
          </button>
        )}
        {messages.map((m) => (
          <div key={m.id} id={`msg-${m.id}`} className="thread-root">
            <MessageItem
              message={m}
              own={m.author_token === me.token}
              onReaction={(kind) => handleReaction(m, kind)}
              onDelete={() => handleDelete(m)}
              onEdit={handleEdit}
            />
          </div>
        ))}
        {messages.length === 0 && (
          <div className="empty">пока пусто — напиши первое сообщение!</div>
        )}
      </div>
      <Composer
        replyTo={null}
        quote={null}
        onCancelReply={() => {}}
        onCancelQuote={() => {}}
        onSend={handleSend}
      />
    </div>
  )
}

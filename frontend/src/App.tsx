import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react'
import type { ChatMessage, Participant, ReactionKind } from './api'
import { api, clearToken, getToken, setToken } from './api'
import { connectChatWs } from './ws'
import { ChatHeader } from './components/ChatHeader'
import { Composer } from './components/Composer'
import { MessageItem } from './components/MessageItem'
import { StartScreen } from './components/StartScreen'

const PAGE_SIZE = 50

// страница API: корневые сообщения + их ветки (replies) — в плоский список для стейта
const flattenPage = (items: ChatMessage[]): ChatMessage[] =>
  items.flatMap((m) => [m, ...(m.replies ?? [])])

export default function App() {
  const [booting, setBooting] = useState(true)
  const [me, setMe] = useState<Participant | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([]) // от старых к новым
  const [nextCursor, setNextCursor] = useState<number | null>(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [replyTo, setReplyTo] = useState<ChatMessage | null>(null)
  const [quote, setQuote] = useState<{ message: ChatMessage; excerpt: string } | null>(null)

  const listRef = useRef<HTMLDivElement>(null)
  const knownIds = useRef(new Set<number>())
  const stickToBottom = useRef(true)
  const lastIdRef = useRef<number | null>(null)
  const messagesRef = useRef(messages)
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  const scrollToBottom = (smooth = false) => {
    const el = listRef.current
    el?.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  }

  // слияние сообщения в ленту: обновление существующего или добавление нового
  const mergeMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => {
      const index = prev.findIndex((x) => x.id === message.id)
      if (index === -1) {
        knownIds.current.add(message.id)
        return [...prev, message]
      }
      const updated = [...prev]
      updated[index] = { ...message, my_reaction: message.my_reaction ?? prev[index].my_reaction }
      return updated
    })
  }, [])

  const removeMessage = useCallback((messageId: number) => {
    setMessages((prev) => prev.filter((x) => x.id !== messageId))
    knownIds.current.delete(messageId)
  }, [])

  const updateReactionCounts = useCallback(
    (messageId: number, likes: number, dislikes: number) => {
      setMessages((prev) =>
        prev.map((x) => (x.id === messageId ? { ...x, likes, dislikes } : x)),
      )
    },
    [],
  )

  const loadInitial = useCallback(async () => {
    const page = await api.listMessages(undefined, PAGE_SIZE)
    const items = flattenPage(page.items)
    knownIds.current = new Set(items.map((m) => m.id))
    setMessages(items)
    setNextCursor(page.next_cursor)
    lastIdRef.current = items.reduce((max, m) => Math.max(max, m.id), 0)
    requestAnimationFrame(() => scrollToBottom())
  }, [])

  const loadOlder = async () => {
    if (nextCursor == null || loadingOlder) return
    setLoadingOlder(true)
    const el = listRef.current
    const prevHeight = el?.scrollHeight ?? 0
    try {
      const page = await api.listMessages(nextCursor, PAGE_SIZE)
      const older = flattenPage(page.items)
      older.forEach((m) => knownIds.current.add(m.id))
      setMessages((prev) => [...older, ...prev])
      setNextCursor(page.next_cursor)
      // сохранить позицию прокрутки после добавления блока сверху
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - prevHeight
      })
    } finally {
      setLoadingOlder(false)
    }
  }

  // восстановление сессии при старте
  useEffect(() => {
    ;(async () => {
      if (getToken()) {
        try {
          setMe(await api.me())
        } catch {
          clearToken()
        }
      }
      setBooting(false)
    })()
  }, [])

  // начальная загрузка + WebSocket после входа
  useEffect(() => {
    if (!me) return
    loadInitial().catch((e) => setError(String(e)))
    const close = connectChatWs(
      (event, data) => {
        if (event === 'message.new') {
          mergeMessage(data as ChatMessage)
        } else if (event === 'message.reaction') {
          const d = data as { message_id: number; likes: number; dislikes: number }
          updateReactionCounts(d.message_id, d.likes, d.dislikes)
        } else if (event === 'message.deleted') {
          removeMessage((data as { message_id: number }).message_id)
        } else if (event === 'message.updated') {
          mergeMessage(data as ChatMessage)
        }
      },
      setConnected,
    )
    return close
  }, [me, loadInitial, mergeMessage, updateReactionCounts, removeMessage])

  // автопрокрутка к новым сообщениям (включая ответы в ветках), если пользователь у нижнего края
  const maxId = messages.reduce((max, m) => Math.max(max, m.id), 0)
  useEffect(() => {
    if (maxId !== lastIdRef.current) {
      if (lastIdRef.current !== null && lastIdRef.current !== 0 && stickToBottom.current) {
        scrollToBottom(true)
      }
      lastIdRef.current = maxId
    }
  }, [maxId])

  const handleScroll = () => {
    const el = listRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  const handleEnter = async (email: string, nickname: string) => {
    setError(null)
    try {
      const participant = await api.register(email, nickname)
      setToken(participant.token)
      setMe(participant)
    } catch (e) {
      setError(`не удалось войти: ${String(e)}`)
    }
  }

  const handleLogout = () => {
    clearToken()
    location.reload()
  }

  const handleSend = async (text: string, attachmentIds: number[]) => {
    const payload: {
      text: string
      reply_to_id?: number
      quote_message_id?: number
      quote_excerpt?: string
      attachment_ids?: number[]
    } = { text }
    if (replyTo) payload.reply_to_id = replyTo.id
    if (quote) {
      payload.quote_message_id = quote.message.id
      payload.quote_excerpt = quote.excerpt
    }
    if (attachmentIds.length > 0) payload.attachment_ids = attachmentIds
    const created = await api.sendMessage(payload)
    mergeMessage(created)
    setReplyTo(null)
    setQuote(null)
    stickToBottom.current = true
  }

  // повторный клик по своей активной реакции снимает её
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

  // цитирование выделенного фрагмента текста сообщения
  const handleListMouseUp = (e: ReactMouseEvent) => {
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed) return
    const selectedText = selection.toString().trim()
    const container = (e.target as HTMLElement).closest('[data-message-id]')
    if (!selectedText || !container) return
    const id = Number(container.getAttribute('data-message-id'))
    const message = messagesRef.current.find((m) => m.id === id)
    if (message) {
      setQuote({ message, excerpt: selectedText.slice(0, 300) })
      selection.removeAllRanges()
    }
  }

  const nicknameById = useMemo(() => {
    const map = new Map<number, string>()
    messages.forEach((m) => map.set(m.id, m.author_nickname))
    return map
  }, [messages])

  // дерево веток: корни — сообщения без родителя в загруженном наборе,
  // остальные группируются по reply_to_id (ответ на ответ крепится к своему родителю)
  const { roots, childrenByParent } = useMemo(() => {
    const ids = new Set(messages.map((m) => m.id))
    const roots: ChatMessage[] = []
    const childrenByParent = new Map<number, ChatMessage[]>()
    for (const m of messages) {
      if (m.reply_to_id != null && ids.has(m.reply_to_id)) {
        const list = childrenByParent.get(m.reply_to_id) ?? []
        list.push(m)
        childrenByParent.set(m.reply_to_id, list)
      } else {
        roots.push(m)
      }
    }
    roots.sort((a, b) => a.id - b.id)
    childrenByParent.forEach((list) => list.sort((a, b) => a.id - b.id))
    return { roots, childrenByParent }
  }, [messages])

  const renderThread = (m: ChatMessage, depth: number): ReactNode => (
    <div key={m.id} className={depth === 0 ? 'thread-root' : depth < 6 ? 'thread-node' : 'thread-node no-indent'}>
      <MessageItem
        message={m}
        own={m.author_token === me!.token}
        replyAuthor={m.reply_to_id != null ? nicknameById.get(m.reply_to_id) : undefined}
        onReply={() => setReplyTo(m)}
        onReaction={(kind) => handleReaction(m, kind)}
        onDelete={() => handleDelete(m)}
        onEdit={handleEdit}
      />
      {(childrenByParent.get(m.id) ?? []).map((child) => renderThread(child, depth + 1))}
    </div>
  )

  if (booting) return <div className="boot">загрузка...</div>
  if (!me) return <StartScreen onEnter={handleEnter} error={error} />

  return (
    <div className="app">
      <ChatHeader me={me} connected={connected} onLogout={handleLogout} />
      <div className="message-list" ref={listRef} onScroll={handleScroll} onMouseUp={handleListMouseUp}>
        {nextCursor != null && (
          <button className="px-btn load-older" onClick={loadOlder} disabled={loadingOlder}>
            {loadingOlder ? 'загрузка...' : '↑ загрузить ранее'}
          </button>
        )}
        {roots.map((m) => renderThread(m, 0))}
        {roots.length === 0 && (
          <div className="empty">пока пусто — напиши первое сообщение!</div>
        )}
      </div>
      <Composer
        replyTo={replyTo}
        quote={quote}
        onCancelReply={() => setReplyTo(null)}
        onCancelQuote={() => setQuote(null)}
        onSend={handleSend}
      />
    </div>
  )
}

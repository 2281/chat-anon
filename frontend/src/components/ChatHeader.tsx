import { useEffect, useRef, useState } from 'react'
import type { AppNotification, Participant, SearchHit } from '../api'
import { api } from '../api'

interface Props {
  me: Participant
  connected: boolean
  notifications: AppNotification[]
  unreadCount: number
  dmUnread: number
  onOpenNotification: (n: AppNotification) => void
  onOpenDmList: () => void
  onOpenSearchHit: (hit: SearchHit) => void
  onLogout: () => void
}

export function ChatHeader({ me, connected, notifications, unreadCount, dmUnread, onOpenNotification, onOpenDmList, onOpenSearchHit, onLogout }: Props) {
  const [editing, setEditing] = useState(false)
  const [nickname, setNickname] = useState(me.nickname)
  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [searching, setSearching] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  // закрытие выпадающих панелей по клику вне их
  useEffect(() => {
    if (!notifOpen) return
    const close = (e: MouseEvent) => {
      if (!notifRef.current?.contains(e.target as Node)) setNotifOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [notifOpen])

  useEffect(() => {
    if (hits === null) return
    const close = (e: MouseEvent) => {
      if (!searchRef.current?.contains(e.target as Node)) setHits(null)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [hits])

  const runSearch = async () => {
    const q = query.trim()
    if (!q || searching) return
    setSearching(true)
    try {
      const results = await api.searchMessages(q)
      setHits(results.items)
    } catch {
      setHits([])
    } finally {
      setSearching(false)
    }
  }

  const save = async () => {
    const trimmed = nickname.trim()
    if (trimmed && trimmed !== me.nickname) {
      await api.updateMe(trimmed)
    }
    setEditing(false)
  }

  return (
    <header className="chat-header">
      <h1 className="logo">chat-anon</h1>
      <div className="search-wrap" ref={searchRef}>
        <input
          className="pixel-input small search-input"
          value={query}
          placeholder="поиск по чату..."
          maxLength={200}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runSearch()}
        />
        <button className="px-btn" title="искать" onClick={runSearch} disabled={searching}>
          {searching ? '...' : '🔍'}
        </button>
        {hits !== null && (
          <div className="notif-panel search-panel">
            {hits.length === 0 && <div className="notif-empty">ничего не найдено</div>}
            {hits.map((h) => (
              <button
                key={`${h.conversation_id ?? 'feed'}-${h.message.id}`}
                className="notif-item"
                onClick={() => {
                  setHits(null)
                  onOpenSearchHit(h)
                }}
              >
                <span className="notif-head">
                  <b>
                    {h.conversation_id != null ? '✉ личка' : '# общий'} · {h.message.author_nickname}
                  </b>
                  <span className="notif-time">
                    {new Date(h.message.created_at).toLocaleString([], {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </span>
                <span className="notif-excerpt">
                  {h.message.text || '📎 вложение'}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="header-right">
        <span
          className={connected ? 'conn ok' : 'conn bad'}
          title={connected ? 'соединение установлено' : 'переподключение...'}
        >
          {connected ? '●' : '○'}
        </span>
        <div className="notif-wrap" ref={notifRef}>
          <button
            className="px-btn notif-bell"
            title="уведомления"
            onClick={() => setNotifOpen((v) => !v)}
          >
            🔔
            {unreadCount > 0 && <span className="notif-badge">{unreadCount}</span>}
          </button>
          {notifOpen && (
            <div className="notif-panel">
              {notifications.length === 0 && (
                <div className="notif-empty">уведомлений пока нет</div>
              )}
              {notifications.map((n) => (
                <button
                  key={n.id}
                  className={n.is_read ? 'notif-item' : 'notif-item unread'}
                  onClick={() => {
                    setNotifOpen(false)
                    onOpenNotification(n)
                  }}
                >
                  <span className="notif-head">
                    <b>
                      {n.kind === 'reply'
                        ? n.actor_nickname
                        : `${n.actor_nickname} оценил сообщение ${n.kind === 'like' ? '👍' : '👎'}`}
                    </b>
                    <span className="notif-time">
                      {new Date(n.created_at).toLocaleString([], {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </span>
                  <span className="notif-excerpt">{n.excerpt}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="px-btn notif-bell" title="личные сообщения" onClick={onOpenDmList}>
          ✉
          {dmUnread > 0 && <span className="notif-badge">{dmUnread}</span>}
        </button>
        {editing ? (
          <>
            <input
              className="pixel-input small"
              value={nickname}
              maxLength={64}
              onChange={(e) => setNickname(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && save()}
            />
            <button className="px-btn" onClick={save}>ok</button>
          </>
        ) : (
          <button className="px-btn" title="сменить никнейм" onClick={() => setEditing(true)}>
            {me.nickname}
          </button>
        )}
        <button className="px-btn" onClick={onLogout}>выйти</button>
      </div>
    </header>
  )
}

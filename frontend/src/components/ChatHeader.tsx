import { useEffect, useRef, useState } from 'react'
import type { AppNotification, Participant } from '../api'
import { api } from '../api'

interface Props {
  me: Participant
  connected: boolean
  notifications: AppNotification[]
  unreadCount: number
  onOpenNotification: (n: AppNotification) => void
  onLogout: () => void
}

export function ChatHeader({ me, connected, notifications, unreadCount, onOpenNotification, onLogout }: Props) {
  const [editing, setEditing] = useState(false)
  const [nickname, setNickname] = useState(me.nickname)
  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)

  // закрытие выпадающего списка уведомлений по клику вне его
  useEffect(() => {
    if (!notifOpen) return
    const close = (e: MouseEvent) => {
      if (!notifRef.current?.contains(e.target as Node)) setNotifOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [notifOpen])

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

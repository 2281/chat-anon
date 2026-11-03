import { useState } from 'react'
import type { Participant } from '../api'
import { api } from '../api'

interface Props {
  me: Participant
  connected: boolean
  onLogout: () => void
}

export function ChatHeader({ me, connected, onLogout }: Props) {
  const [editing, setEditing] = useState(false)
  const [nickname, setNickname] = useState(me.nickname)

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

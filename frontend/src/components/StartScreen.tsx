import { useState } from 'react'

interface Props {
  onEnter: (nickname: string) => void
  error: string | null
}

export function StartScreen({ onEnter, error }: Props) {
  const [nickname, setNickname] = useState('')

  return (
    <div className="start-screen">
      <div className="start-panel">
        <h1 className="logo">chat-anon</h1>
        <p className="start-hint">анонимный чат без регистрации</p>
        <input
          className="pixel-input"
          value={nickname}
          placeholder="никнейм (необязательно)"
          maxLength={64}
          onChange={(e) => setNickname(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onEnter(nickname)}
        />
        <button className="px-btn primary big" onClick={() => onEnter(nickname)}>
          войти в чат
        </button>
        {error && <p className="error-text">{error}</p>}
      </div>
    </div>
  )
}

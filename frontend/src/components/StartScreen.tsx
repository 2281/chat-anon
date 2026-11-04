import { useState } from 'react'

interface Props {
  onEnter: (email: string, nickname: string) => void
  error: string | null
}

export function StartScreen({ onEnter, error }: Props) {
  const [email, setEmail] = useState('')
  const [nickname, setNickname] = useState('')

  const submit = () => {
    if (email.trim()) onEnter(email, nickname)
  }

  return (
    <div className="start-screen">
      <div className="start-panel">
        <h1 className="logo">chat-anon</h1>
        <p className="start-hint">анонимный чат: вход по email, без пароля</p>
        <input
          className="pixel-input"
          type="email"
          value={email}
          placeholder="email (обязательно)"
          maxLength={255}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        <input
          className="pixel-input"
          value={nickname}
          placeholder="никнейм (необязательно)"
          maxLength={64}
          onChange={(e) => setNickname(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        <button className="px-btn primary big" disabled={!email.trim()} onClick={submit}>
          войти в чат
        </button>
        {error && <p className="error-text">{error}</p>}
      </div>
    </div>
  )
}

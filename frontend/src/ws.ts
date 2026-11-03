export type WsEventHandler = (event: string, data: unknown) => void
export type WsStatusHandler = (connected: boolean) => void

/** Подключение к /ws/chat с автоматическим переподключением с нарастающей задержкой. */
export function connectChatWs(onEvent: WsEventHandler, onStatus: WsStatusHandler): () => void {
  let stopped = false
  let socket: WebSocket | null = null
  let attempts = 0
  let retryTimer: number | undefined
  let heartbeatTimer: number | undefined

  const open = () => {
    if (stopped) return
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${location.host}/ws/chat`)
    socket.onopen = () => {
      attempts = 0
      onStatus(true)
      // корпоративный прокси рвёт долго простаивающие WebSocket —
      // пульс не даёт соединению считаться простаивающим
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = window.setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ event: 'ping' }))
        }
      }, 10_000)
    }
    socket.onmessage = (e) => {
      try {
        const message = JSON.parse(e.data as string) as { event: string; data: unknown }
        onEvent(message.event, message.data)
      } catch {
        // игнорируем некорректные кадры
      }
    }
    socket.onclose = () => {
      onStatus(false)
      window.clearInterval(heartbeatTimer)
      if (!stopped) {
        attempts += 1
        retryTimer = window.setTimeout(open, Math.min(15000, 1000 * 2 ** attempts))
      }
    }
    socket.onerror = () => socket?.close()
  }

  open()

  return () => {
    stopped = true
    window.clearTimeout(retryTimer)
    window.clearInterval(heartbeatTimer)
    socket?.close()
  }
}

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

// Корпоративный прокси рвёт долго простаивающие WebSocket. Без трафика HMR-сокет
// vite-client погибает, клиент решает, что сервер перезапустился, и перезагружает
// страницу. Пульс каждые 10 секунд держит сокет занятым — автоперезагрузки прекращаются.
if (import.meta.hot) {
  window.setInterval(() => import.meta.hot?.send('ping'), 10_000)
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

import GithubIcon from './GithubIcon.jsx'
import { useEffect, useRef, useState } from 'react'
import { api, post } from './api.js'
import ThemeToggle from './ThemeToggle.jsx'

function loadGoogle() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts) return resolve()
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.onload = resolve
    s.onerror = reject
    document.head.append(s)
  })
}

export default function Login({ onLogin }) {
  const btn = useRef(null)
  const [err, setErr] = useState('')
  const [dev, setDev] = useState(false)

  useEffect(() => {
    let alive = true
    ;(async () => {
      const cfg = await api('/api/config')
      if (!alive) return
      setDev(cfg.dev)
      if (!cfg.clientId) return
      await loadGoogle()
      window.google.accounts.id.initialize({
        client_id: cfg.clientId,
        callback: async ({ credential }) => {
          try { onLogin((await post('/api/auth/google', { credential })).user) }
          catch (e) { setErr(e.message) }
        },
      })
      window.google.accounts.id.renderButton(btn.current, { theme: 'outline', size: 'large', shape: 'pill' })
    })().catch(() => setErr('Could not load Google sign-in'))
    return () => { alive = false }
  }, [onLogin])

  return (
    <div className="center">
      <div className="card login">
        <ThemeToggle />
        <h1>☕ CopeeMachine</h1>
        <p className="muted">Your notes, on every device.</p>
        <div ref={btn} className="gbtn" />
        {dev && <button className="btn ghost" onClick={async () => onLogin((await post('/api/auth/dev', { name: 'dev' })).user)}>Dev sign-in</button>}
        <p className="err">{err}</p>
        <a className="link" href="https://github.com/Tsaha11" target="_blank" rel="noreferrer" title="GitHub" aria-label="GitHub"><GithubIcon /></a>
      </div>
    </div>
  )
}

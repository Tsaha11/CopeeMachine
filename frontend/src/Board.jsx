import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, post, AuthError, API_BASE } from './api.js'
import Composer from './Composer.jsx'
import NoteCard from './NoteCard.jsx'
import Editor from './Editor.jsx'
import ThemeToggle from './ThemeToggle.jsx'

export default function Board({ user, onLogout }) {
  const [notes, setNotes] = useState([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // note id being edited
  const [status, setStatus] = useState('')

  const guard = useCallback((e) => {
    if (e instanceof AuthError) onLogout()
    else { setStatus(e.message); setTimeout(() => setStatus(''), 4000) }
  }, [onLogout])

  const upsert = useCallback((n) => setNotes((cur) => {
    const rest = cur.filter((x) => x.id !== n.id)
    return [n, ...rest].sort((a, b) => (b.pinned - a.pinned) || (b.updatedAt - a.updatedAt))
  }), [])

  // Live sync across this user's devices.
  useEffect(() => {
    const es = new EventSource(API_BASE + '/api/events', { withCredentials: true })
    es.onopen = () => api('/api/notes').then(setNotes).catch(guard)
    es.addEventListener('note', (e) => upsert(JSON.parse(e.data)))
    es.addEventListener('gone', (e) => {
      const { id } = JSON.parse(e.data)
      setNotes((cur) => cur.filter((n) => n.id !== id))
      setOpen((o) => (o === id ? null : o))
    })
    return () => es.close()
  }, [guard, upsert])

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? notes.filter((n) => `${n.title} ${n.body}`.toLowerCase().includes(q)) : notes
  }, [notes, query])
  const pinned = shown.filter((n) => n.pinned)
  const others = shown.filter((n) => !n.pinned)

  async function logout() {
    await post('/api/logout', {}).catch(() => {})
    onLogout()
  }

  return (
    <div>
      <header className="top">
        <h1>☕ CopeeMachine</h1>
        <input className="search" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
        <span className="status">{status}</span>
        <div className="who">
          <ThemeToggle />
          {user.picture && <img src={user.picture} alt="" referrerPolicy="no-referrer" />}
          <button className="link" onClick={logout} title={user.email}>Sign out</button>
        </div>
      </header>
      <main>
        <Composer onError={guard} />
        {notes.length === 0 && <p className="empty">Notes you add appear here — on all your devices.</p>}
        {pinned.length > 0 && <><h2>Pinned</h2><div className="grid">{pinned.map((n) => <NoteCard key={n.id} note={n} onOpen={() => setOpen(n.id)} />)}</div></>}
        {others.length > 0 && <>{pinned.length > 0 && <h2>Others</h2>}<div className="grid">{others.map((n) => <NoteCard key={n.id} note={n} onOpen={() => setOpen(n.id)} />)}</div></>}
      </main>
      {open && notes.find((n) => n.id === open) &&
        <Editor note={notes.find((n) => n.id === open)} onClose={() => setOpen(null)} onError={guard} />}
    </div>
  )
}

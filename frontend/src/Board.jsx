import GithubIcon from './GithubIcon.jsx'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, patch, post, AuthError, API_BASE } from './api.js'
import Composer from './Composer.jsx'
import NoteCard from './NoteCard.jsx'
import Editor from './Editor.jsx'
import Passcode from './Passcode.jsx'
import ThemeToggle from './ThemeToggle.jsx'
import Loader from './Loader.jsx'
import useFlip from './useFlip.js'

export default function Board({ user, onLogout }) {
  const [notes, setNotes] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [showLoader, setShowLoader] = useState(true)
  const pinnedRef = useRef(null)
  const othersRef = useRef(null)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // note id being edited
  const [status, setStatus] = useState('')
  const [revealed, setRevealed] = useState({}) // locked note id -> body, after the passcode was entered
  const [asking, setAsking] = useState(null) // { id, then: 'open' | 'unlock' } while the passcode prompt is up

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
    es.onopen = () => api('/api/notes').then(setNotes).catch(guard).finally(() => setLoaded(true))
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
  const order = shown.map((n) => n.id + n.pinned).join()
  useFlip(pinnedRef, [order, loaded])
  useFlip(othersRef, [order, loaded])
  useEffect(() => {
    if (!loaded) return
    const t = setTimeout(() => setShowLoader(false), 450)
    return () => clearTimeout(t)
  }, [loaded])

  // Locked notes need the passcode to open or to remove the lock; locking needs nothing.
  const openNote = (n) => (n.locked && !(n.id in revealed) ? setAsking({ id: n.id, then: 'open' }) : setOpen(n.id))
  const toggleLock = (n) => {
    if (n.locked) return n.id in revealed ? patch(`/api/notes/${n.id}`, { locked: false }).catch(guard) : setAsking({ id: n.id, then: 'unlock' })
    patch(`/api/notes/${n.id}`, { locked: true }).catch(guard)
  }
  const unlocked = async (n) => {
    const { then } = asking
    setAsking(null)
    setRevealed((r) => ({ ...r, [n.id]: n.body }))
    if (then === 'open') setOpen(n.id)
    else await patch(`/api/notes/${n.id}`, { locked: false }).catch(guard)
  }
  // Closing a note locks it again: forget its text here and on the server.
  const closeNote = (id) => {
    setOpen(null)
    if (!(id in revealed) && !notes.find((n) => n.id === id)?.locked) return
    setRevealed(({ [id]: _, ...r }) => r)
    post(`/api/notes/${id}/close`, {}).catch(() => {})
  }
  const withBody = (n) => (n.locked && n.id in revealed ? { ...n, body: revealed[n.id] } : n)

  async function logout() {
    await post('/api/logout', {}).catch(() => {})
    onLogout()
  }

  return (
    <div>
      {showLoader && <Loader leaving={loaded} />}
      <header className="top">
        <h1>☕ CopeeMachine</h1>
        <input className="search" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
        <span className="status">{status}</span>
        <div className="who">
          <ThemeToggle />
          <a className="link" href="https://github.com/Tsaha11" target="_blank" rel="noreferrer" title="GitHub" aria-label="GitHub"><GithubIcon /></a>
          {user.picture && <img src={user.picture} alt="" referrerPolicy="no-referrer" />}
          <button className="link" onClick={logout} title={user.email}>Sign out</button>
        </div>
      </header>
      <main>
        <Composer onError={guard} />
        {notes.length === 0 && <p className="empty">Notes you add appear here — on all your devices.</p>}
        {pinned.length > 0 && <><h2>Pinned</h2><div className="grid" ref={pinnedRef}>{pinned.map((n, i) => <NoteCard key={n.id} index={i} note={n} onOpen={() => openNote(n)} onLock={() => toggleLock(n)} />)}</div></>}
        {others.length > 0 && <>{pinned.length > 0 && <h2>Others</h2>}<div className="grid" ref={othersRef}>{others.map((n, i) => <NoteCard key={n.id} index={i} note={n} onOpen={() => openNote(n)} onLock={() => toggleLock(n)} />)}</div></>}
      </main>
      {open && notes.find((n) => n.id === open) &&
        <Editor note={withBody(notes.find((n) => n.id === open))} onClose={() => closeNote(open)} onError={guard} />}
      {asking && <Passcode noteId={asking.id} onDone={unlocked} onCancel={() => setAsking(null)} />}
    </div>
  )
}

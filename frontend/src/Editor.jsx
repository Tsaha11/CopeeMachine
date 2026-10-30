import { useEffect, useRef, useState } from 'react'
import { del, patch, post } from './api.js'
import EmailIcon from './EmailIcon.jsx'
import LockIcon from './LockIcon.jsx'

export const COLORS = ['default', 'red', 'orange', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink', 'gray']

export default function Editor({ note, onClose, onError }) {
  const [title, setTitle] = useState(note.title)
  const [body, setBody] = useState(note.body)
  const [mailState, setMailState] = useState('') // '', 'sending', 'sent'
  const [leaving, setLeaving] = useState(false)
  const dirty = useRef({})
  const timer = useRef(null)
  const noteId = note.id

  // Debounced autosave of text edits; flushed on close.
  const flush = async () => {
    clearTimeout(timer.current)
    const d = dirty.current
    if (!Object.keys(d).length) return
    dirty.current = {}
    try { await patch(`/api/notes/${noteId}`, d) } catch (e) { onError(e) }
  }
  const edit = (k, v) => {
    dirty.current[k] = v
    clearTimeout(timer.current)
    timer.current = setTimeout(flush, 600)
  }
  const leave = () => { setLeaving(true); setTimeout(onClose, 220) }
  const close = async () => { if (leaving) return; await flush(); leave() }
  useEffect(() => () => { flush() }, []) // eslint-disable-line

  const act = (fn) => fn().catch(onError)

  async function sendEmail() {
    setMailState('sending')
    try {
      await flush()
      await post(`/api/notes/${noteId}/email`, {})
      setMailState('sent')
      setTimeout(() => setMailState(''), 3000)
    } catch (err) { setMailState(''); onError(err) }
  }

  return (
    <div className={`backdrop${leaving ? ' out' : ''}`} onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className={`card editor c-${note.color}`}>
        <div className="row between">
          <input className="title" placeholder="Title" value={title} onChange={(e) => { setTitle(e.target.value); edit('title', e.target.value) }} />
          <button className={`icon lock-btn${note.locked ? ' on' : ''}`} title={note.locked ? 'Unlock' : 'Lock'}
                  onClick={() => act(() => patch(`/api/notes/${noteId}`, note.locked ? { locked: false } : { locked: true, keepOpen: true }))}><LockIcon locked={note.locked} size={18} /></button>
          <button className="icon" title={note.pinned ? 'Unpin' : 'Pin'} onClick={() => act(() => patch(`/api/notes/${noteId}`, { pinned: !note.pinned }))}>{note.pinned ? '📌' : '📍'}</button>
        </div>
        <textarea autoFocus placeholder="Note" value={body} onChange={(e) => { setBody(e.target.value); edit('body', e.target.value) }} />
        <div className="swatches">{COLORS.map((c) => (
              <button key={c} className={`sw c-${c} ${note.color === c ? 'on' : ''}`} title={c}
                      onClick={() => act(() => patch(`/api/notes/${noteId}`, { color: c }))} />
        ))}</div>
        <div className="row between">
          <div className="row">
            <button className="link" onClick={async () => { await flush(); await act(() => del(`/api/notes/${noteId}`)); leave() }}>🗑 Delete</button>
            <button className="link" title="Email this note to yourself" disabled={mailState === 'sending'} onClick={sendEmail}><EmailIcon /> {mailState === 'sending' ? 'Sending…' : 'Email'}</button>
            {mailState === 'sent' && <span className="muted">Sent ✓</span>}
          </div>
          <button className="btn" onClick={close}>Close</button>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { del, patch, post } from './api.js'
import { shareWhatsApp } from './share.js'
import whatsappIcon from './img/whatsapp.png'
import emailIcon from './img/email.png'

export const COLORS = ['default', 'red', 'orange', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink', 'gray']

export default function Editor({ note, onClose, onError }) {
  const [title, setTitle] = useState(note.title)
  const [body, setBody] = useState(note.body)
  const [mailTo, setMailTo] = useState(null) // null = closed, string = recipient being typed
  const [mailState, setMailState] = useState('') // '', 'sending', 'sent'
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
  const close = async () => { await flush(); onClose() }
  useEffect(() => () => { flush() }, []) // eslint-disable-line

  const act = (fn) => fn().catch(onError)

  async function sendEmail(e) {
    e.preventDefault()
    setMailState('sending')
    try {
      await flush()
      await post(`/api/notes/${noteId}/email`, { to: mailTo })
      setMailState('sent'); setMailTo(null)
      setTimeout(() => setMailState(''), 3000)
    } catch (err) { setMailState(''); onError(err) }
  }

  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className={`card editor c-${note.color}`}>
        <div className="row between">
          <input className="title" placeholder="Title" value={title} onChange={(e) => { setTitle(e.target.value); edit('title', e.target.value) }} />
          <button className="icon" title={note.pinned ? 'Unpin' : 'Pin'} onClick={() => act(() => patch(`/api/notes/${noteId}`, { pinned: !note.pinned }))}>{note.pinned ? '📌' : '📍'}</button>
        </div>
        <textarea autoFocus placeholder="Note" value={body} onChange={(e) => { setBody(e.target.value); edit('body', e.target.value) }} />
        <div className="swatches">{COLORS.map((c) => (
              <button key={c} className={`sw c-${c} ${note.color === c ? 'on' : ''}`} title={c}
                      onClick={() => act(() => patch(`/api/notes/${noteId}`, { color: c }))} />
        ))}</div>
        {mailTo !== null && (
          <form className="row" onSubmit={sendEmail}>
            <input className="mailto" type="email" required autoFocus placeholder="Send to (email address)"
                   value={mailTo} onChange={(e) => setMailTo(e.target.value)} />
            <button className="btn" disabled={mailState === 'sending'}>{mailState === 'sending' ? 'Sending…' : 'Send'}</button>
          </form>
        )}
        <div className="row between">
          <div className="row">
            <button className="link" onClick={async () => { await flush(); await act(() => del(`/api/notes/${noteId}`)); onClose() }}>🗑 Delete</button>
            <button className="link" title="Send via WhatsApp" onClick={() => shareWhatsApp(title, body)}><img className="ico" src={whatsappIcon} alt="" /> WhatsApp</button>
            <button className="link" title="Send via email" onClick={() => setMailTo(mailTo === null ? '' : null)}><img className="ico" src={emailIcon} alt="" /> Email</button>
            {mailState === 'sent' && <span className="muted">Sent ✓</span>}
          </div>
          <button className="btn" onClick={close}>Close</button>
        </div>
      </div>
    </div>
  )
}

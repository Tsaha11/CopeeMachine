import { useState } from 'react'
import { post } from './api.js'
import { COLORS } from './Editor.jsx'

export default function Composer({ onError }) {
  const [expanded, setExpanded] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [color, setColor] = useState('default')
  const [busy, setBusy] = useState(false)

  async function save() {
    if (busy) return
    if (!title.trim() && !body.trim()) return setExpanded(false)
    setBusy(true)
    try {
      await post('/api/notes', { title, body, color })
      setTitle(''); setBody(''); setColor('default'); setExpanded(false)
    } catch (e) { onError(e) }
    setBusy(false)
  }

  if (!expanded) return (
    <div className="card composer collapsed" onClick={() => setExpanded(true)}>
      <span className="muted">Take a note…</span>
    </div>
  )
  return (
    <div className={`card composer c-${color}`}>
      <input className="title" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea autoFocus placeholder="Take a note…" value={body}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save() }} />
      <div className="row between">
        <div className="row">
          <div className="swatches">{COLORS.map((c) => (
            <button key={c} className={`sw c-${c} ${color === c ? 'on' : ''}`} title={c} onClick={() => setColor(c)} />
          ))}</div>
          <button className="link" onClick={() => { setTitle(''); setBody(''); setColor('default'); setExpanded(false) }}>Discard</button>
        </div>
        <button className="btn" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Done'}</button>
      </div>
    </div>
  )
}

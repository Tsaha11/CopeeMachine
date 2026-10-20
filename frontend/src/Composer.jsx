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

  const reset = () => { setTitle(''); setBody(''); setColor('default'); setExpanded(false) }

  return (
    <div className={`card composer ${expanded ? `open c-${color}` : 'collapsed'}`}
         onClick={() => !expanded && setExpanded(true)}>
      <div className={`collapse${expanded ? ' open' : ''}`}><div>
        <input className="title" placeholder="Title" tabIndex={expanded ? 0 : -1} value={title} onChange={(e) => setTitle(e.target.value)} />
      </div></div>
      <textarea placeholder="Take a note…" value={body} rows={1}
                onFocus={() => setExpanded(true)}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save() }} />
      <div className={`collapse${expanded ? ' open' : ''}`}><div>
        <div className="row between composer-foot">
          <div className="row">
            <div className="swatches">{COLORS.map((c) => (
              <button key={c} className={`sw c-${c} ${color === c ? 'on' : ''}`} title={c} onClick={() => setColor(c)} />
            ))}</div>
            <button className="link" onClick={reset}>Discard</button>
          </div>
          <button className="btn" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Done'}</button>
        </div>
      </div></div>
    </div>
  )
}

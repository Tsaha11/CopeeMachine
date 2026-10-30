import { useState } from 'react'
import { post } from './api.js'
import LockIcon from './LockIcon.jsx'

// Asks for the passcode; on success the server returns the note with its body revealed.
export default function Passcode({ noteId, onDone, onCancel }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (busy || !code) return
    setBusy(true); setError('')
    try { onDone(await post(`/api/notes/${noteId}/unlock`, { passcode: code })) } catch (err) {
      setError(err.message); setCode(''); setBusy(false)
    }
  }

  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <form className="card editor passcode" onSubmit={submit}>
        <div className="row"><LockIcon locked size={20} /><b>This note is locked</b></div>
        <input autoFocus type="password" inputMode="numeric" autoComplete="off" placeholder="Passcode"
               value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && onCancel()} />
        {error && <span className="error">{error}</span>}
        <div className="row between">
          <button type="button" className="link" onClick={onCancel}>Cancel</button>
          <button className="btn" disabled={busy || !code}>{busy ? 'Checking…' : 'Unlock'}</button>
        </div>
      </form>
    </div>
  )
}

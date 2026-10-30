import { useState } from 'react'
import LockIcon from './LockIcon.jsx'

// Shown blurred in place of a locked note's text; the real text is never sent to the browser.
const HAZE = 'Locked note — enter the passcode to read what is written here.\nThis text is only a placeholder.'

export default function NoteCard({ note, onOpen, onLock, index = 0 }) {
  const [copied, setCopied] = useState(false)

  const copy = async e => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(note.body)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {}
  }

  return (
    <article data-flip={note.id} className={`card note c-${note.color}`} onClick={onOpen} style={{ animationDelay: `${Math.min(index, 12) * 40}ms` }}>
      {note.title && <h3>{note.title}</h3>}
      {note.locked && <p className="body hazy" aria-label="Locked">{HAZE}</p>}
      {!note.locked && note.body && <p className="body">{note.body.length > 600 ? note.body.slice(0, 600) + '…' : note.body}</p>}
      <button className={`lock${note.locked ? ' on' : ''}${note.pinned ? ' by-pin' : ''}`} title={note.locked ? 'Unlock' : 'Lock'} aria-label={note.locked ? 'Unlock' : 'Lock'}
              onClick={(e) => { e.stopPropagation(); onLock() }}><LockIcon locked={note.locked} /></button>
      {note.pinned && <span className="pin">📌</span>}
      {!note.locked && note.body && (
        <button className={`copy${copied ? ' done' : ''}`} onClick={copy} title={copied ? 'Copied' : 'Copy text'} aria-label="Copy text">
          {copied
            ? <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
            : <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" /></svg>}
        </button>
      )}
    </article>
  )
}

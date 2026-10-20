export default function NoteCard({ note, onOpen, index = 0 }) {
  return (
    <article data-flip={note.id} className={`card note c-${note.color}`} onClick={onOpen} style={{ animationDelay: `${Math.min(index, 12) * 40}ms` }}>
      {note.title && <h3>{note.title}</h3>}
      {note.body && <p className="body">{note.body.length > 600 ? note.body.slice(0, 600) + '…' : note.body}</p>}
      {note.pinned && <span className="pin">📌</span>}
    </article>
  )
}

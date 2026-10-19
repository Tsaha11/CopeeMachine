export default function NoteCard({ note, onOpen }) {
  return (
    <article className={`card note c-${note.color}`} onClick={onOpen}>
      {note.title && <h3>{note.title}</h3>}
      {note.body && <p className="body">{note.body.length > 600 ? note.body.slice(0, 600) + '…' : note.body}</p>}
      {note.pinned && <span className="pin">📌</span>}
    </article>
  )
}

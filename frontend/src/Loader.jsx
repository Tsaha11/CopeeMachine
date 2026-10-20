export default function Loader() {
  return (
    <div className="loader" role="status" aria-label="Loading">
      <svg viewBox="0 0 64 64" width="72" height="72" aria-hidden="true">
        <path className="steam s1" d="M23 21c0-4.5 4.5-4.5 4.5-9" />
        <path className="steam s2" d="M33 21c0-4.5 4.5-4.5 4.5-9" />
        <path className="handle" d="M44 30h3.5a6.5 6.5 0 0 1 0 13H44" />
        <path className="cup" d="M14 27h30v13a12 12 0 0 1-12 12h-6a12 12 0 0 1-12-12z" />
      </svg>
      <span>Brewing your notes…</span>
    </div>
  )
}

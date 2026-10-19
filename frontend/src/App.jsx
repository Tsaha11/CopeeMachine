import { useEffect, useState } from 'react'
import { api } from './api.js'
import Login from './Login.jsx'
import Board from './Board.jsx'

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = checking, null = signed out

  useEffect(() => {
    api('/api/me').then((d) => setUser(d.user)).catch(() => setUser(null))
  }, [])

  if (user === undefined) return null
  return user
    ? <Board user={user} onLogout={() => setUser(null)} />
    : <Login onLogin={setUser} />
}

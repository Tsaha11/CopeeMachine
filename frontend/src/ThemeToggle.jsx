import { useState } from 'react'
import { MODES, getMode, setMode } from './theme.js'

const ICON = { system: '🖥️', light: '☀️', dark: '🌙' }
const LABEL = { system: 'Match system', light: 'Light', dark: 'Dark' }

export default function ThemeToggle() {
  const [mode, set] = useState(getMode)
  const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length]
  return (
    <button className="link theme" title={`Theme: ${LABEL[mode]} (click for ${LABEL[next]})`}
            onClick={() => { setMode(next); set(next) }}>{ICON[mode]}</button>
  )
}

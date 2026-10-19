import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'
import { getMode, setMode } from './theme.js'

setMode(getMode())

createRoot(document.getElementById('root')).render(<App />)

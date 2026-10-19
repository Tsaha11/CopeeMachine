// 'system' follows the OS; 'light' / 'dark' force a theme via <html data-theme>.
export const MODES = ['system', 'light', 'dark']

export function getMode() {
  try { const m = localStorage.getItem('theme'); return MODES.includes(m) ? m : 'system' } catch { return 'system' }
}

export function setMode(mode) {
  if (mode === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.dataset.theme = mode
  try { localStorage.setItem('theme', mode) } catch { /* private mode: still applies for this visit */ }
}

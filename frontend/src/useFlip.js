import { useLayoutEffect, useRef } from 'react'

// FLIP: when children (keyed by data-flip) change position, glide them from the old spot.
export default function useFlip(ref, deps) {
  const prev = useRef(new Map())
  const width = useRef(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const next = new Map()
    const resized = width.current !== window.innerWidth
    width.current = window.innerWidth
    for (const c of el.children) {
      const id = c.dataset.flip
      const r = c.getBoundingClientRect()
      next.set(id, r)
      const old = prev.current.get(id)
      if (!old || resized) continue
      const dx = old.left - r.left, dy = old.top - r.top
      if (!dx && !dy) continue
      c.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: 'none' }],
        { duration: 380, easing: 'cubic-bezier(.22,.61,.36,1)' })
    }
    prev.current = next
  }, deps) // eslint-disable-line
}

import { useEffect } from 'react'
import type { Palette } from '../lib/api'

const DEFAULT: Palette = { from: '#000000', to: '#050507', accent: '#7c5cff' }

/**
 * Environmental Feedback Engine (Phase 1 rendering).
 * Background colours glide over ~12 s — never flashing, never distracting —
 * as specified for the environment controller.
 */
export default function Ambient({ palette }: { palette?: Palette | null }) {
  const p = palette ?? DEFAULT
  useEffect(() => {
    document.documentElement.style.setProperty('--env-accent', p.accent)
  }, [p.accent])
  return (
    <div
      aria-hidden="true"
      className="ambient pointer-events-none fixed inset-0 -z-10"
      style={{ ['--env-from' as string]: p.from, ['--env-to' as string]: p.to, ['--env-accent' as string]: p.accent }}
    >
      <div className="absolute inset-0 opacity-[0.035] [background-image:radial-gradient(rgba(255,255,255,0.9)_1px,transparent_1px)] [background-size:3px_3px]" />
    </div>
  )
}

import { useEffect, useRef } from 'react'

export type OrbMode = 'idle' | 'thinking' | 'speaking'

/** Colour sets for each environment state chosen by the Decision Engine. */
export const ORB_COLORS: Record<string, string[]> = {
  neutral_black: ['#ffb36b', '#ff3ea5', '#8a5cff', '#3b82f6'],
  calm_dark_blue: ['#7cc4ff', '#4f7dff', '#6a5cff', '#1e3a8a'],
  soft_violet: ['#f0a6ff', '#c46bff', '#8a5cff', '#4f46e5'],
  warm_amber: ['#ffd27a', '#ff9d4d', '#ff3ea5', '#a855f7'],
  gentle_teal: ['#a7f3d0', '#3fd0c9', '#38bdf8', '#6366f1'],
  muted_indigo: ['#c7d2fe', '#7b83ff', '#6d28d9', '#1e1b4b'],
  dim_slate: ['#cbd5e1', '#8fa3b8', '#64748b', '#334155'],
}

type Props = {
  mode?: OrbMode
  palette?: string
  className?: string
  /** Lower ring count for small renders. */
  detail?: 'high' | 'low'
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

export default function Orb({ mode = 'idle', palette = 'neutral_black', className, detail = 'high' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const modeRef = useRef(mode)
  const colorsRef = useRef<[number, number, number][]>((ORB_COLORS[palette] ?? ORB_COLORS.neutral_black).map(hexToRgb))
  const targetColorsRef = useRef(colorsRef.current)

  modeRef.current = mode
  useEffect(() => {
    targetColorsRef.current = (ORB_COLORS[palette] ?? ORB_COLORS.neutral_black).map(hexToRgb)
  }, [palette])

  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let raf = 0
    let t = Math.random() * 100
    let last = performance.now()
    let energy = 0.3
    let dpr = 1
    let visible = true

    const resize = () => {
      const r = canvas.getBoundingClientRect()
      dpr = Math.min(2, window.devicePixelRatio || 1)
      canvas.width = Math.max(1, Math.round(r.width * dpr))
      canvas.height = Math.max(1, Math.round(r.height * dpr))
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting))
    io.observe(canvas)

    const rings = detail === 'high' ? 44 : 22
    const seg = detail === 'high' ? 96 : 56

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (!visible) return
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      const m = modeRef.current
      const target = m === 'thinking' ? 0.9 : m === 'speaking' ? 0.65 : 0.28
      energy += (target - energy) * Math.min(1, dt * 1.6)
      t += dt * (reduced ? 0.08 : 0.3 + energy * 0.9)

      // Ease colours towards the target palette (slow environmental change).
      colorsRef.current = colorsRef.current.map((c, i) => {
        const tc = targetColorsRef.current[i]
        return c.map((v, k) => v + (tc[k] - v) * Math.min(1, dt * 0.6)) as [number, number, number]
      })
      const cols = colorsRef.current
      const rgb = (c: [number, number, number], a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`

      const W = canvas.width
      const H = canvas.height
      const cx = W / 2
      const cy = H / 2
      const R = Math.min(W, H) * 0.34
      ctx.clearRect(0, 0, W, H)

      // Soft halo
      ctx.globalCompositeOperation = 'source-over'
      const halo = ctx.createRadialGradient(cx, cy, R * 0.3, cx, cy, R * 1.55)
      halo.addColorStop(0, rgb(cols[2], 0.22 + energy * 0.12))
      halo.addColorStop(0.6, rgb(cols[1], 0.06))
      halo.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = halo
      ctx.fillRect(0, 0, W, H)

      ctx.globalCompositeOperation = 'lighter'
      ctx.lineWidth = Math.max(0.7, dpr * (detail === 'high' ? 1.05 : 0.9))
      // Colour each ring along the sphere: warm crown -> magenta -> violet -> blue base.
      const ringColor = (u: number) => {
        const x = Math.min(0.999, Math.max(0, u)) * 3
        const k = Math.floor(x)
        const f = x - k
        const a = cols[k], b = cols[k + 1]
        return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f] as [number, number, number]
      }

      const rotY = t * 0.55
      const tilt = 0.42 + Math.sin(t * 0.27) * 0.12
      const cY = Math.cos(rotY), sY = Math.sin(rotY)
      const cT = Math.cos(tilt), sT = Math.sin(tilt)
      const amp = 0.07 + energy * 0.11

      for (let i = 0; i < rings; i++) {
        const theta = ((i + 0.5) / rings) * Math.PI
        const st = Math.sin(theta)
        const ct = Math.cos(theta)
        ctx.beginPath()
        for (let j = 0; j <= seg; j++) {
          const phi = (j / seg) * Math.PI * 2
          const n =
            Math.sin(3 * theta + t * 1.3) * Math.cos(2 * phi - t) * 0.5 +
            Math.sin(5 * phi + 2 * theta + t * 0.7) * 0.28 +
            Math.sin(4 * theta - 3 * phi + t * 1.7) * 0.22
          const r = R * (1 + amp * n)
          const x = r * st * Math.cos(phi)
          const y = r * ct
          const z = r * st * Math.sin(phi)
          const x2 = x * cY - z * sY
          const z2 = x * sY + z * cY
          const y2 = y * cT - z2 * sT
          const px = cx + x2
          const py = cy + y2
          if (j === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        }
        ctx.strokeStyle = rgb(ringColor(1 - i / (rings - 1) + Math.sin(t * 0.4) * 0.06))
        ctx.globalAlpha = 0.22 + 0.5 * st * st
        ctx.stroke()
      }
      ctx.globalAlpha = 1
      ctx.globalCompositeOperation = 'source-over'
    }
    raf = requestAnimationFrame(frame)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
    }
  }, [detail])

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}

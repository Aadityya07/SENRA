import { LifeBuoy, Phone } from 'lucide-react'
import type { Helpline } from '../../lib/api'

const DEFAULT_LINES: Helpline[] = [
  { name: 'Tele-MANAS (Govt. of India, 24x7)', contact: '14416 / 1-800-891-4416', href: 'tel:14416' },
  { name: 'Emergency Services (India)', contact: '112', href: 'tel:112' },
]

export default function SafetyCard({ level, helplines }: { level: string; helplines?: Helpline[] }) {
  const lines = helplines?.length ? helplines : DEFAULT_LINES
  const crisis = level === 'crisis'
  return (
    <div className={`mt-4 rounded-2xl border p-4 ${crisis ? 'border-rose-400/30 bg-rose-500/[0.07]' : 'border-sky-300/20 bg-sky-400/[0.05]'}`}>
      <div className="flex items-center gap-2 text-sm font-medium text-white/90">
        <LifeBuoy className={`h-4 w-4 ${crisis ? 'text-rose-300' : 'text-sky-300'}`} />
        {crisis ? 'You deserve support from a real person right now' : 'If things feel heavy, real people can help'}
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-white/60">
        SENRA is an AI companion, not a counsellor. These services are free, confidential and available any time.
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {lines.map((h) => (
          <a
            key={h.name}
            href={h.href}
            target={h.href.startsWith('http') ? '_blank' : undefined}
            rel="noreferrer"
            className="flex items-center gap-3 rounded-xl bg-white/[0.04] px-3 py-2.5 ring-1 ring-white/10 transition hover:bg-white/[0.08]"
          >
            <Phone className="h-4 w-4 shrink-0 text-white/60" />
            <span className="min-w-0">
              <span className="block truncate text-[12px] text-white/55">{h.name}</span>
              <span className="block text-[14px] font-medium text-white/90">{h.contact}</span>
            </span>
          </a>
        ))}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Brain, Trash2, X } from 'lucide-react'
import { api } from '../../lib/api'

type Item = { id: number; memory_type: string; memory_key: string; memory_value: string; count: number }

const TYPE_LABEL: Record<string, string> = {
  profile: 'About you', trigger: 'Has weighed on you', uplift: 'Lifts your mood', preference: 'Preference',
}

function describe(i: Item) {
  if (i.memory_type === 'profile') return `${i.memory_key}: ${i.memory_value}`
  if (i.memory_type === 'preference') return i.memory_value === 'listen' ? 'Prefers being listened to' : 'Appreciates practical suggestions'
  return `${i.memory_key}${i.count > 1 ? ` · mentioned ${i.count}×` : ''}`
}

export default function MemoryDialog({ userId, onClose }: { userId: string; onClose: () => void }) {
  const [enabled, setEnabled] = useState(true)
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => api.memory(userId).then((m) => { setEnabled(m.memory_enabled); setItems(m.items); setLoading(false) }).catch(() => setLoading(false))
  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const toggle = async () => { await api.setMemory(userId, !enabled); setEnabled(!enabled) }
  const remove = async (id?: number) => { await api.clearMemory(userId, id); load() }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Emotional memory" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md animate-fade-up rounded-3xl border border-white/10 bg-[#0b0b10] p-6 shadow-2xl">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/5 ring-1 ring-white/10"><Brain className="h-5 w-5" /></span>
          <div className="flex-1">
            <h2 className="text-base font-medium">Emotional memory</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-white/55">
              SENRA can remember small things — your name, what tends to weigh on you, how you like to be supported — to make conversations feel more personal. You stay in control.
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-white/50 hover:bg-white/5" aria-label="Close"><X className="h-4 w-4" /></button>
        </div>

        <label className="mt-5 flex cursor-pointer items-center justify-between rounded-2xl bg-white/[0.04] px-4 py-3 ring-1 ring-white/10">
          <span className="text-sm">Remember things about me</span>
          <button type="button" onClick={toggle} role="switch" aria-checked={enabled}
            className={`relative h-6 w-11 rounded-full transition ${enabled ? 'bg-[var(--env-accent)]' : 'bg-white/15'}`}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${enabled ? 'left-[22px]' : 'left-0.5'}`} />
          </button>
        </label>

        <div className="mt-4 max-h-64 space-y-1.5 overflow-y-auto">
          {loading ? <p className="py-6 text-center text-sm text-white/40">Loading…</p>
            : items.length === 0 ? <p className="py-6 text-center text-sm text-white/40">Nothing remembered yet.</p>
            : items.map((i) => (
              <div key={i.id} className="group flex items-center gap-3 rounded-xl px-3 py-2 hover:bg-white/[0.04]">
                <span className="w-28 shrink-0 text-[11px] uppercase tracking-wider text-white/35">{TYPE_LABEL[i.memory_type] ?? i.memory_type}</span>
                <span className="flex-1 truncate text-[13.5px] capitalize text-white/80">{describe(i)}</span>
                <button onClick={() => remove(i.id)} className="rounded-md p-1 text-white/30 opacity-0 hover:text-rose-300 group-hover:opacity-100" aria-label="Forget"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            ))}
        </div>

        {items.length > 0 && (
          <button onClick={() => remove()} className="mt-4 w-full rounded-xl border border-rose-400/20 bg-rose-500/[0.06] py-2.5 text-[13px] text-rose-200 transition hover:bg-rose-500/[0.12]">
            Forget everything
          </button>
        )}
        <p className="mt-4 text-center text-[11.5px] text-white/35">Stored locally on this machine. Raw audio and video are never stored.</p>
      </div>
    </div>
  )
}

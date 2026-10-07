import { useEffect, useRef } from 'react'
import { ArrowUp, Camera, Mic, Plus, Square } from 'lucide-react'

type Props = {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  streaming: boolean
  disabled?: boolean
  autoFocus?: boolean
}

function PhaseTwo({ icon: Icon, label }: { icon: any; label: string }) {
  return (
    <div className="group relative">
      <button type="button" disabled aria-label={`${label} (coming in Phase 2)`}
        className="grid h-9 w-9 place-items-center rounded-full text-white/35 transition">
        <Icon className="h-[18px] w-[18px]" />
      </button>
      <span className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-white px-2 py-1 text-[11px] font-medium text-black opacity-0 shadow-lg transition group-hover:opacity-100">
        {label} · Phase 2
      </span>
    </div>
  )
}

export default function Composer({ value, onChange, onSend, onStop, streaming, disabled, autoFocus }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = Math.min(200, el.scrollHeight) + 'px'
  }, [value])

  useEffect(() => {
    if (autoFocus && window.matchMedia('(pointer: fine)').matches) ref.current?.focus()
  }, [autoFocus])

  const canSend = value.trim().length > 0 && !disabled

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (streaming) onStop(); else if (canSend) onSend() }}
      className="glass flex items-end gap-1 rounded-[28px] p-1.5 pl-2 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.9)] focus-within:border-white/20"
    >
      <PhaseTwo icon={Plus} label="Attachments" />
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            if (!streaming && canSend) onSend()
          }
        }}
        placeholder="Message SENRA…"
        aria-label="Message SENRA"
        className="max-h-[200px] min-h-[36px] flex-1 resize-none bg-transparent px-1 py-[7px] text-[15px] leading-[22px] text-white placeholder:text-white/35 focus:outline-none"
      />
      <PhaseTwo icon={Camera} label="Camera" />
      <PhaseTwo icon={Mic} label="Voice" />
      <button
        type="submit"
        disabled={!streaming && !canSend}
        aria-label={streaming ? 'Stop generating' : 'Send message'}
        className={`grid h-9 w-9 shrink-0 place-items-center rounded-full transition ${streaming ? 'bg-white text-black' : canSend ? 'btn-orb text-white' : 'bg-white/10 text-white/35'}`}
      >
        {streaming ? <Square className="h-3.5 w-3.5 fill-current" /> : <ArrowUp className="h-[18px] w-[18px]" />}
      </button>
    </form>
  )
}

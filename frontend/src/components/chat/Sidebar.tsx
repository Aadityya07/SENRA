import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Brain, Check, Home, LogOut, MessageSquare, Pencil, PenSquare, Trash2, X } from 'lucide-react'
import type { Conversation } from '../../lib/api'
import Logo from '../Logo'

type Props = {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
  onOpenMemory: () => void
  onLogout: () => void
  onClose?: () => void
}

function group(convs: Conversation[]) {
  const now = new Date()
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
  const week = startToday - 6 * 86400
  const g: Record<string, Conversation[]> = { Today: [], 'Previous 7 days': [], Earlier: [] }
  for (const c of convs) {
    if (c.updated_at >= startToday) g.Today.push(c)
    else if (c.updated_at >= week) g['Previous 7 days'].push(c)
    else g.Earlier.push(c)
  }
  return Object.entries(g).filter(([, v]) => v.length)
}

export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete, onRename, onOpenMemory, onLogout, onClose }: Props) {
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [confirmDel, setConfirmDel] = useState<string | null>(null)

  return (
    <div className="flex h-full flex-col bg-[#060608]/95 backdrop-blur-xl lg:bg-black/30">
      <div className="flex items-center gap-2 px-4 pb-2 pt-4">
        <Link to="/" className="flex items-center gap-2 rounded-lg px-1 py-1">
          <Logo className="h-6 w-6" />
          <span className="text-[13px] font-semibold tracking-[0.18em]">SENRA</span>
        </Link>
        {onClose && (
          <button onClick={onClose} className="ml-auto rounded-lg p-1.5 text-white/50 hover:bg-white/5 lg:hidden" aria-label="Close sidebar">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="px-3 py-2">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-[13.5px] text-white/85 transition hover:bg-white/[0.08]"
        >
          <PenSquare className="h-4 w-4" /> New conversation
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 && (
          <p className="px-3 py-6 text-center text-[12.5px] leading-relaxed text-white/35">Your conversations will appear here.</p>
        )}
        {group(conversations).map(([label, items]) => (
          <div key={label} className="mt-3">
            <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-white/30">{label}</p>
            {items.map((c) => (
              <div
                key={c.conversation_id}
                className={`group relative flex items-center rounded-lg ${activeId === c.conversation_id ? 'bg-white/[0.08]' : 'hover:bg-white/[0.04]'}`}
              >
                {editing === c.conversation_id ? (
                  <form
                    className="flex w-full items-center gap-1 px-2 py-1"
                    onSubmit={(e) => { e.preventDefault(); if (draft.trim()) onRename(c.conversation_id, draft.trim()); setEditing(null) }}
                  >
                    <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => setEditing(null)}
                      className="w-full rounded-md bg-black/50 px-2 py-1 text-[13px] outline-none ring-1 ring-white/15" />
                    <button type="submit" onMouseDown={(e) => e.preventDefault()} className="p-1 text-white/60"><Check className="h-3.5 w-3.5" /></button>
                  </form>
                ) : (
                  <>
                    <button onClick={() => onSelect(c.conversation_id)} className="flex min-w-0 flex-1 items-center gap-2.5 px-3 py-2 text-left">
                      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-white/35" />
                      <span className="truncate text-[13px] text-white/75">{c.title}</span>
                    </button>
                    {confirmDel === c.conversation_id ? (
                      <div className="flex items-center gap-1 pr-2">
                        <button onClick={() => { onDelete(c.conversation_id); setConfirmDel(null) }} className="rounded-md bg-rose-500/20 px-2 py-0.5 text-[11px] text-rose-200">Delete</button>
                        <button onClick={() => setConfirmDel(null)} className="p-1 text-white/50"><X className="h-3 w-3" /></button>
                      </div>
                    ) : (
                      <div className="flex items-center pr-1.5 opacity-0 transition group-hover:opacity-100 max-lg:opacity-100">
                        <button onClick={() => { setEditing(c.conversation_id); setDraft(c.title) }} className="rounded-md p-1.5 text-white/40 hover:text-white" aria-label="Rename"><Pencil className="h-3.5 w-3.5" /></button>
                        <button onClick={() => setConfirmDel(c.conversation_id)} className="rounded-md p-1.5 text-white/40 hover:text-rose-300" aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        ))}
      </nav>

      <div className="space-y-1 border-t border-white/[0.06] p-3">
        <button onClick={onOpenMemory} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-white/65 hover:bg-white/[0.05] hover:text-white">
          <Brain className="h-4 w-4" /> Emotional memory
        </button>
        <Link to="/" className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-white/65 hover:bg-white/[0.05] hover:text-white">
          <Home className="h-4 w-4" /> About SENRA
        </Link>
        <button onClick={onLogout} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-white/65 hover:bg-rose-500/10 hover:text-rose-200">
          <LogOut className="h-4 w-4" /> Log out
        </button>
      </div>
    </div>
  )
}

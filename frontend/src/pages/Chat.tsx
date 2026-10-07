import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Activity, AlertTriangle, Check, Copy, LogOut, Menu, PenSquare, RotateCcw } from 'lucide-react'
import Orb, { type OrbMode } from '../components/Orb'
import Ambient from '../components/Ambient'
import Logo from '../components/Logo'
import Markdown from '../components/chat/Markdown'
import Composer from '../components/chat/Composer'
import Sidebar from '../components/chat/Sidebar'
import InsightsPanel from '../components/chat/InsightsPanel'
import SafetyCard from '../components/chat/SafetyCard'
import MemoryDialog from '../components/chat/MemoryDialog'
import {
  api, getUserId, streamChat,
  type Analysis, type Conversation, type Done, type Fusion, type Health, type Helpline, type Palette,
} from '../lib/api'

type UIMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  emotion?: Fusion
  streaming?: boolean
  stage?: 'listening' | 'composing'
  error?: string
  safety?: { level: string; helplines?: Helpline[] }
  strategy?: string
  latency?: Done['latency']
}

/** How long SENRA visibly "thinks" before its reply starts to appear. */
const THINKING_MS = 2000
/** Typing effect: characters revealed per tick, and tick length (≈ 200 chars/s). */
const TYPE_CHARS_PER_TICK = 5
const TYPE_TICK_MS = 25

const SUGGESTIONS = [
  { label: 'I need to vent a little', icon: '◐' },
  { label: 'I’m feeling anxious today', icon: '◌' },
  { label: 'I had a really good day!', icon: '✦' },
  { label: 'Help me plan my study night', icon: '▤' },
  { label: 'I feel a bit lonely', icon: '◑' },
  { label: 'Explain emotion recognition simply', icon: '◇' },
  { label: 'Just want to chat', icon: '○' },
]

function greeting() {
  const h = new Date().getHours()
  return h < 5 ? 'Still up?' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

const readPref = (k: string, d: boolean) => { try { const v = localStorage.getItem(k); return v == null ? d : v === '1' } catch { return d } }
const writePref = (k: string, v: boolean) => { try { localStorage.setItem(k, v ? '1' : '0') } catch { /* storage unavailable */ } }

export default function Chat() {
  const { id: routeId } = useParams()
  const navigate = useNavigate()
  const userId = useMemo(getUserId, [])

  const [conversations, setConversations] = useState<Conversation[]>([])
  const activeId = routeId ?? null
  // Router navigations run inside a transition, so the route param can lag a
  // few frames behind the user's intent. The ref is updated synchronously on
  // every explicit switch and is what outgoing requests use.
  const activeIdRef = useRef<string | null>(activeId)
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [orbMode, setOrbMode] = useState<OrbMode>('idle')
  const [palette, setPalette] = useState<Palette | null>(null)
  const [paletteName, setPaletteName] = useState('neutral_black')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [done, setDone] = useState<Done | null>(null)
  const [insights, setInsights] = useState(() => readPref('senra.insights', false) && window.innerWidth >= 1024)
  const [sidebar, setSidebar] = useState(false)
  const [memoryOpen, setMemoryOpen] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [healthErr, setHealthErr] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [logoutOpen, setLogoutOpen] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const skipLoadRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickRef = useRef(true)

  const refreshList = useCallback(() => api.conversations(userId).then(setConversations).catch(() => {}), [userId])

  // ---------------------------------------------------------------- health
  useEffect(() => {
    let alive = true
    const check = () => api.health().then((h) => { if (alive) { setHealth(h); setHealthErr(false) } }).catch(() => alive && setHealthErr(true))
    check()
    const t = setInterval(check, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  useEffect(() => { refreshList() }, [refreshList])

  // ------------------------------------------------- load a conversation
  useEffect(() => {
    const id = routeId ?? null
    activeIdRef.current = id
    if (!id) {
      if (!streaming) { setMessages([]); setAnalysis(null); setDone(null); setPalette(null); setPaletteName('neutral_black') }
      return
    }
    if (skipLoadRef.current === id) { skipLoadRef.current = null; return }
    abortRef.current?.abort()
    api.conversation(userId, id).then((c) => {
      const ui: UIMessage[] = c.messages.map((m) => ({
        id: m.message_id,
        role: m.role,
        content: m.content,
        emotion: m.role === 'user' ? m.meta?.emotion : undefined,
        safety: m.role === 'assistant' && m.meta?.structured?.show_helplines ? { level: m.meta.structured.safety.level } : undefined,
        strategy: m.meta?.strategy,
        latency: m.meta?.latency,
      }))
      setMessages(ui)
      setAnalysis(null)
      setDone(null)
      const lastA = [...c.messages].reverse().find((m) => m.role === 'assistant' && m.meta?.structured)
      setPalette(lastA?.meta.structured.palette ?? null)
      setPaletteName(lastA?.meta.structured.background ?? 'neutral_black')
      stickRef.current = true
    }).catch(() => navigate('/chat', { replace: true }))
  }, [routeId]) // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------ scrolling
  useEffect(() => {
    const el = scrollRef.current
    if (el && stickRef.current) el.scrollTop = el.scrollHeight
  }, [messages])
  const onScroll = () => {
    const el = scrollRef.current
    if (el) stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
  }

  // ----------------------------------------------------------------- send
  const run = useCallback(async (text: string, regenerate = false) => {
    const assistantId = "a_" + Date.now()
    setMessages((prev) => {
      const base = regenerate ? prev.slice(0, prev.map((m) => m.role).lastIndexOf('user') + 1) : [...prev, { id: 'u_' + Date.now(), role: 'user' as const, content: text }]
      return [...base, { id: assistantId, role: 'assistant', content: '', streaming: true, stage: 'listening' }]
    })
    stickRef.current = true
    setStreaming(true)
    setOrbMode('thinking')
    setDone(null)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const convId = activeIdRef.current
    const patch = (fn: (m: UIMessage) => UIMessage) => setMessages((prev) => prev.map((m) => (m.id === assistantId ? fn(m) : m)))

    // Thinking phase: SENRA takes a moment before it starts to answer. Tokens
    // are queued and then "typed" out at a steady pace, so the writing effect
    // is kept even when most of the reply was generated during the pause.
    let thinking = true
    let streamEnded = false
    let queue = ''
    let doneData: Done | null = null
    let finishTyping: () => void = () => {}
    const typingDone = new Promise<void>((resolve) => { finishTyping = resolve })
    const typer = setInterval(() => {
      if (thinking) return
      if (queue) {
        // Speed up gently when a long backlog is waiting.
        const n = Math.max(TYPE_CHARS_PER_TICK, Math.ceil(queue.length / 120))
        const piece = queue.slice(0, n)
        queue = queue.slice(n)
        setOrbMode('speaking')
        patch((m) => ({ ...m, content: m.content + piece }))
      } else if (streamEnded) {
        clearInterval(typer)
        finishTyping()
      }
    }, TYPE_TICK_MS)
    setTimeout(() => { thinking = false }, THINKING_MS)
    ctrl.signal.addEventListener('abort', () => {
      // Stop pressed: show what has arrived immediately.
      thinking = false
      if (queue) {
        const rest = queue
        queue = ''
        patch((m) => ({ ...m, content: m.content + rest }))
      }
    })

    await streamChat(
      { user_id: userId, conversation_id: convId, message: text, regenerate },
      {
        onMeta: ({ conversation_id }) => {
          if (conversation_id !== convId) {
            activeIdRef.current = conversation_id
            skipLoadRef.current = conversation_id
            navigate(`/chat/${conversation_id}`, { replace: !convId })
          }
        },
        onAnalysis: (a) => {
          setAnalysis(a)
          setPalette(a.decision.palette)
          setPaletteName(a.decision.background)
          setMessages((prev) => {
            const lastUser = prev.map((m) => m.role).lastIndexOf('user')
            return prev.map((m, i) => (i === lastUser ? { ...m, emotion: a.fusion } : m.id === assistantId
              ? { ...m, stage: 'composing', strategy: a.decision.strategy, safety: a.safety.level === 'crisis' || a.safety.level === 'elevated' ? { level: a.safety.level, helplines: a.safety.helplines } : undefined }
              : m))
          })
        },
        onToken: (t) => { queue += t },
        onDone: (d) => { doneData = d },
        onError: (msg) => patch((m) => ({ ...m, streaming: false, error: msg })),
      },
      ctrl.signal,
    )
    streamEnded = true
    await typingDone
    if (doneData) {
      const d: Done = doneData
      setDone(d)
      patch((m) => ({ ...m, content: d.text, streaming: false, latency: d.latency }))
      refreshList()
    }
    patch((m) => (m.streaming ? { ...m, streaming: false } : m))
    setStreaming(false)
    setOrbMode('idle')
    abortRef.current = null
  }, [navigate, refreshList, userId])

  const send = (text?: string) => {
    const t = (text ?? input).trim()
    if (!t || streaming) return
    setInput('')
    run(t)
  }
  const stop = () => abortRef.current?.abort()
  const regenerate = () => { if (!streaming) run('', true) }
  const newChat = () => {
    abortRef.current?.abort()
    activeIdRef.current = null
    setSidebar(false)
    setMessages([]); setAnalysis(null); setDone(null); setPalette(null); setPaletteName('neutral_black')
    navigate('/chat')
  }
  const logout = () => {
    abortRef.current?.abort()
    activeIdRef.current = null
    setLogoutOpen(false)
    try { sessionStorage.clear() } catch { /* storage unavailable */ }
    navigate('/', { replace: true })
  }
  const toggleInsights = () => setInsights((v) => { writePref('senra.insights', !v); return !v })

  const copy = (m: UIMessage) => {
    navigator.clipboard?.writeText(m.content)
    setCopied(m.id)
    setTimeout(() => setCopied(null), 1400)
  }

  const llmProblem = healthErr
    ? 'The SENRA backend is not reachable. Start it with start.bat (or uvicorn on port 8000).'
    : health && !health.llm.reachable
      ? 'Ollama is not running. Start Ollama, then try again.'
      : health && health.llm.model_available === false
        ? `Model ${health.llm.model} is not installed. Run: ollama pull ${health.llm.model}`
        : null

  const empty = messages.length === 0
  const lastAssistantIdx = messages.map((m) => m.role).lastIndexOf('assistant')

  return (
    <div className="flex h-[100dvh] overflow-hidden text-white">
      <Ambient palette={palette} />

      {/* sidebar */}
      <div className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition lg:hidden ${sidebar ? 'opacity-100' : 'pointer-events-none opacity-0'}`} onClick={() => setSidebar(false)} />
      <aside className={`fixed inset-y-0 left-0 z-50 w-[280px] border-r border-white/[0.06] transition-transform duration-300 lg:static lg:z-auto lg:translate-x-0 ${sidebar ? 'translate-x-0' : '-translate-x-full'}`}>
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={(id) => { activeIdRef.current = id; setSidebar(false); navigate(`/chat/${id}`) }}
          onNew={newChat}
          onDelete={async (id) => { await api.deleteConversation(userId, id); refreshList(); if (id === activeIdRef.current) newChat() }}
          onRename={async (id, title) => { await api.renameConversation(userId, id, title); refreshList() }}
          onOpenMemory={() => { setSidebar(false); setMemoryOpen(true) }}
          onLogout={() => { setSidebar(false); setLogoutOpen(true) }}
          onClose={() => setSidebar(false)}
        />
      </aside>

      {/* main column */}
      <main className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 px-3 pb-2 pt-3 sm:px-5">
          <button onClick={() => setSidebar(true)} className="grid h-10 w-10 place-items-center rounded-full bg-white/[0.06] ring-1 ring-white/10 lg:hidden" aria-label="Open conversations">
            <Menu className="h-[18px] w-[18px]" />
          </button>
          <div className="mx-auto flex items-center gap-2.5 rounded-full bg-white/[0.06] py-1.5 pl-1.5 pr-4 ring-1 ring-white/10 backdrop-blur">
            <span className="relative grid h-8 w-8 place-items-center overflow-hidden rounded-full bg-black">
              {empty ? <Logo className="h-6 w-6" /> : <Orb mode={orbMode} palette={paletteName} detail="low" className="absolute -inset-2 h-12 w-12" />}
            </span>
            <span className="leading-tight">
              <span className="block text-[13.5px] font-medium">SENRA</span>
              <span className="block text-[11px] text-white/45">
                {streaming ? (orbMode === 'thinking' ? 'Sensing how you feel…' : 'Responding…') : 'AI Companion'}
              </span>
            </span>
          </div>
          <button onClick={newChat} className="grid h-10 w-10 place-items-center rounded-full bg-white/[0.06] ring-1 ring-white/10 lg:hidden" aria-label="New conversation">
            <PenSquare className="h-[17px] w-[17px]" />
          </button>
          <button onClick={toggleInsights} aria-pressed={insights}
            className={`hidden h-10 items-center gap-2 rounded-full px-3.5 text-[13px] ring-1 transition lg:flex ${insights ? 'bg-white text-black ring-white' : 'bg-white/[0.06] text-white/75 ring-white/10 hover:bg-white/10'}`}>
            <Activity className="h-4 w-4" /> Insights
          </button>
          <button onClick={toggleInsights} aria-label="Toggle insights" className={`grid h-10 w-10 place-items-center rounded-full ring-1 lg:hidden ${insights ? 'bg-white text-black ring-white' : 'bg-white/[0.06] ring-white/10'}`}>
            <Activity className="h-[17px] w-[17px]" />
          </button>
        </header>

        {llmProblem && (
          <div className="mx-auto mt-1 flex w-[calc(100%-2rem)] max-w-3xl items-center gap-2 rounded-xl border border-amber-400/25 bg-amber-400/[0.07] px-3.5 py-2.5 text-[13px] text-amber-100">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" /> {llmProblem}
          </div>
        )}

        {/* messages / empty state */}
        <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
          {empty ? (
            <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-4 pb-6 text-center">
              <div className="w-[min(64vw,300px)] animate-float sm:w-[320px]">
                <Orb mode={orbMode} palette={paletteName} className="aspect-square w-full" />
              </div>
              <p className="mt-1 text-[15px] text-white/55">{greeting()}, I’m SENRA.</p>
              <h1 className="mt-1.5 font-serif text-[36px] leading-tight sm:text-[46px]">How are you feeling today?</h1>
              <div className="mt-7 flex max-w-2xl flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s.label} onClick={() => send(s.label)}
                    className="flex items-center gap-2 rounded-full bg-white/[0.05] px-3.5 py-2 text-[13px] text-white/75 ring-1 ring-white/10 transition hover:bg-white/10 hover:text-white">
                    <span className="text-white/40">{s.icon}</span>{s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-3xl px-4 pb-10 pt-4 sm:px-6">
              {messages.map((m, i) => m.role === 'user' ? (
                <div key={m.id} className="mb-6 flex animate-fade-up flex-col items-end">
                  <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-3xl rounded-br-lg bg-white/[0.09] px-4 py-2.5 text-[15px] leading-relaxed text-white/95 ring-1 ring-white/[0.08]">
                    {m.content}
                  </div>
                  {insights && m.emotion && (
                    <span className="mt-1.5 flex items-center gap-1.5 pr-1 font-mono text-[10.5px] text-white/40">
                      <span className="h-1.5 w-1.5 rounded-full bg-[var(--env-accent)]" />
                      sensed {m.emotion.emotion} · {m.emotion.intensity_level} · {(m.emotion.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              ) : (
                <div key={m.id} className="group mb-8 flex animate-fade-up gap-3">
                  <span className="mt-1 h-7 w-7 shrink-0 rounded-full bg-[radial-gradient(circle_at_30%_25%,#ffb36b,#ff3ea5_45%,#8a5cff_80%,#3b82f6)] shadow-[0_0_18px_-2px_var(--env-accent)]" />
                  <div className="min-w-0 flex-1">
                    {m.error ? (
                      <div className="rounded-xl border border-rose-400/25 bg-rose-500/[0.07] px-3.5 py-2.5 text-[13.5px] text-rose-100">{m.error}</div>
                    ) : m.content ? (
                      <div className={m.streaming ? 'caret-wrap' : ''}>
                        <Markdown text={m.content} />
                      </div>
                    ) : (
                      <div className="flex h-7 items-center gap-2 text-[13px] text-white/45">
                        <span className="flex gap-1">
                          {[0, 1, 2].map((d) => <span key={d} className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-[var(--env-accent)]" style={{ animationDelay: `${d * 0.18}s` }} />)}
                        </span>
                        <span className="thinking-shimmer">{m.stage === 'composing' ? 'Thinking…' : 'Sensing how you feel…'}</span>
                      </div>
                    )}
                    {m.safety && !m.streaming && <SafetyCard level={m.safety.level} helplines={m.safety.helplines} />}
                    {!m.streaming && !m.error && m.content && (
                      <div className="mt-2 flex items-center gap-1 text-white/40">
                        <button onClick={() => copy(m)} className="rounded-md p-1.5 hover:bg-white/5 hover:text-white" aria-label="Copy reply">
                          {copied === m.id ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                        </button>
                        {i === lastAssistantIdx && (
                          <button onClick={regenerate} disabled={streaming} className="rounded-md p-1.5 hover:bg-white/5 hover:text-white" aria-label="Regenerate reply">
                            <RotateCcw className="h-3.5 w-3.5" />
                          </button>
                        )}
                        {insights && m.strategy && (
                          <span className="ml-1 font-mono text-[10.5px] text-white/35">
                            {m.strategy.replace(/_/g, ' ')}{m.latency ? ` · ${(m.latency.total_ms / 1000).toFixed(1)}s` : ''}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* composer */}
        <div className="px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-1 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Composer value={input} onChange={setInput} onSend={() => send()} onStop={stop} streaming={streaming} autoFocus />
            <p className="mt-2 text-center text-[11px] leading-snug text-white/35">
              SENRA is an AI companion, not a therapist. In crisis? Call <a href="tel:14416" className="underline hover:text-white/70">Tele-MANAS 14416</a> or <a href="tel:112" className="underline hover:text-white/70">112</a>.
            </p>
          </div>
        </div>
      </main>

      {/* insights */}
      {insights && (
        <>
          <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={toggleInsights} />
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-[400px] border-l border-white/[0.06] lg:static lg:z-auto lg:w-[380px]">
            <InsightsPanel analysis={analysis} done={done} onClose={toggleInsights} />
          </div>
        </>
      )}

      {memoryOpen && <MemoryDialog userId={userId} onClose={() => setMemoryOpen(false)} />}

      {logoutOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm" onClick={() => setLogoutOpen(false)}>
          <div role="dialog" aria-modal="true" aria-label="Log out" onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm animate-fade-up rounded-3xl border border-white/10 bg-[#0b0b10] p-6 text-center shadow-2xl">
            <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white/5 ring-1 ring-white/10"><LogOut className="h-5 w-5" /></span>
            <h2 className="mt-4 text-base font-medium">Log out of SENRA?</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-white/55">This ends your current session. Your conversations stay saved on this device for next time.</p>
            <div className="mt-6 grid grid-cols-2 gap-2">
              <button onClick={() => setLogoutOpen(false)} className="rounded-xl bg-white/[0.06] py-2.5 text-sm text-white/80 ring-1 ring-white/10 hover:bg-white/10">Cancel</button>
              <button onClick={logout} className="rounded-xl bg-white py-2.5 text-sm font-medium text-black hover:bg-white/90">Log out</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

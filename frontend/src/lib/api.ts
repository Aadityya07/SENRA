// SENRA API client — REST + Server-Sent Events over fetch streams.

export type Palette = { from: string; to: string; accent: string }

export type Fusion = {
  emotion: string
  dominant: string
  ekman: Record<string, number>
  valence: number
  arousal: number
  intensity: number
  intensity_level: 'low' | 'medium' | 'high'
  confidence: number
  agreement: number
  modalities: string[]
  weights: Record<string, number>
}

export type Decision = {
  intent: string
  strategy: string
  priority: string
  length: string
  tone: string
  avatar_emotion: string
  voice_style: string
  voice: { rate: number; pitch: number; pause_ms: number; energy: number }
  gesture: string
  background: string
  palette: Palette
  guidance: string[]
  wellbeing_nudge: boolean
}

export type Helpline = { name: string; contact: string; href: string }

export type Safety = {
  level: 'none' | 'low' | 'elevated' | 'crisis'
  score: number
  categories: string[]
  escalate: boolean
  reasons: string[]
  helplines: Helpline[]
}

export type Analysis = {
  user_message_id: string | null
  perception: {
    text: {
      label: string
      ekman: Record<string, number>
      valence: number
      arousal: number
      intensity: number
      confidence: number
      top_labels: [string, number][]
      cues: string[]
      source: string
      latency_ms: number
    }
  }
  fusion: Fusion
  context: {
    trend: {
      trend: 'improving' | 'stable' | 'worsening' | 'new'
      smoothed_valence: number
      smoothed_arousal: number
      delta: number
      turns: number
      history: { emotion: string; valence: number; smoothed: number; intensity: number }[]
    }
    memory: Record<string, unknown>
    memory_updates: string[]
  }
  safety: Safety
  decision: Decision
  orchestration: { structured_context: Record<string, unknown>; briefing: string }
  timings: Record<string, number>
  llm: { provider: string; model: string }
}

export type Structured = {
  speech: string
  tone: string
  emotion: string
  voice_style: string
  facial_expression: string
  gesture: string
  background: string
  palette: Palette
  safety: { level: string; escalated: boolean }
  show_helplines: boolean
}

export type Done = {
  message_id: string
  conversation_id: string
  text: string
  replaced: boolean
  structured: Structured
  validation: { passed: boolean; violations: string[] }
  latency: { total_ms: number; llm_ms: number; first_token_ms: number }
}

export type Message = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  meta: Record<string, any>
  created_at: number
}

export type Conversation = {
  conversation_id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
}

export type Health = {
  status: string
  phase: number
  llm: { provider: string; model: string; reachable: boolean; model_available?: boolean }
  text_emotion: { model: string; status: string }
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => json<Health>('/api/health'),
  conversations: (uid: string) => json<Conversation[]>(`/api/users/${uid}/conversations`),
  conversation: (uid: string, cid: string) =>
    json<Conversation & { messages: Message[] }>(`/api/conversations/${cid}?user_id=${uid}`),
  deleteConversation: (uid: string, cid: string) =>
    json(`/api/conversations/${cid}?user_id=${uid}`, { method: 'DELETE' }),
  renameConversation: (uid: string, cid: string, title: string) =>
    json(`/api/conversations/${cid}?user_id=${uid}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  memory: (uid: string) =>
    json<{ memory_enabled: boolean; items: any[]; profile: any }>(`/api/users/${uid}/memory`),
  setMemory: (uid: string, enabled: boolean) =>
    json(`/api/users/${uid}/memory`, { method: 'PUT', body: JSON.stringify({ memory_enabled: enabled }) }),
  clearMemory: (uid: string, id?: number) =>
    json(`/api/users/${uid}/memory${id != null ? `?memory_id=${id}` : ''}`, { method: 'DELETE' }),
}

export type StreamHandlers = {
  onMeta?: (d: { conversation_id: string }) => void
  onAnalysis?: (d: Analysis) => void
  onToken?: (t: string) => void
  onDone?: (d: Done) => void
  onError?: (msg: string) => void
}

export async function streamChat(
  body: { user_id: string; conversation_id?: string | null; message: string; regenerate?: boolean },
  h: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(BASE + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    h.onError?.('Cannot reach the SENRA backend. Is it running on port 8000?')
    return
  }
  if (!res.ok || !res.body) {
    h.onError?.(`Server error (${res.status}).`)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        let event = 'message'
        let data = ''
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (!data) continue
        const parsed = JSON.parse(data)
        if (event === 'meta') h.onMeta?.(parsed)
        else if (event === 'analysis') h.onAnalysis?.(parsed)
        else if (event === 'token') h.onToken?.(parsed.t)
        else if (event === 'done') h.onDone?.(parsed)
        else if (event === 'error') h.onError?.(parsed.message)
      }
    }
  } catch (e: any) {
    if (e?.name !== 'AbortError') h.onError?.('The connection was interrupted.')
  }
}

export function getUserId(): string {
  const KEY = 'senra.user_id'
  try {
    let id = localStorage.getItem(KEY)
    if (!id) {
      id = 'u_' + crypto.randomUUID().replace(/-/g, '').slice(0, 20)
      localStorage.setItem(KEY, id)
    }
    return id
  } catch {
    return 'u_guest_session'
  }
}

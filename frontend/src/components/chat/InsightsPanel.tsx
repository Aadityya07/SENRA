import { useState } from 'react'
import { Activity, Brain, ChevronDown, Compass, Cpu, Layers, Shield, Sparkles, X } from 'lucide-react'
import type { Analysis, Done } from '../../lib/api'

const EKMAN_COLORS: Record<string, string> = {
  joy: '#fbbf24', sadness: '#60a5fa', anger: '#f87171', fear: '#a78bfa',
  surprise: '#34d399', disgust: '#a3e635', neutral: '#94a3b8',
}

function Bar({ value, color = 'var(--env-accent)' }: { value: number; color?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.max(2, value * 100)}%`, background: color }} />
    </div>
  )
}

function Section({ icon: Icon, title, children, tag }: { icon: any; title: string; children: React.ReactNode; tag?: string }) {
  return (
    <section className="border-b border-white/[0.06] px-5 py-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-white/50" />
        <h3 className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/55">{title}</h3>
        {tag && <span className="ml-auto font-mono text-[10px] text-white/30">{tag}</span>}
      </div>
      {children}
    </section>
  )
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-white/[0.03] px-2.5 py-2 ring-1 ring-white/[0.06]">
      <div className="text-[10px] uppercase tracking-wider text-white/35">{k}</div>
      <div className="mt-0.5 truncate text-[12.5px] text-white/85">{v}</div>
    </div>
  )
}

function Circumplex({ v, a }: { v: number; a: number }) {
  const x = 60 + v * 50
  const y = 110 - a * 100
  return (
    <svg viewBox="0 0 120 120" className="h-28 w-28 shrink-0">
      <rect x="1" y="1" width="118" height="118" rx="12" fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.08)" />
      <line x1="60" y1="8" x2="60" y2="112" stroke="rgba(255,255,255,0.1)" />
      <line x1="8" y1="60" x2="112" y2="60" stroke="rgba(255,255,255,0.1)" />
      <text x="112" y="56" textAnchor="end" fontSize="8" fill="rgba(255,255,255,0.35)">+V</text>
      <text x="9" y="56" fontSize="8" fill="rgba(255,255,255,0.35)">−V</text>
      <text x="63" y="15" fontSize="8" fill="rgba(255,255,255,0.35)">high A</text>
      <circle cx={x} cy={y} r="10" fill="var(--env-accent)" opacity="0.18" />
      <circle cx={x} cy={y} r="4.5" fill="var(--env-accent)" />
    </svg>
  )
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <p className="text-[12px] text-white/40">Trend appears after a few messages.</p>
  const w = 260, h = 54
  const xs = points.map((_, i) => (i / (points.length - 1)) * w)
  const ys = points.map((p) => h / 2 - p * (h / 2 - 4))
  const d = xs.map((x, i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-14 w-full">
      <line x1="0" y1={h / 2} x2={w} y2={h / 2} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 4" />
      <path d={d} fill="none" stroke="var(--env-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {xs.map((x, i) => <circle key={i} cx={x} cy={ys[i]} r="2.5" fill="var(--env-accent)" />)}
    </svg>
  )
}

const LEVEL_STYLE: Record<string, string> = {
  none: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/25',
  low: 'bg-sky-400/10 text-sky-300 ring-sky-400/25',
  elevated: 'bg-amber-400/10 text-amber-300 ring-amber-400/25',
  crisis: 'bg-rose-500/15 text-rose-300 ring-rose-400/30',
}

export default function InsightsPanel({ analysis, done, onClose }: { analysis: Analysis | null; done: Done | null; onClose: () => void }) {
  const [showBrief, setShowBrief] = useState(false)
  return (
    <aside className="flex h-full w-full flex-col bg-[#07070a]/95 backdrop-blur-xl lg:bg-black/40">
      <div className="flex items-center gap-3 border-b border-white/[0.06] px-5 py-4">
        <div>
          <h2 className="text-sm font-medium text-white/90">Pipeline insights</h2>
          <p className="text-[11.5px] text-white/40">Research view · what SENRA sensed and decided</p>
        </div>
        <button onClick={onClose} className="ml-auto rounded-lg p-1.5 text-white/50 hover:bg-white/5 hover:text-white" aria-label="Close insights">
          <X className="h-4 w-4" />
        </button>
      </div>

      {!analysis ? (
        <div className="grid flex-1 place-items-center px-8 text-center text-sm text-white/40">
          Send a message to see how it flows through perception, fusion, decision and generation.
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <Section icon={Brain} title="Emotion perception · text" tag={`${analysis.perception.text.latency_ms.toFixed(0)} ms`}>
            <div className="space-y-2">
              {analysis.perception.text.top_labels.slice(0, 5).map(([label, p]) => (
                <div key={label} className="grid grid-cols-[92px_1fr_40px] items-center gap-2 text-[12px]">
                  <span className="truncate text-white/70">{label}</span>
                  <Bar value={p} />
                  <span className="text-right font-mono text-white/45">{(p * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
            {analysis.perception.text.cues.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {analysis.perception.text.cues.map((c) => (
                  <span key={c} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-white/65 ring-1 ring-white/10">cue: {c}</span>
                ))}
              </div>
            )}
            <p className="mt-2 font-mono text-[10.5px] text-white/30">{analysis.perception.text.source}</p>
          </Section>

          <Section icon={Layers} title="Emotion fusion engine" tag={`modalities: ${analysis.fusion.modalities.join(', ')}`}>
            <div className="flex gap-4">
              <Circumplex v={analysis.fusion.valence} a={analysis.fusion.arousal} />
              <div className="min-w-0 flex-1 space-y-2.5">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-white/35">Current emotion</div>
                  <div className="font-serif text-[26px] capitalize leading-tight text-white">{analysis.fusion.emotion}</div>
                </div>
                <div className="text-[11.5px] text-white/55">
                  Intensity <span className="text-white/80">{analysis.fusion.intensity_level}</span>
                  <Bar value={analysis.fusion.intensity} />
                </div>
                <div className="text-[11.5px] text-white/55">
                  Confidence <span className="text-white/80">{(analysis.fusion.confidence * 100).toFixed(0)}%</span>
                  <Bar value={analysis.fusion.confidence} color="#94a3b8" />
                </div>
              </div>
            </div>
            <div className="mt-3 flex h-2 overflow-hidden rounded-full">
              {Object.entries(analysis.fusion.ekman).map(([k, p]) => (
                <div key={k} title={`${k} ${(p * 100).toFixed(0)}%`} style={{ width: `${p * 100}%`, background: EKMAN_COLORS[k] }} />
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-white/45">
              {Object.entries(analysis.fusion.ekman).filter(([, p]) => p > 0.04).map(([k, p]) => (
                <span key={k} className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full" style={{ background: EKMAN_COLORS[k] }} />{k} {(p * 100).toFixed(0)}%</span>
              ))}
            </div>
            <p className="mt-2 font-mono text-[10.5px] text-white/30">
              V {analysis.fusion.valence.toFixed(2)} · A {analysis.fusion.arousal.toFixed(2)} · weights {Object.entries(analysis.fusion.weights).map(([k, w]) => `${k}:${w.toFixed(2)}`).join(' ')}
            </p>
          </Section>

          <Section icon={Activity} title="Emotion context" tag={`${analysis.context.trend.turns} turns`}>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[12px] text-white/55">Emotional trend</span>
              <span className="text-[13px] capitalize text-white/90">{analysis.context.trend.trend}</span>
            </div>
            <Sparkline points={analysis.context.trend.history.map((h) => h.smoothed)} />
            {analysis.context.memory_updates.length > 0 && (
              <p className="mt-2 text-[11.5px] text-white/50">Memory updated: <span className="text-white/75">{analysis.context.memory_updates.join(', ')}</span></p>
            )}
          </Section>

          <Section icon={Shield} title="Risk detection & safety">
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2.5 py-0.5 text-[11.5px] capitalize ring-1 ${LEVEL_STYLE[analysis.safety.level]}`}>{analysis.safety.level}</span>
              {done && <span className={`rounded-full px-2.5 py-0.5 text-[11.5px] ring-1 ${done.validation.passed ? LEVEL_STYLE.none : LEVEL_STYLE.elevated}`}>output {done.validation.passed ? 'validated' : 'corrected'}</span>}
            </div>
            {analysis.safety.reasons.map((r) => <p key={r} className="mt-2 text-[12px] text-white/55">{r}</p>)}
          </Section>

          <Section icon={Compass} title="Companion decision engine">
            <div className="grid grid-cols-2 gap-2">
              <KV k="Intent" v={analysis.decision.intent.replace(/_/g, ' ')} />
              <KV k="Strategy" v={analysis.decision.strategy.replace(/_/g, ' ')} />
              <KV k="Priority" v={analysis.decision.priority} />
              <KV k="Length" v={analysis.decision.length} />
              <KV k="Avatar" v={analysis.decision.avatar_emotion.replace(/_/g, ' ')} />
              <KV k="Gesture" v={analysis.decision.gesture.replace(/_/g, ' ')} />
              <KV k="Voice" v={`${analysis.decision.voice_style.replace(/_/g, ' ')} · ${analysis.decision.voice.rate}x`} />
              <KV k="Environment" v={<span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full ring-1 ring-white/20" style={{ background: `linear-gradient(135deg, ${analysis.decision.palette.to}, ${analysis.decision.palette.accent})` }} />{analysis.decision.background.replace(/_/g, ' ')}</span>} />
            </div>
            <p className="mt-2 text-[12px] text-white/55">Tone: <span className="text-white/80">{analysis.decision.tone}</span></p>
          </Section>

          <Section icon={Sparkles} title="Prompt orchestration">
            <button onClick={() => setShowBrief((s) => !s)} className="flex w-full items-center justify-between text-[12px] text-white/60 hover:text-white">
              Structured context sent to the LLM
              <ChevronDown className={`h-3.5 w-3.5 transition ${showBrief ? 'rotate-180' : ''}`} />
            </button>
            {showBrief && (
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-black/60 p-3 font-mono text-[10.5px] leading-relaxed text-white/60 ring-1 ring-white/[0.06]">
                {JSON.stringify(analysis.orchestration.structured_context, null, 2)}
                {'\n\n— briefing —\n'}
                {analysis.orchestration.briefing}
              </pre>
            )}
          </Section>

          <Section icon={Cpu} title="Reasoning engine & latency" tag={`${analysis.llm.provider} · ${analysis.llm.model}`}>
            <div className="grid grid-cols-3 gap-2">
              <KV k="Perception" v={`${analysis.timings.perception_ms?.toFixed(0)} ms`} />
              <KV k="Fusion+ctx" v={`${((analysis.timings.fusion_ms ?? 0) + (analysis.timings.context_ms ?? 0)).toFixed(1)} ms`} />
              <KV k="Safety+dec." v={`${((analysis.timings.safety_ms ?? 0) + (analysis.timings.decision_ms ?? 0)).toFixed(1)} ms`} />
              <KV k="1st token" v={done ? `${done.latency.first_token_ms} ms` : '…'} />
              <KV k="LLM" v={done ? `${(done.latency.llm_ms / 1000).toFixed(1)} s` : '…'} />
              <KV k="Total" v={done ? `${(done.latency.total_ms / 1000).toFixed(1)} s` : '…'} />
            </div>
          </Section>
        </div>
      )}
    </aside>
  )
}

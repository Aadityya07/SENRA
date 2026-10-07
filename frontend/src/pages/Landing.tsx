import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight, AudioLines, Brain, Camera, Compass, HeartHandshake, Layers, MessageCircle,
  Shield, Sparkles, SunMoon, Waves,
} from 'lucide-react'
import Orb from '../components/Orb'
import Logo from '../components/Logo'

/* ------------------------------------------------------------------ cards */

type Card =
  | { kind: 'quote'; who: 'user' | 'senra'; text: string; tag?: string; tint: string }
  | { kind: 'emotion'; from: string; to: string; tint: string }
  | { kind: 'wave'; label: string; tint: string }
  | { kind: 'env'; label: string; a: string; b: string }
  | { kind: 'metric'; label: string; value: string; tint: string }

const TINTS = {
  rose: 'from-[#ff3ea5]/25 via-[#2a0d1f]/40 to-transparent',
  violet: 'from-[#8a5cff]/25 via-[#150d2a]/40 to-transparent',
  blue: 'from-[#3b82f6]/25 via-[#0b1630]/40 to-transparent',
  amber: 'from-[#ff9d4d]/25 via-[#2a1608]/40 to-transparent',
  teal: 'from-[#3fd0c9]/20 via-[#06221f]/40 to-transparent',
}

const LAYERS: { depth: number; speed: number; top: string; cards: Card[] }[] = [
  {
    depth: 0.35, speed: 140, top: '12%',
    cards: [
      { kind: 'quote', who: 'user', text: 'I just moved here and I don’t really know anyone yet.', tag: 'lonely · 0.82', tint: TINTS.violet },
      { kind: 'env', label: 'Environment · black → dark blue', a: '#000000', b: '#0a1a3a' },
      { kind: 'metric', label: 'Emotional trend', value: 'Improving ↗', tint: TINTS.teal },
      { kind: 'quote', who: 'user', text: 'Everything feels like too much today.', tag: 'overwhelmed · high', tint: TINTS.blue },
      { kind: 'wave', label: 'Voice · softer, slower', tint: TINTS.rose },
      { kind: 'metric', label: 'Valence / Arousal', value: '−0.65 · 0.71', tint: TINTS.violet },
    ],
  },
  {
    depth: 0.65, speed: 100, top: '34%',
    cards: [
      { kind: 'quote', who: 'senra', text: 'Starting over somewhere new is hard. Tell me what your days look like.', tint: TINTS.rose },
      { kind: 'emotion', from: 'anxious', to: 'calmer', tint: TINTS.blue },
      { kind: 'quote', who: 'user', text: 'I got selected for the internship!!', tag: 'excited · 0.90', tint: TINTS.amber },
      { kind: 'metric', label: 'Safety layer', value: 'Active · independent', tint: TINTS.teal },
      { kind: 'quote', who: 'senra', text: 'You don’t have to figure everything out at once.', tint: TINTS.violet },
    ],
  },
  {
    depth: 1, speed: 70, top: '56%',
    cards: [
      { kind: 'metric', label: 'Memory', value: 'Prefers listening over advice', tint: TINTS.amber },
      { kind: 'quote', who: 'user', text: 'Talking to you actually helps a bit.', tag: 'grateful · rising', tint: TINTS.teal },
      { kind: 'wave', label: 'Presence · not performance', tint: TINTS.blue },
      { kind: 'emotion', from: 'frustrated', to: 'heard', tint: TINTS.rose },
    ],
  },
]

function Wave() {
  const bars = [6, 14, 22, 12, 28, 18, 34, 20, 26, 10, 18, 30, 14, 24, 8, 16, 26, 12]
  return (
    <div className="flex h-9 items-center gap-[3px]">
      {bars.map((h, i) => (
        <span key={i} className="w-[3px] rounded-full bg-white/70" style={{ height: h, opacity: 0.35 + (h / 34) * 0.6 }} />
      ))}
    </div>
  )
}

function FloatingCard({ card }: { card: Card }) {
  const base = 'relative w-[230px] shrink-0 overflow-hidden rounded-2xl border border-white/10 p-4 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.9)] sm:w-[260px]'
  if (card.kind === 'env') {
    return (
      <div className={base + ' bg-black/40'}>
        <div className="h-16 rounded-xl" style={{ background: `linear-gradient(90deg, ${card.a}, ${card.b})` }} />
        <p className="mt-3 text-[12px] text-white/70">{card.label}</p>
      </div>
    )
  }
  const tint = 'tint' in card ? card.tint : ''
  return (
    <div className={`${base} bg-gradient-to-br ${tint} bg-black/50 backdrop-blur-md`}>
      {card.kind === 'quote' && (
        <>
          <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-white/50">
            {card.who === 'senra' ? <Sparkles className="h-3 w-3" /> : <MessageCircle className="h-3 w-3" />}
            {card.who === 'senra' ? 'SENRA' : 'You'}
          </div>
          <p className="font-serif text-[19px] leading-snug text-white/90">“{card.text}”</p>
          {card.tag && <span className="mt-3 inline-block rounded-full bg-white/10 px-2.5 py-1 font-mono text-[10.5px] text-white/70">{card.tag}</span>}
        </>
      )}
      {card.kind === 'emotion' && (
        <>
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/50">Emotional shift</p>
          <p className="mt-2 font-serif text-[26px] leading-none text-white/90">
            {card.from} <span className="text-white/40">→</span> <em>{card.to}</em>
          </p>
        </>
      )}
      {card.kind === 'wave' && (
        <>
          <Wave />
          <p className="mt-2 text-[12px] text-white/70">{card.label}</p>
        </>
      )}
      {card.kind === 'metric' && (
        <>
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/50">{card.label}</p>
          <p className="mt-2 text-[17px] font-medium text-white/90">{card.value}</p>
        </>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- content */

const PIPELINE = [
  { icon: Brain, title: 'Perceive', body: 'A RoBERTa model trained on GoEmotions reads 28 fine-grained emotions from your words, combined with an affective cue lexicon.', tag: 'Text · live' },
  { icon: Layers, title: 'Fuse', body: 'Confidence-aware late fusion blends modalities with your recent emotional history into one state: emotion, intensity, confidence, valence, arousal.', tag: 'Core research' },
  { icon: Compass, title: 'Decide', body: 'The Companion Decision Engine picks a strategy — comfort, ground, de-escalate, celebrate or inform — plus tone, voice style, gesture and environment.', tag: 'Core research' },
  { icon: Sparkles, title: 'Generate', body: 'A context-aware prompt carries everything upstream to a local Gemma 2 (2B) model, which writes the words — the LLM is one module, not the whole system.', tag: 'Local LLM' },
  { icon: SunMoon, title: 'Act', body: 'The Response Controller turns the reply into directives for the environment today, and for voice and avatar in the next phases.', tag: 'Actuation' },
]

const PRINCIPLES = [
  { icon: HeartHandshake, title: 'Presence over information', body: 'Sometimes the right response is simply acknowledgement, calm and companionship — not more advice.' },
  { icon: Waves, title: 'Subtlety over exaggeration', body: 'No dramatic reactions. The environment changes over seconds, never flashes, and follows your trend, not a single message.' },
  { icon: Shield, title: 'Trust over engagement', body: 'No streaks, no guilt notifications, no “I’m all you need”. SENRA encourages real human connection.' },
  { icon: Shield, title: 'Responsible by design', body: 'An independent safety layer checks every message and every reply. SENRA is an AI companion — never a therapist.' },
]

const PHASES = [
  { n: '01', title: 'Chat & emotional intelligence', status: 'Live now', items: ['Text emotion perception', 'Emotion fusion & trend tracking', 'Emotional memory (opt-in)', 'Decision engine + local LLM', 'Safety & crisis escalation'], active: true, icon: MessageCircle },
  { n: '02', title: 'Voice & camera', status: 'Next', items: ['faster-whisper speech recognition', 'Speech emotion (wav2vec2 / WavLM)', 'Facial emotion (MediaPipe + DeepFace)', 'Multimodal fusion', 'Emotion-adaptive TTS'], active: false, icon: Camera },
  { n: '03', title: 'Embodied avatar', status: 'Final', items: ['VRM avatar in Unity', 'Lip-sync with uLipSync', 'Expressions, gaze & gestures', 'Idle micro-movements', 'Environment lighting'], active: false, icon: AudioLines },
]

/* ------------------------------------------------------------------- page */

export default function Landing() {
  const stageRef = useRef<HTMLDivElement>(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const x = e.clientX / window.innerWidth - 0.5
      const y = e.clientY / window.innerHeight - 0.5
      setTilt({ x, y })
    }
    window.addEventListener('pointermove', onMove)
    return () => window.removeEventListener('pointermove', onMove)
  }, [])

  return (
    <div className="min-h-full bg-black text-white">
      {/* ---------------------------------------------------------- HERO */}
      <section className="relative isolate h-[100svh] min-h-[680px] overflow-hidden">
        {/* stage lighting */}
        <div className="absolute inset-0 -z-20 bg-[radial-gradient(90%_60%_at_50%_0%,#1a1022_0%,#07060a_55%,#000_100%)]" />
        <div className="absolute inset-x-0 top-0 -z-10 h-40 bg-gradient-to-b from-black to-transparent" />

        {/* floating panels in depth */}
        <div ref={stageRef} className="absolute inset-0 -z-10 [perspective:1400px]">
          <div
            className="absolute inset-0 transition-transform duration-700 ease-out [transform-style:preserve-3d]"
            style={{ transform: `rotateX(${tilt.y * -4}deg) rotateY(${tilt.x * 6}deg)` }}
          >
            {LAYERS.map((layer, li) => (
              <div
                key={li}
                className="absolute left-0 w-full"
                style={{
                  top: layer.top,
                  transform: `translate3d(${tilt.x * -40 * layer.depth}px, ${tilt.y * -20 * layer.depth}px, ${(layer.depth - 1) * 420}px)`,
                  filter: layer.depth < 0.5 ? 'blur(2.5px) brightness(0.55)' : layer.depth < 0.9 ? 'blur(0.8px) brightness(0.75)' : 'brightness(0.95)',
                  opacity: layer.depth < 0.5 ? 0.7 : 0.9,
                }}
              >
                <div className="flex w-max gap-10 animate-drift" style={{ animationDuration: `${layer.speed}s`, animationDirection: li % 2 ? 'reverse' : 'normal' }}>
                  {[...layer.cards, ...layer.cards, ...layer.cards, ...layer.cards].map((c, i) => (
                    <div key={i} style={{ transform: `translateY(${(i % 3) * 26 - 20}px)` }}>
                      <FloatingCard card={c} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {/* vignette keeps the centre readable */}
          <div className="absolute inset-0 bg-[radial-gradient(46%_56%_at_50%_45%,rgba(0,0,0,0.94)_0%,rgba(0,0,0,0.75)_50%,rgba(0,0,0,0.2)_85%,transparent_100%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(120%_100%_at_50%_50%,transparent_55%,#000_100%)]" />
        </div>

        {/* floor */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[34%]">
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#140b06]/80 to-[#1d1108]" />
          <div className="absolute inset-x-[-20%] bottom-0 h-full origin-bottom opacity-40 [transform:perspective(600px)_rotateX(62deg)] [background-image:repeating-linear-gradient(90deg,rgba(255,180,120,0.08)_0px,rgba(255,180,120,0.08)_1px,transparent_1px,transparent_90px),repeating-linear-gradient(0deg,rgba(255,180,120,0.06)_0px,rgba(255,180,120,0.06)_1px,transparent_1px,transparent_60px)]" />
          <div className="absolute left-1/2 top-[18%] h-[70%] w-[70%] -translate-x-1/2 rounded-[50%] bg-[radial-gradient(closest-side,rgba(255,140,70,0.32),rgba(255,62,165,0.12)_45%,transparent)] blur-2xl" />
        </div>

        {/* nav */}
        <header className="absolute inset-x-0 top-0 z-20">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
            <Link to="/" className="flex items-center gap-2.5">
              <Logo className="h-7 w-7" />
              <span className="text-[15px] font-semibold tracking-[0.18em]">SENRA</span>
            </Link>
            <nav className="hidden items-center gap-8 text-sm text-white/60 md:flex">
              <a href="#how" className="transition hover:text-white">How it works</a>
              <a href="#principles" className="transition hover:text-white">Principles</a>
              <a href="#roadmap" className="transition hover:text-white">Roadmap</a>
            </nav>
            <Link to="/chat" className="rounded-full bg-white px-4 py-2 text-[13px] font-medium text-black transition hover:bg-white/90">
              Start talking
            </Link>
          </div>
        </header>

        {/* headline */}
        <div className="relative z-10 mx-auto flex h-full max-w-5xl flex-col items-center px-5 pt-[clamp(88px,14vh,160px)] text-center">
          <motion.span
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[12px] text-amber-200/90 backdrop-blur"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-amber-300 shadow-[0_0_10px_#fcd34d]" />
            Emotion-aware AI companion · Phase 1 live
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.1 }}
            className="font-serif text-[42px] leading-[1.02] tracking-[-0.01em] text-white sm:text-[clamp(52px,7.5vh,64px)] lg:text-[clamp(56px,9vh,80px)]"
          >
            A companion that hears <br className="hidden sm:block" />
            <em className="text-gradient pr-2">how</em> you feel, not just what you say.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.25 }}
            className="mt-5 max-w-xl text-[15px] leading-relaxed text-white/65 sm:text-base"
          >
            SENRA senses the emotion behind your words, follows how it changes, and adapts its tone, pace and
            presence — so you feel heard, understood and a little less alone.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.4 }}
            className="relative z-20 mt-7 flex flex-wrap items-center justify-center gap-3"
          >
            <Link to="/chat" className="btn-orb group inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium text-white">
              Talk to SENRA <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
            <a href="#how" className="rounded-full border border-white/30 bg-black/85 px-6 py-3 text-sm font-medium text-white shadow-[0_8px_30px_-10px_rgba(0,0,0,0.9)] backdrop-blur-md transition hover:border-white/50 hover:bg-black/80">
              See how it works
            </a>
          </motion.div>

          {/* orb on stage */}
          {/* Sits in the normal flow below the buttons, so it can never cover them. */}
          <div className="pointer-events-none relative mt-2 min-h-[170px] w-full flex-1">
            <motion.div
              className="absolute left-1/2 top-0 aspect-square h-[150%] max-h-[600px] max-w-[92vw] -translate-x-1/2 -translate-y-[9%]"
              initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 1.4, delay: 0.3 }}
            >
              <div className="absolute inset-[16%] rounded-full bg-[radial-gradient(closest-side,#000_70%,rgba(0,0,0,0.6)_88%,transparent)]" />
              <Orb className="relative h-full w-full" />
            </motion.div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ PIPELINE */}
      <section id="how" className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
        <SectionHead
          kicker="Perception → Fusion → Decision → Generation → Actuation"
          title={<>Not a chatbot. A layered <em>affective</em> system.</>}
          body="Every message flows through specialised modules before the language model writes a single word. The LLM is the voice — the understanding happens around it."
        />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {PIPELINE.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: i * 0.07 }}
              className="glass relative rounded-2xl p-5"
            >
              <div className="flex items-center justify-between">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/5 ring-1 ring-white/10">
                  <s.icon className="h-5 w-5 text-white/85" />
                </span>
                <span className="font-mono text-[11px] text-white/35">0{i + 1}</span>
              </div>
              <h3 className="mt-5 font-serif text-[28px] leading-none">{s.title}</h3>
              <p className="mt-3 text-[13.5px] leading-relaxed text-white/60">{s.body}</p>
              <span className="mt-4 inline-block rounded-full bg-white/5 px-2.5 py-1 text-[11px] text-white/55 ring-1 ring-white/10">{s.tag}</span>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------- PRINCIPLES */}
      <section id="principles" className="relative border-y border-white/5 bg-[radial-gradient(60%_80%_at_50%_0%,#120c1c,transparent)]">
        <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
          <SectionHead
            kicker="Design principles"
            title={<>Built for <em>presence</em>, not for screen time.</>}
            body="SENRA is designed around calm, minimal interaction and clear boundaries — the opposite of an engagement machine."
          />
          <div className="mt-14 grid gap-4 md:grid-cols-2">
            {PRINCIPLES.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.06 }}
                className="glass flex gap-5 rounded-2xl p-6"
              >
                <p.icon className="mt-1 h-5 w-5 shrink-0 text-white/70" />
                <div>
                  <h3 className="text-lg font-medium">{p.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/60">{p.body}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------- ROADMAP */}
      <section id="roadmap" className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
        <SectionHead
          kicker="Three-phase roadmap"
          title={<>First the <em>brain</em>. Then the senses. Then the body.</>}
          body="Phase 1 establishes conversation quality, emotional response quality, safety and context — the foundation every later phase builds on."
        />
        <div className="mt-14 grid gap-4 lg:grid-cols-3">
          {PHASES.map((p) => (
            <div key={p.n} className={`relative overflow-hidden rounded-2xl p-6 ${p.active ? 'border border-white/15 bg-gradient-to-b from-[#2a1030]/70 to-black' : 'glass'}`}>
              {p.active && <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[#ff3ea5]/20 blur-3xl" />}
              <div className="relative flex items-center justify-between">
                <span className="font-mono text-sm text-white/40">PHASE {p.n}</span>
                <span className={`rounded-full px-2.5 py-1 text-[11px] ${p.active ? 'bg-emerald-400/15 text-emerald-300 ring-1 ring-emerald-400/30' : 'bg-white/5 text-white/50 ring-1 ring-white/10'}`}>{p.status}</span>
              </div>
              <p.icon className="relative mt-6 h-6 w-6 text-white/80" />
              <h3 className="relative mt-3 font-serif text-[30px] leading-tight">{p.title}</h3>
              <ul className="relative mt-4 space-y-2 text-sm text-white/60">
                {p.items.map((it) => (
                  <li key={it} className="flex items-start gap-2">
                    <span className={`mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full ${p.active ? 'bg-[#ff3ea5]' : 'bg-white/25'}`} />
                    {it}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-20 flex flex-col items-center text-center">
          <h3 className="font-serif text-[40px] leading-tight sm:text-[52px]">Ready when you are.</h3>
          <p className="mt-3 max-w-md text-white/60">Runs privately on your own machine. No account, no tracking — just a conversation.</p>
          <Link to="/chat" className="btn-orb mt-7 inline-flex items-center gap-2 rounded-full px-7 py-3.5 text-sm font-medium">
            Start a conversation <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* -------------------------------------------------------- FOOTER */}
      <footer className="border-t border-white/5">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-10 text-sm text-white/45 sm:px-8 md:grid-cols-3">
          <div>
            <div className="flex items-center gap-2 text-white/80">
              <Logo className="h-5 w-5" /> <span className="font-semibold tracking-[0.16em]">SENRA</span>
            </div>
            <p className="mt-3 leading-relaxed">Emotion-Aware Multimodal AI Companion — final year project, Department of AI &amp; DS, PVGCOE Nashik.</p>
          </div>
          <div>
            <p className="text-white/70">Team</p>
            <p className="mt-2 leading-relaxed">Yugandhara Patil · Yash Zoman · Aditya Yadav · Yash Tongale</p>
            <p className="mt-1">Guide: Prof. U. B. Bhadange</p>
          </div>
          <div>
            <p className="text-white/70">Important</p>
            <p className="mt-2 leading-relaxed">
              SENRA is an AI companion, not a therapist or medical service. If you are in crisis in India, call
              Tele-MANAS <a className="text-white/80 underline" href="tel:14416">14416</a> or emergency <a className="text-white/80 underline" href="tel:112">112</a>.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

function SectionHead({ kicker, title, body }: { kicker: string; title: React.ReactNode; body: string }) {
  return (
    <div className="max-w-3xl">
      <p className="font-mono text-[11.5px] uppercase tracking-[0.16em] text-white/40">{kicker}</p>
      <h2 className="mt-4 font-serif text-[40px] leading-[1.05] sm:text-[56px] section-title">{title}</h2>
      <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-white/60">{body}</p>
    </div>
  )
}

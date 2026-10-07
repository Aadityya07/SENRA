# SENRA — Emotion-Aware Multimodal AI Companion

> A companion that hears **how** you feel, not just what you say.

SENRA is a final-year project (Department of AI & DS, PVGCOE Nashik) that investigates whether an AI that perceives emotional cues — and adapts its words, tone, voice, avatar and environment to them — creates a stronger sense of *emotional presence* than a conventional chatbot.

**This repository contains Phase 1: the emotionally intelligent conversational core.** It runs fully locally: a GoEmotions RoBERTa model for emotion perception and **Gemma 3n E2B** (Google's 2B-effective-parameter Gemma) through Ollama for language generation.

> SENRA is an AI companion — not a therapist, diagnostic tool or medical service.

---

## Architecture

SENRA follows a **layered multimodal affective computing architecture** (Perception → Fusion → Decision → Generation → Actuation) with an independent safety layer. The LLM is only the reasoning/response module; understanding and decisions happen in the surrounding modules.

```
User text
  │
  ▼
Emotion Perception Layer ── Text Emotion Analysis (RoBERTa-GoEmotions + affective lexicon)
  │
  ▼
Emotion Fusion Engine ───── confidence-aware late fusion + temporal prior
  │
  ▼
Emotion Context Layer ───── Emotional State Tracker (EMA + trend) · Emotional Memory (opt-in)
  │
  ▼
Risk Detection (pre) ────── crisis / self-harm / hopelessness detection, escalation
  │
  ▼
Companion Decision Engine ─ strategy · tone · length · avatar · voice · gesture · environment
  │
  ▼
Prompt Orchestration ────── structured context → Gemma 3n E2B (Ollama)
  │
  ▼
Safety Validation (post) ── no human/therapist claims, no diagnosis, no dependency, no method info
  │
  ▼
Humanizer ───────────────── rewrites stock AI phrasing ("It sounds like…") live in the stream
  │
  ▼
Structured Response + Response Controller → Feedback & Actuation (environment today; voice/avatar next)
```

### Module map (architecture diagram → code)

| Architecture block | Code | Phase 1 status |
|---|---|---|
| Input Layer — Text | `frontend/src/components/chat/Composer.tsx` | ✅ (camera/mic shown as Phase 2) |
| Text Emotion Analysis | `backend/app/perception/text_emotion.py` | ✅ RoBERTa (GoEmotions, 28 labels) + lexicon, projected to Ekman + valence/arousal |
| Emotion Fusion Engine | `backend/app/fusion/fusion_engine.py` | ✅ confidence-weighted late fusion, JS-divergence agreement, history prior — speech/face plug into the same interface |
| Emotional State Tracker | `backend/app/context/state_tracker.py` | ✅ confidence-weighted EMA, trend (improving/stable/worsening) |
| Emotional Memory Module | `backend/app/context/emotional_memory.py` | ✅ name, role, triggers, uplifts, comfort style — user can disable/clear |
| Risk Detection & Safety Validation | `backend/app/safety/safety_layer.py` | ✅ pre-generation risk + post-generation output validation, Indian helplines |
| Companion Decision Engine | `backend/app/decision/decision_engine.py` | ✅ intent, strategy, priority, avatar/voice/gesture/background directives |
| Context-Aware Prompt Orchestration | `backend/app/orchestration/prompt_orchestrator.py` | ✅ companion persona / task persona + history + structured companion briefing |
| Reasoning Engine (LLM) | `backend/app/llm/adapter.py` | ✅ provider-agnostic adapter, Ollama + Gemma 3n E2B, streaming |
| Humanizer | `backend/app/response/humanizer.py` | ✅ removes robotic/therapy-speak phrasing and name overuse, stream-safe |
| Structured Companion Response / Response Controller | `backend/app/response/response_controller.py` | ✅ speech + tone + voice + expression + gesture + background |
| Environmental Feedback Engine | `frontend/src/components/Ambient.tsx`, `Orb.tsx` | ✅ slow (~12 s) background transitions, orb colour/motion |
| Speech / facial emotion, TTS, avatar | — | Phase 2 / Phase 3 |

The whole turn is coordinated by `backend/app/pipeline.py`.

### Emotion representation

Internally every turn produces a rich state (never shown to the user unless the research view is enabled):

```json
{ "emotion": "lonely", "intensity": 0.87, "intensity_level": "high", "confidence": 0.76,
  "valence": -0.70, "arousal": 0.27, "trend": "improving",
  "ekman": { "sadness": 0.92, "neutral": 0.05, "...": "..." } }
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19 · Vite · TypeScript · Tailwind CSS v4 · Framer Motion · react-markdown |
| Backend | Python · FastAPI · Server-Sent Events (token streaming) |
| Text emotion | Hugging Face Transformers · PyTorch · `SamLowe/roberta-base-go_emotions` |
| LLM | Gemma 3n E2B (`gemma3n:e2b`) via Ollama — local, private, GPU-accelerated (Gemma 2 2B also supported) |
| Storage | SQLite (schema mirrors the planned PostgreSQL design) |

---

## Running it

**Requirements:** Python 3.10+, Node 18+, [Ollama](https://ollama.com), ~3 GB of disk space. A GPU is recommended (tested on an RTX 4050 6 GB).

```bat
setup.bat     :: once — venv, Python deps, emotion model, gemma3n:e2b, npm install
start.bat     :: launches backend (8000) + frontend (5173) and opens the browser
```

Manual start:

```bash
# backend
cd backend
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# frontend
cd frontend
npm run dev
```

Open <http://localhost:5173>. The first reply after a cold start takes a few extra seconds while Gemma loads onto the GPU. Afterwards SENRA shows a 2-second "thinking" phase (`THINKING_MS` in `frontend/src/pages/Chat.tsx`), then streams the reply.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SENRA_LLM_MODEL` | `gemma3n:e2b` | Any Ollama model, e.g. `gemma2:2b`, `gemma3:4b`, `qwen2.5:3b` |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `SENRA_LLM_TEMPERATURE` | `0.7` | Sampling temperature (tasks use 0.4, risk turns 0.5) |
| `SENRA_ENABLE_TRANSFORMER` | `1` | `0` = lexicon-only emotion analysis |
| `SENRA_SESSION_NUDGE_AFTER` | `30` | Gentle "take a break / reach out" nudge every N messages |

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | LLM + emotion-model status |
| `POST` | `/api/chat` | SSE stream: `meta` → `analysis` → `token`… → `done` |
| `POST` | `/api/analyze` | Perception + safety only (for evaluation) |
| `GET` | `/api/users/{uid}/conversations` | Conversation history |
| `GET/PATCH/DELETE` | `/api/conversations/{id}?user_id=` | Read / rename / delete |
| `GET/PUT/DELETE` | `/api/users/{uid}/memory` | View / toggle / clear emotional memory |

Interactive docs: <http://localhost:8000/docs>.

---

## Evaluation

```bash
cd backend
.venv\Scripts\python -m scripts.eval_conversations
```

Runs scripted scenarios (greeting, loneliness → recovery, exam stress + task, anger toward the companion, pure knowledge task, good news, crisis) through the full pipeline and prints each module's output together with SENRA's reply and latency.

---

## Demo script (Phase 1 review)

1. **Landing page** → *Talk to SENRA*. Turn on **Insights** (top right) to show the research view.
2. *"I've been feeling really lonely since I moved to the hostel."* → perception (sadness + `lonely` cue), fusion, **companion presence** strategy, background drifts to soft violet.
3. *"yeah, everyone already has their groups"* → message alone is neutral, but the **state tracker** keeps the conversation in supportive mode (`continue_support`).
4. *"talking to you actually helps a bit, thanks"* → trend **improving**, **gentle uplift** strategy, encourages real-world connection (dependency prevention).
5. *"Explain supervised vs unsupervised learning"* → intent **task**, full structured Markdown answer.
6. *"You're not even listening to me!"* → **de-escalate**, calm tone, no defensiveness.
7. New conversation: a crisis statement → **independent safety layer** escalates, helpline card (Tele-MANAS 14416, 112), output validated.
8. Sidebar → **Emotional memory** → show what was remembered and that the user can turn it off or erase it.

---

## Roadmap

- **Phase 1 — Chat + emotional intelligence** ✅ *(this repository)*
- **Phase 2 — Voice & camera:** faster-whisper ASR, wav2vec2/WavLM speech emotion, MediaPipe + DeepFace facial emotion, multimodal fusion, emotion-adaptive TTS
- **Phase 3 — Embodied avatar:** VRoid/VRM avatar in Unity (UniVRM), uLipSync lip-sync, expressions, gaze, gestures, environment lighting

## Team

Yugandhara Patil · Yash Zoman · Aditya Yadav · Yash Tongale — Guide: Prof. U. B. Bhadange

## Crisis resources (India)

Tele-MANAS **14416** / 1-800-891-4416 (24x7) · Emergency **112** · AASRA +91 98204 66726 · Vandrevala Foundation +91 9999 666 555

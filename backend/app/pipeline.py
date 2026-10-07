"""SENRA Companion Pipeline — Perception → Fusion → Decision → Generation → Actuation.

One user turn flows through every layer of the architecture:

  Input Layer (text)
    → Emotion Perception Layer      (TextEmotionAnalyzer)
    → Emotion Fusion Engine         (EmotionFusionEngine, + history prior)
    → Emotion Context Layer         (EmotionalStateTracker, EmotionalMemory)
    → Risk Detection (pre)          (SafetyLayer.assess)
    → Companion Decision Engine     (CompanionDecisionEngine)
    → Prompt Orchestration          (PromptOrchestrator)
    → Reasoning Engine (LLM)        (LLMAdapter → Gemma 2 2B via Ollama)
    → Safety Validation (post)      (SafetyLayer.validate_output)
    → Structured Response + Response Controller → Feedback & Actuation

Events are streamed to the client as they become available.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import AsyncIterator

from .config import settings
from .context.emotional_memory import EmotionalMemory
from .context.state_tracker import EmotionalStateTracker, TrackedPoint
from .decision.decision_engine import CompanionDecisionEngine
from .fusion.fusion_engine import EmotionFusionEngine, FusedEmotion, ModalityReading
from .llm.adapter import LLMAdapter, LLMError
from .orchestration.prompt_orchestrator import PromptOrchestrator
from .perception.text_emotion import TextEmotionAnalyzer
from .response.humanizer import StreamRewriter, humanize
from .response.response_controller import ResponseController, clean_text, has_emoji, strip_emoji
from .safety.safety_layer import SafetyLayer
from .storage.database import Database

log = logging.getLogger("senra.pipeline")


def make_title(text: str) -> str:
    words = re.sub(r"\s+", " ", text.strip()).split(" ")
    title = " ".join(words[:7])
    return (title[:60] + ("…" if len(words) > 7 or len(title) > 60 else "")) or "New conversation"


class CompanionPipeline:
    def __init__(self, db: Database, llm: LLMAdapter) -> None:
        self.db = db
        self.llm = llm
        self.text_emotion = TextEmotionAnalyzer()
        self.fusion = EmotionFusionEngine()
        self.tracker = EmotionalStateTracker()
        self.memory = EmotionalMemory(db)
        self.safety = SafetyLayer()
        self.decision = CompanionDecisionEngine()
        self.orchestrator = PromptOrchestrator()
        self.controller = ResponseController()
        self._last_fused: dict[str, FusedEmotion] = {}

    # ------------------------------------------------------------ analysis
    async def analyse(self, user_id: str, cid: str, text: str, history_points: list[TrackedPoint],
                      recent_levels: list[str], user_turns: int, memory_enabled: bool) -> dict:
        timings: dict[str, float] = {}

        t = time.perf_counter()
        text_res = await asyncio.to_thread(self.text_emotion.analyze, text)
        timings["perception_ms"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        reading = ModalityReading("text", text_res.label, text_res.ekman, text_res.valence,
                                  text_res.arousal, text_res.intensity, text_res.confidence)
        fused = self.fusion.fuse([reading], history=self._last_fused.get(cid))
        timings["fusion_ms"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        points = history_points + [TrackedPoint(fused.valence, fused.arousal, fused.intensity,
                                                fused.confidence, fused.emotion)]
        trend = self.tracker.compute(points)
        profile = self.memory.profile(user_id) if memory_enabled else {}
        memory_summary = self.memory.summarise(profile) if memory_enabled else ""
        timings["context_ms"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        risk = self.safety.assess(text, fused.valence, fused.intensity, recent_levels)
        timings["safety_ms"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        decision = self.decision.decide(text, fused, trend, risk, user_turns,
                                        preferences=profile, nudge_after=settings.session_nudge_after)
        timings["decision_ms"] = (time.perf_counter() - t) * 1000

        return {"text_emotion": text_res, "fused": fused, "trend": trend, "risk": risk,
                "decision": decision, "profile": profile, "memory_summary": memory_summary,
                "timings": timings}

    # --------------------------------------------------------------- turn
    async def run_turn(self, user_id: str, conversation_id: str | None, message: str,
                       regenerate: bool = False) -> AsyncIterator[dict]:
        t_start = time.perf_counter()
        user = self.db.ensure_user(user_id)
        message = message.strip()

        conv = self.db.get_conversation(conversation_id) if conversation_id else None
        if conv is None or conv["user_id"] != user_id:
            conversation_id = self.db.create_conversation(user_id, make_title(message))
        cid = conversation_id
        yield {"event": "meta", "data": {"conversation_id": cid}}

        history = self.db.get_messages(cid, limit=settings.history_turns * 2 + 2)
        if regenerate:
            # Drop the last assistant answer and reuse the last user message.
            while history and history[-1]["role"] == "assistant":
                self.db.delete_message(history.pop()["message_id"])
            if history and history[-1]["role"] == "user":
                message = history[-1]["content"]
                history.pop()
        states = self.db.get_emotional_states(cid, limit=12)
        history_points = [TrackedPoint(s["valence"], s["arousal"], s["intensity"], s["confidence"], s["emotion"])
                          for s in states]
        recent_levels = [s["risk_level"] for s in states]
        user_turns = self.db.count_user_messages(cid) + (0 if regenerate else 1)

        a = await self.analyse(user_id, cid, message, history_points, recent_levels, user_turns,
                               user["memory_enabled"])
        fused, trend, risk, decision = a["fused"], a["trend"], a["risk"], a["decision"]
        self._last_fused[cid] = fused

        user_meta = {"emotion": fused.to_dict(), "risk": risk.level}
        user_mid = None
        if not regenerate:
            user_mid = self.db.add_message(cid, "user", message, user_meta)
        if user["memory_enabled"]:
            stored = self.memory.observe(user_id, message, fused.valence, fused.intensity)
        else:
            stored = []

        prompt = self.orchestrator.build(message, history, fused, trend, risk, decision,
                                         a["memory_summary"], environment_state=decision.background)

        analysis = {
            "user_message_id": user_mid,
            "perception": {"text": a["text_emotion"].to_dict()},
            "fusion": fused.to_dict(),
            "context": {"trend": trend.to_dict(), "memory": a["profile"], "memory_updates": stored},
            "safety": risk.to_dict(),
            "decision": decision.to_dict(),
            "orchestration": {"structured_context": prompt.structured_context, "briefing": prompt.briefing},
            "timings": {k: round(v, 1) for k, v in a["timings"].items()},
            "llm": {"provider": self.llm.name, "model": self.llm.model},
        }
        yield {"event": "analysis", "data": analysis}

        # ---------------------------------------------------- generation
        parts: list[str] = []
        t_llm = time.perf_counter()
        first_token_ms = None
        error = None
        allow_emoji = has_emoji(message)
        max_tokens = {"brief": 260, "moderate": 650, "detailed": 1400}[decision.length]
        if decision.intent == "task":
            temperature = 0.4
        elif risk.level in ("elevated", "crisis"):
            temperature = 0.5
        else:
            temperature = 0.75  # a little more natural variation for emotional talk
        # Conversational replies pass through the humanizer; task answers
        # (which may contain code) are streamed untouched.
        user_name = (a["profile"] or {}).get("name")
        rewriter = StreamRewriter(user_name) if decision.intent not in ("task",) else None
        try:
            async for chunk in self.llm.stream_chat(prompt.messages, temperature=temperature, max_tokens=max_tokens):
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - t_llm) * 1000
                chunk = chunk.replace("▁", " ")  # SentencePiece whitespace artefact
                if not allow_emoji:
                    chunk = strip_emoji(chunk)
                    if not chunk:
                        continue
                parts.append(chunk)
                if rewriter is not None:
                    chunk = rewriter.feed(chunk)
                    if not chunk:
                        continue
                yield {"event": "token", "data": {"t": chunk}}
            if rewriter is not None and (tail := rewriter.flush()):
                yield {"event": "token", "data": {"t": tail}}
        except LLMError as exc:
            error = str(exc)
        except (asyncio.CancelledError, GeneratorExit):
            # Client stopped generation: keep what was produced.
            partial = clean_text("".join(parts), allow_emoji)
            if partial:
                self.db.add_message(cid, "assistant", partial, {"stopped": True})
                self.db.touch_conversation(cid)
            raise

        raw = "".join(parts)
        text = clean_text(raw, allow_emoji)
        if rewriter is not None:
            text = humanize(text, user_name)
            raw = humanize(raw, user_name)
        replaced = False

        # ------------------------------------------- safety validation
        validation = self.safety.validate_output(text)
        if error and not text:
            text = self.safety.crisis_fallback() if risk.level == "crisis" else ""
            replaced = bool(text)
        elif not validation.passed:
            text = self.safety.crisis_fallback() if risk.level == "crisis" else self.safety.safe_fallback()
            replaced = True
        elif risk.level == "crisis" and not re.search(r"14416|112|helpline|crisis line", text, re.I):
            text += ("\n\nIf you feel you might act on these thoughts, please call **Tele-MANAS at 14416** "
                     "or **112** right now. You don't have to go through this alone.")
            replaced = True
        if " ".join(text.split()) != " ".join(raw.split()):
            replaced = True

        if error and not text:
            yield {"event": "error", "data": {"message": error}}
            return

        structured = self.controller.build(text, decision, risk)
        total_ms = (time.perf_counter() - t_start) * 1000
        llm_ms = (time.perf_counter() - t_llm) * 1000
        meta = {
            "structured": structured.to_dict(),
            "validation": validation.to_dict(),
            "emotion": fused.emotion,
            "strategy": decision.strategy,
            "latency": {"total_ms": round(total_ms), "llm_ms": round(llm_ms),
                        "first_token_ms": round(first_token_ms or 0)},
        }
        mid = self.db.add_message(cid, "assistant", text, meta)
        if not regenerate:
            self.db.add_emotional_state(cid, user_mid, "fused", fused.to_dict(), risk.level)
        self.db.touch_conversation(cid)

        yield {"event": "done", "data": {
            "message_id": mid, "conversation_id": cid, "text": text, "replaced": replaced,
            "structured": structured.to_dict(), "validation": validation.to_dict(),
            "latency": meta["latency"],
        }}

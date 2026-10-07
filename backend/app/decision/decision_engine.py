"""Companion Decision Engine.

Turns the fused emotional state, trend, safety assessment and conversational
intent into a *response policy*:

    strategy · response priority · length · tone
    avatar emotion · voice style · gesture · background (environment)

The LLM receives the policy as guidance; the actuation layer (voice / avatar /
environment) receives it as directives. Keeping these decisions outside the
LLM makes behaviour explainable, testable and model-independent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..context.state_tracker import EmotionalTrend
from ..fusion.fusion_engine import FusedEmotion
from ..safety.safety_layer import RiskAssessment

TASK_RX = re.compile(
    r"^\s*(what|what's|whats|how|why|when|where|which|who|can you|could you|would you|please|explain|write|"
    r"summari[sz]e|translate|define|list|give me|show me|tell me about|help me (with|write|understand|plan|study|learn|make|create|fix|solve)|"
    r"solve|calculate|compare|create|generate|make|plan|suggest|recommend|draft|fix|debug|teach|is it|are there|does|do you know)\b",
    re.IGNORECASE,
)
TASK_HINT_RX = re.compile(
    r"\b(code|python|java|javascript|sql|essay|email|resume|recipe|math|equation|algorithm|homework|assignment|"
    r"exam tips|study plan|difference between|example of|steps to|meaning of|in detail|step by step|bullet points)\b",
    re.IGNORECASE,
)
GREETING_RX = re.compile(r"^\s*(hi+|hey+|hello+|hola|yo|sup|good (morning|afternoon|evening|night)|namaste|hii+)\b[\s!.?]*\w{0,12}[\s!.?]*$", re.IGNORECASE)
META_RX = re.compile(r"\b(who|what) are you\b|\bare you (a |an )?(human|real|bot|ai|robot|person|therapist)\b|\byour name\b|\bwho (made|created|built) you\b", re.IGNORECASE)
FIRST_PERSON_FEELING_RX = re.compile(r"\b(i|i'm|im|i've|ive|me|my|myself)\b", re.IGNORECASE)
CLOSING_RX = re.compile(r"^\s*(bye|goodbye|good night|gn|see you|talk later|ttyl|thanks?,? bye)\b", re.IGNORECASE)

# Environment palette (Environmental Feedback Engine). Default is pure black.
BACKGROUNDS = {
    "neutral_black": {"from": "#000000", "to": "#050507", "accent": "#7c5cff"},
    "calm_dark_blue": {"from": "#02040d", "to": "#0a1a3a", "accent": "#4f7dff"},
    "soft_violet": {"from": "#05020b", "to": "#1d1036", "accent": "#a66bff"},
    "warm_amber": {"from": "#080402", "to": "#2a1606", "accent": "#ff9d4d"},
    "gentle_teal": {"from": "#010607", "to": "#06252a", "accent": "#3fd0c9"},
    "muted_indigo": {"from": "#030308", "to": "#141432", "accent": "#7b83ff"},
    "dim_slate": {"from": "#030405", "to": "#10161c", "accent": "#8fa3b8"},
}


@dataclass
class CompanionDecision:
    intent: str
    strategy: str
    priority: str
    length: str
    tone: str
    avatar_emotion: str
    voice_style: str
    voice: dict
    gesture: str
    background: str
    palette: dict
    guidance: list[str] = field(default_factory=list)
    wellbeing_nudge: bool = False

    def to_dict(self) -> dict:
        return {
            "intent": self.intent, "strategy": self.strategy, "priority": self.priority,
            "length": self.length, "tone": self.tone, "avatar_emotion": self.avatar_emotion,
            "voice_style": self.voice_style, "voice": self.voice, "gesture": self.gesture,
            "background": self.background, "palette": self.palette,
            "guidance": self.guidance, "wellbeing_nudge": self.wellbeing_nudge,
        }


VOICE_PRESETS = {
    "soft_slow": {"rate": 0.85, "pitch": -0.05, "pause_ms": 450, "energy": 0.4},
    "calm_steady": {"rate": 0.92, "pitch": -0.02, "pause_ms": 320, "energy": 0.5},
    "warm": {"rate": 1.0, "pitch": 0.0, "pause_ms": 250, "energy": 0.6},
    "bright": {"rate": 1.06, "pitch": 0.04, "pause_ms": 200, "energy": 0.75},
    "clear": {"rate": 1.0, "pitch": 0.0, "pause_ms": 220, "energy": 0.6},
}


def detect_intent(text: str, fused: FusedEmotion) -> str:
    t = text.strip()
    if CLOSING_RX.search(t):
        return "closing"
    if GREETING_RX.match(t):
        return "greeting"
    if META_RX.search(t):
        return "about_senra"
    emotional = fused.emotion != "neutral" and fused.intensity >= 0.35 and abs(fused.valence) >= 0.25
    is_task = bool(TASK_RX.search(t)) or bool(TASK_HINT_RX.search(t))
    if is_task and not (emotional and fused.valence < -0.3 and FIRST_PERSON_FEELING_RX.search(t) and not TASK_HINT_RX.search(t)):
        return "task_with_feeling" if emotional and fused.valence < -0.3 else "task"
    if emotional:
        return "emotional_share"
    return "conversation"


class CompanionDecisionEngine:
    def decide(self, text: str, fused: FusedEmotion, trend: EmotionalTrend,
               risk: RiskAssessment, user_turns: int, preferences: dict | None = None,
               nudge_after: int = 30) -> CompanionDecision:
        prefs = preferences or {}
        intent = detect_intent(text, fused)
        e, v, i = fused.emotion, fused.valence, fused.intensity
        guidance: list[str] = []
        prev_smoothed = trend.history[-2]["smoothed"] if len(trend.history) >= 2 else None

        # ---- 1. Safety overrides everything --------------------------------
        if risk.level == "crisis":
            return CompanionDecision(
                intent=intent, strategy="crisis_support", priority="safety", length="moderate",
                tone="calm, steady, serious and caring", avatar_emotion="concerned",
                voice_style="soft_slow", voice=VOICE_PRESETS["soft_slow"], gesture="hand_to_chest",
                background="dim_slate", palette=BACKGROUNDS["dim_slate"],
                guidance=[
                    "The user may be in danger. Respond with calm, serious care. No jokes, no emojis, no lists of tips.",
                    "Acknowledge what they shared and thank them for telling you.",
                    "Clearly and gently encourage them to contact a crisis line (Tele-MANAS 14416, or 112 in an emergency) or a trusted person right now.",
                    "Ask directly and kindly whether they are safe right now.",
                    "State that you are an AI and cannot replace real human help, but that you are still here to talk.",
                    "Use simple, human words. Do not mention programming, algorithms or being a machine beyond saying you are an AI.",
                    "Never tell them they are safe with you or that you can protect them.",
                ],
            )

        # ---- 2. Choose strategy by intent + affect --------------------------
        if intent == "task":
            strategy, priority, tone = "inform", "informational", "clear, friendly and precise"
            length = "detailed" if len(text) > 60 or re.search(r"\b(explain|in detail|step by step|essay|code|write)\b", text, re.I) else "moderate"
            avatar, voice, gesture, bg = "attentive", "clear", "open_palm", "neutral_black"
            guidance.append("Start directly with the answer. No greeting, no filler, no rhetorical intro.")
        elif intent == "task_with_feeling":
            strategy, priority, tone = "supportive_help", "emotional", "warm, reassuring and practical"
            length = "detailed"
            avatar, voice, gesture, bg = "soft_concern", "calm_steady", "gentle_nod", "calm_dark_blue"
            guidance.append("Briefly acknowledge the feeling in one sentence, then help with the actual request clearly.")
        elif intent == "greeting":
            strategy, priority, tone = "welcome", "conversational", "warm, light and inviting"
            length, avatar, voice, gesture, bg = "brief", "soft_smile", "warm", "small_wave", "neutral_black"
        elif intent == "closing":
            strategy, priority, tone = "farewell", "conversational", "warm and kind"
            length, avatar, voice, gesture, bg = "brief", "soft_smile", "warm", "small_wave", "neutral_black"
        elif intent == "about_senra":
            strategy, priority, tone = "self_disclosure", "conversational", "honest, warm and simple"
            length, avatar, voice, gesture, bg = "brief", "soft_smile", "warm", "head_tilt", "neutral_black"
            guidance.append("Be transparent: you are SENRA, an AI companion (not a human, not a therapist).")
        elif v <= -0.2:
            # Negative affect -> choose the comforting mode that fits the emotion.
            if e in {"angry", "frustrated", "upset"}:
                strategy, tone = "de_escalate", "calm, non-defensive and validating"
                avatar, voice, gesture, bg = "concerned", "calm_steady", "none", "dim_slate"
                guidance.append("Do not argue or over-apologise. Validate the frustration and ask what would help.")
            elif e in {"anxious", "overwhelmed", "stressed", "uneasy"}:
                strategy, tone = "ground_and_reassure", "slow, steady and reassuring"
                avatar, voice, gesture, bg = "soft_concern", "soft_slow", "gentle_nod", "calm_dark_blue"
                guidance.append("Help them feel steadier. You may offer one small grounding idea (like a slow breath) only if it fits naturally.")
            elif e in {"lonely"}:
                strategy, tone = "companion_presence", "gentle, present and warm"
                avatar, voice, gesture, bg = "soft_concern", "soft_slow", "head_tilt", "soft_violet"
                guidance.append("Make them feel accompanied and heard. Show genuine interest in them.")
            elif e in {"exhausted"}:
                strategy, tone = "comfort", "soft, unhurried and kind"
                avatar, voice, gesture, bg = "soft_concern", "soft_slow", "gentle_nod", "calm_dark_blue"
                guidance.append("Acknowledge how tiring things are. Do not push productivity advice.")
            elif e in {"grieving"}:
                strategy, tone = "comfort", "tender, patient and respectful"
                avatar, voice, gesture, bg = "concerned", "soft_slow", "hand_to_chest", "muted_indigo"
                guidance.append("Honour the loss. Do not try to fix or minimise it.")
            else:
                strategy, tone = "comfort", "gentle, validating and warm"
                avatar, voice, gesture, bg = "soft_concern", "soft_slow", "gentle_nod", "calm_dark_blue"
            priority = "emotional"
            heavy = e in {"distressed", "grieving", "overwhelmed", "lonely", "exhausted"}
            length = "detailed" if (i >= 0.6 or len(text) > 100 or heavy or trend.trend == "worsening") else "moderate"
            guidance.append("Validate first. Reflect what they said in your own words before anything else.")
            if prefs.get("comfort_style") == "listen":
                guidance.append("They prefer to be listened to: avoid giving advice unless asked.")
            elif prefs.get("comfort_style") == "advice":
                guidance.append("They appreciate practical suggestions: after validating, offer one or two gentle, concrete ideas.")
            else:
                guidance.append("Do not jump to advice. End with one gentle, open question.")
        elif v >= 0.3 and prev_smoothed is not None and prev_smoothed < -0.15:
            # Mood lifting after a hard moment: gently glad, not over-excited.
            strategy, priority, tone = "gentle_uplift", "emotional", "warm, gently glad and grounded"
            length = "moderate"
            avatar, voice, gesture, bg = "soft_smile", "warm", "gentle_nod", "gentle_teal"
            guidance.append("Their mood is lifting after a difficult moment. Be gently glad, not over-excited, and keep the focus on them.")
            guidance.append("If they thank you, receive it warmly and humbly, and gently remind them that the people around them can be a source of support too.")
        elif v >= 0.3:
            strategy, priority, tone = "celebrate", "emotional", "warm, genuinely happy and engaged"
            length = "moderate"
            avatar, voice, gesture, bg = "happy", "bright", "open_palm", "warm_amber"
            guidance.append("Share in their good feeling sincerely, mention the specific thing they are happy about, and show curiosity about it.")
        elif trend.turns >= 2 and trend.smoothed_valence <= -0.25:
            # Neutral-sounding message, but the conversation is still emotionally heavy.
            strategy, priority, tone = "continue_support", "emotional", "gentle, attentive and warm"
            length = "moderate" if len(text) < 100 else "detailed"
            avatar, voice, gesture, bg = "soft_concern", "calm_steady", "head_tilt", "calm_dark_blue"
            guidance.append("They are still talking about something difficult from earlier. Stay with it and respond to the new detail they just shared.")
            guidance.append("Do not jump to solutions or brainstorming yet. End with one gentle, open question.")
        else:
            strategy, priority, tone = "converse", "conversational", "natural, friendly and curious"
            length = "brief" if len(text) < 40 else "moderate"
            avatar, voice, gesture, bg = "attentive", "warm", "head_tilt", "neutral_black"

        # ---- 3. Trend-aware adjustments ------------------------------------
        if trend.trend == "improving" and v > -0.6 and priority == "emotional" and strategy != "celebrate":
            guidance.append("Their mood seems to be lifting a little compared to earlier; gently acknowledge it if it feels natural.")
            bg = "gentle_teal" if v > -0.2 else bg
        elif trend.trend == "worsening" and priority == "emotional":
            guidance.append("Their mood has been getting heavier during this conversation; be extra gentle and patient.")
        if risk.level == "elevated":
            priority = "safety"
            tone = "gentle, serious and caring"
            avatar, voice, bg = "concerned", "soft_slow", "dim_slate"
            guidance.append("There are signs of hopelessness. Check in kindly about how they are coping, and mention softly that talking to someone they trust or a helpline like Tele-MANAS (14416) can help.")

        # ---- 4. Responsible AI: gentle session nudge -----------------------
        nudge = user_turns > 0 and user_turns % nudge_after == 0
        if nudge:
            guidance.append("Near the end of your reply, gently encourage them to take a short break or connect with someone in their life. Keep it kind, not pushy.")

        return CompanionDecision(
            intent=intent, strategy=strategy, priority=priority, length=length, tone=tone,
            avatar_emotion=avatar, voice_style=voice, voice=VOICE_PRESETS[voice], gesture=gesture,
            background=bg, palette=BACKGROUNDS[bg], guidance=guidance, wellbeing_nudge=nudge,
        )

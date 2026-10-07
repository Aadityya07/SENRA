"""Structured Companion Response + Response Controller.

Formats the LLM output for delivery and translates it into actuation
directives for the Feedback & Actuation Layer:

    speech text · tone · voice style/parameters · avatar expression · gesture ·
    background / environment

Phase 1 renders text + environment (ambient background and companion orb);
Phase 2/3 consume the same directives for TTS, the avatar and lighting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..decision.decision_engine import CompanionDecision
from ..safety.safety_layer import RiskAssessment

_LEAK_RX = re.compile(r"\[/?\s*companion briefing[^\]]*\]", re.I)
_PREFIX_RX = re.compile(r"^\s*(senra|sena|assistant|model|companion)\s*:\s*", re.I)


_EMOJI_RX = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF️‍]+"
)
_BRACKET_NOTE_RX = re.compile(r"^\s*[*_]*\[(?:[^\]]{0,200})\][*_]*\s*$", re.M)


def has_emoji(text: str) -> bool:
    return bool(_EMOJI_RX.search(text or ""))


def strip_emoji(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", _EMOJI_RX.sub("", text))


def clean_text(text: str, allow_emoji: bool = True) -> str:
    text = _LEAK_RX.sub("", text)
    text = _PREFIX_RX.sub("", text)
    text = re.sub(r"<end_of_turn>|<start_of_turn>(model|user)?", "", text)
    text = _BRACKET_NOTE_RX.sub("", text)          # e.g. "_[Consider adding ...]_"
    if not allow_emoji:
        text = strip_emoji(text)
    text = text.strip()
    # Small models sometimes wrap the whole reply in quotes.
    if len(text) > 2 and text[0] in "\"“":
        close = max(text.rfind('"', 1), text.rfind("”", 1))
        if close > len(text) * 0.6 and text.count('"') + text.count("“") + text.count("”") == 2:
            text = text[1:close] + text[close + 1:]
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class StructuredResponse:
    speech: str
    tone: str
    emotion: str
    voice_style: str
    voice: dict
    facial_expression: str
    gesture: str
    background: str
    palette: dict
    safety: dict
    show_helplines: bool

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ResponseController:
    def build(self, text: str, decision: CompanionDecision, risk: RiskAssessment) -> StructuredResponse:
        return StructuredResponse(
            speech=text,
            tone=decision.tone,
            emotion=decision.avatar_emotion,
            voice_style=decision.voice_style,
            voice=decision.voice,
            facial_expression=decision.avatar_emotion,
            gesture=decision.gesture,
            background=decision.background,
            palette=decision.palette,
            safety={"level": risk.level, "escalated": risk.escalate},
            show_helplines=risk.level in ("crisis", "elevated"),
        )

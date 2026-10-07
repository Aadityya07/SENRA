"""Text Emotion Analysis — Emotion Perception Layer (text modality).

Hybrid affect recogniser:
  1. A RoBERTa classifier fine-tuned on Google's GoEmotions dataset
     (28 fine-grained labels, multi-label sigmoid outputs).
  2. An affective cue lexicon for states GoEmotions does not model well
     (loneliness, exhaustion, overwhelm, stress, hopelessness).

The fine-grained output is projected into
  * the Ekman space (joy, sadness, anger, fear, surprise, disgust, neutral),
    using the official GoEmotions -> Ekman mapping, so that text, speech
    (RAVDESS/CREMA-D) and face (FER-2013) can later be fused in one space;
  * the valence/arousal circumplex (Russell, 1980).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field

from ..config import settings

log = logging.getLogger("senra.perception.text")

EKMAN = ("joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral")

# GoEmotions -> Ekman mapping (Demszky et al., 2020, GoEmotions paper, Table 7).
GO_TO_EKMAN: dict[str, str] = {
    "anger": "anger", "annoyance": "anger", "disapproval": "anger",
    "disgust": "disgust",
    "fear": "fear", "nervousness": "fear",
    "joy": "joy", "amusement": "joy", "approval": "joy", "excitement": "joy",
    "gratitude": "joy", "love": "joy", "optimism": "joy", "relief": "joy",
    "pride": "joy", "admiration": "joy", "desire": "joy", "caring": "joy",
    "sadness": "sadness", "disappointment": "sadness", "embarrassment": "sadness",
    "grief": "sadness", "remorse": "sadness",
    "surprise": "surprise", "realization": "surprise", "confusion": "surprise",
    "curiosity": "surprise",
    "neutral": "neutral",
}

# Approximate valence [-1, 1] / arousal [0, 1] anchors per label
# (derived from the NRC-VAD lexicon, rescaled).
GO_VA: dict[str, tuple[float, float]] = {
    "admiration": (0.60, 0.45), "amusement": (0.70, 0.60), "anger": (-0.70, 0.85),
    "annoyance": (-0.50, 0.60), "approval": (0.50, 0.35), "caring": (0.60, 0.35),
    "confusion": (-0.20, 0.50), "curiosity": (0.30, 0.60), "desire": (0.40, 0.65),
    "disappointment": (-0.60, 0.35), "disapproval": (-0.50, 0.50), "disgust": (-0.70, 0.60),
    "embarrassment": (-0.50, 0.55), "excitement": (0.75, 0.90), "fear": (-0.75, 0.85),
    "gratitude": (0.75, 0.40), "grief": (-0.85, 0.45), "joy": (0.85, 0.65),
    "love": (0.85, 0.55), "nervousness": (-0.55, 0.75), "optimism": (0.65, 0.50),
    "pride": (0.70, 0.60), "realization": (0.10, 0.45), "relief": (0.60, 0.25),
    "remorse": (-0.60, 0.40), "sadness": (-0.75, 0.25), "surprise": (0.10, 0.80),
    "neutral": (0.00, 0.30),
}

# Companion-facing label for the dominant fine-grained GoEmotions label.
GO_TO_STATE: dict[str, str] = {
    "admiration": "warm", "amusement": "playful", "anger": "angry", "annoyance": "frustrated",
    "approval": "content", "caring": "affectionate", "confusion": "confused",
    "curiosity": "curious", "desire": "hopeful", "disappointment": "disappointed",
    "disapproval": "frustrated", "disgust": "upset", "embarrassment": "embarrassed",
    "excitement": "excited", "fear": "anxious", "gratitude": "grateful", "grief": "grieving",
    "joy": "happy", "love": "affectionate", "nervousness": "anxious", "optimism": "hopeful",
    "pride": "proud", "realization": "reflective", "relief": "relieved", "remorse": "guilty",
    "sadness": "sad", "surprise": "surprised", "neutral": "neutral",
}


@dataclass(frozen=True)
class Cue:
    pattern: re.Pattern
    state: str
    ekman: str
    valence: float
    arousal: float
    weight: float


def _cue(regex: str, state: str, ekman: str, v: float, a: float, w: float) -> Cue:
    return Cue(re.compile(regex, re.IGNORECASE), state, ekman, v, a, w)


# Affective cue lexicon: states that matter for companionship but are weakly
# represented in GoEmotions.
CUES: tuple[Cue, ...] = (
    _cue(r"\b(lonely|loneliness|so alone|all alone|feel(?:ing)? alone|no ?one (?:cares|understands|to talk)|nobody (?:cares|understands)|isolated|left out)\b",
         "lonely", "sadness", -0.70, 0.25, 0.75),
    _cue(r"\b(exhausted|drained|burn(?:ed|t)[ -]?out|so tired|tired of everything|worn out|no energy|can'?t sleep|sleepless)\b",
         "exhausted", "sadness", -0.55, 0.15, 0.65),
    _cue(r"\b(overwhelm(?:ed|ing)?|too much (?:for me|to handle)|can'?t cope|falling apart|breaking down|drowning)\b",
         "overwhelmed", "fear", -0.70, 0.75, 0.75),
    _cue(r"\b(stress(?:ed|ful)?|pressure|deadline|under so much|tense)\b",
         "stressed", "fear", -0.50, 0.70, 0.55),
    _cue(r"\b(anxious|anxiety|worried|worrying|panic(?:king)?|nervous|scared|afraid|terrified|uneasy)\b",
         "anxious", "fear", -0.60, 0.80, 0.65),
    _cue(r"\b(hopeless|worthless|empty inside|feel(?:ing)? empty|numb|pointless|meaningless|no purpose|give up)\b",
         "distressed", "sadness", -0.85, 0.35, 0.85),
    _cue(r"\b(compar(?:e|es|ing) me|never (?:good )?enough|not good enough|disappointed in me|let (?:them|everyone|my parents) down|nothing i do)\b",
         "hurt", "sadness", -0.65, 0.45, 0.75),
    _cue(r"\b(heartbroken|broke up|break ?up|miss (?:him|her|them)|lost my|passed away|died)\b",
         "grieving", "sadness", -0.80, 0.40, 0.75),
    _cue(r"\b(frustrat(?:ed|ing)|fed up|sick of|annoyed|irritated|pissed)\b",
         "frustrated", "anger", -0.55, 0.65, 0.6),
    _cue(r"\b(furious|so angry|hate (?:this|it|you|everything)|rage|livid)\b",
         "angry", "anger", -0.75, 0.90, 0.7),
    _cue(r"\b(sad|down|depress(?:ed|ing)|low|upset|crying|cried|tears|miserable|unhappy|hurt)\b",
         "sad", "sadness", -0.65, 0.30, 0.55),
    _cue(r"\b(happy|glad|great day|amazing|awesome|wonderful|excited|thrilled|can'?t wait)\b",
         "happy", "joy", 0.75, 0.65, 0.5),
    _cue(r"\b(got (?:selected|the job|in|accepted|promoted|placed)|passed (?:my|the)|cleared (?:my|the)|i won|nailed it|finally did it)\b",
         "excited", "joy", 0.85, 0.80, 0.7),
    _cue(r"\b(thank(?:s| you)|grateful|appreciate)\b", "grateful", "joy", 0.70, 0.40, 0.45),
    _cue(r"\b(calm|peaceful|relaxed|better now|feel(?:ing)? better|relieved)\b",
         "calm", "joy", 0.55, 0.20, 0.5),
)

NEGATION = re.compile(r"\b(not|never|no|isn'?t|aren'?t|don'?t|doesn'?t|didn'?t|wasn'?t|ain'?t|hardly)\b(?:\W+\w+){0,2}\W*$", re.IGNORECASE)
INTENSIFIERS = re.compile(r"\b(so|very|really|extremely|totally|completely|incredibly|super|too|absolutely|literally|deeply)\b", re.IGNORECASE)


@dataclass
class TextEmotionResult:
    modality: str
    label: str                      # companion-facing state, e.g. "lonely"
    ekman: dict[str, float]         # distribution over EKMAN (sums to 1)
    valence: float                  # -1 .. 1
    arousal: float                  # 0 .. 1
    intensity: float                # 0 .. 1
    confidence: float               # 0 .. 1
    top_labels: list[tuple[str, float]] = field(default_factory=list)
    cues: list[str] = field(default_factory=list)
    source: str = "hybrid"
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "modality": self.modality,
            "label": self.label,
            "ekman": {k: round(v, 4) for k, v in self.ekman.items()},
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "intensity": round(self.intensity, 3),
            "confidence": round(self.confidence, 3),
            "top_labels": [[k, round(v, 4)] for k, v in self.top_labels],
            "cues": self.cues,
            "source": self.source,
            "latency_ms": round(self.latency_ms, 1),
        }


class TextEmotionAnalyzer:
    """Loads the GoEmotions classifier lazily and analyses user text."""

    def __init__(self, model_name: str = settings.text_emotion_model,
                 enable_transformer: bool = settings.enable_transformer) -> None:
        self.model_name = model_name
        self.enable_transformer = enable_transformer
        self._pipe = None
        self._lock = threading.Lock()
        self.status = "not_loaded"

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        if not self.enable_transformer or self._pipe is not None:
            return
        with self._lock:
            if self._pipe is not None:
                return
            try:
                self.status = "loading"
                from transformers import pipeline  # heavy import, keep lazy

                self._pipe = pipeline(
                    "text-classification", model=self.model_name, top_k=None,
                    truncation=True, max_length=256, device=-1,
                )
                self._pipe("warm up")
                self.status = "ready"
                log.info("Text emotion model loaded: %s", self.model_name)
            except Exception as exc:  # pragma: no cover - environment specific
                self.status = f"lexicon_only ({exc.__class__.__name__})"
                log.warning("Falling back to lexicon-only text emotion: %s", exc)

    @property
    def ready(self) -> bool:
        return self._pipe is not None

    # --------------------------------------------------------------- analyse
    def analyze(self, text: str) -> TextEmotionResult:
        t0 = time.perf_counter()
        text = (text or "").strip()
        go_scores = self._classify(text)
        cues = self._match_cues(text)

        # --- project fine-grained scores into Ekman + VA ---------------------
        ekman = {e: 0.0 for e in EKMAN}
        v_num = a_num = mass = 0.0
        for label, p in go_scores.items():
            ekman[GO_TO_EKMAN[label]] += p
            va = GO_VA[label]
            v_num += p * va[0]
            a_num += p * va[1]
            mass += p

        # Lexicon cues contribute additional evidence.
        for cue in cues:
            ekman[cue.ekman] += cue.weight
            v_num += cue.weight * cue.valence
            a_num += cue.weight * cue.arousal
            mass += cue.weight

        if mass <= 0:
            ekman["neutral"] = 1.0
            mass, v_num, a_num = 1.0, 0.0, 0.3

        total = sum(ekman.values()) or 1.0
        ekman = {k: v / total for k, v in ekman.items()}
        valence = max(-1.0, min(1.0, v_num / mass))
        arousal = max(0.0, min(1.0, a_num / mass))

        # --- companion-facing label -----------------------------------------
        ranked = sorted(go_scores.items(), key=lambda kv: kv[1], reverse=True)
        non_neutral = [(k, v) for k, v in ranked if k != "neutral"]
        label = "neutral"
        strongest_cue = max(cues, key=lambda c: c.weight, default=None)
        if strongest_cue and (not non_neutral or strongest_cue.weight >= non_neutral[0][1] * 0.9):
            label = strongest_cue.state
        elif non_neutral and non_neutral[0][1] >= 0.18:
            label = GO_TO_STATE[non_neutral[0][0]]

        # --- intensity -------------------------------------------------------
        peak = max((v for k, v in ekman.items() if k != "neutral"), default=0.0)
        boosts = len(INTENSIFIERS.findall(text)) * 0.06
        boosts += min(text.count("!"), 3) * 0.05
        caps = sum(1 for w in re.findall(r"\b[A-Z]{3,}\b", text))
        boosts += min(caps, 3) * 0.05
        intensity = 0.45 * peak + 0.35 * abs(valence) + 0.2 * arousal * (1 - ekman["neutral"]) + boosts
        if label == "neutral":
            intensity *= 0.6
        intensity = max(0.0, min(1.0, intensity))

        # --- confidence ------------------------------------------------------
        if self.ready and ranked:
            top = ranked[0][1]
            second = ranked[1][1] if len(ranked) > 1 else 0.0
            margin = top - second
            confidence = 0.5 * top + 0.5 * min(1.0, margin * 1.5)
            if cues and GO_TO_EKMAN.get(ranked[0][0]) == cues[0].ekman:
                confidence += 0.15  # transformer and lexicon agree
            src = "roberta-goemotions+lexicon" if cues else "roberta-goemotions"
        else:
            confidence = 0.35 + 0.1 * len(cues) if cues else 0.3
            src = "lexicon"
        if len(text.split()) <= 2:
            confidence *= 0.8  # very short messages carry little affect
        confidence = max(0.05, min(0.99, confidence))

        return TextEmotionResult(
            modality="text", label=label, ekman=ekman, valence=valence,
            arousal=arousal, intensity=intensity, confidence=confidence,
            top_labels=ranked[:5], cues=sorted({c.state for c in cues}), source=src,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    # -------------------------------------------------------------- helpers
    def _classify(self, text: str) -> dict[str, float]:
        if not text:
            return {"neutral": 1.0}
        if self._pipe is None and self.enable_transformer and self.status == "not_loaded":
            self.load()
        if self._pipe is None:
            return {}
        out = self._pipe(text[:1000])
        rows = out[0] if out and isinstance(out[0], list) else out
        # Keep labels with meaningful probability mass to reduce noise.
        return {r["label"]: float(r["score"]) for r in rows if r["score"] >= 0.04}

    @staticmethod
    def _match_cues(text: str) -> list[Cue]:
        found: list[Cue] = []
        for cue in CUES:
            for m in cue.pattern.finditer(text):
                prefix = text[max(0, m.start() - 30):m.start()]
                if NEGATION.search(prefix):
                    continue
                found.append(cue)
                break
        return found

"""Emotion Fusion Engine — confidence-aware multimodal late fusion.

Combines per-modality emotion readings (text in Phase 1; speech and face are
added in Phase 2 through the same interface) with the user's historical
emotional state, producing:

    current emotion · intensity · confidence · valence · arousal

Fusion rule (late fusion over a shared Ekman space):

    w_m      = r_m * c_m                      (modality reliability x confidence)
    w_hist   = lambda * c_hist                (temporal prior)
    P_fused  = normalise( sum_m w_m * P_m  +  w_hist * P_hist )
    V_fused  = sum_m w_m * V_m + w_hist * V_hist  / sum(w)

Confidence is the weighted mean confidence scaled by inter-modality agreement
(1 - mean Jensen-Shannon divergence), so conflicting modalities reduce
confidence instead of producing over-confident states.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..perception.text_emotion import EKMAN

# Relative trust in each modality (tunable / learnable in Phase 2).
MODALITY_RELIABILITY = {"text": 1.0, "speech": 0.85, "face": 0.75}
HISTORY_WEIGHT = 0.25


@dataclass
class ModalityReading:
    modality: str
    label: str
    ekman: dict[str, float]
    valence: float
    arousal: float
    intensity: float
    confidence: float


@dataclass
class FusedEmotion:
    emotion: str                    # companion-facing label
    ekman: dict[str, float]
    dominant: str                   # dominant Ekman class
    valence: float
    arousal: float
    intensity: float
    confidence: float
    agreement: float
    modalities: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)

    @property
    def intensity_level(self) -> str:
        if self.intensity >= 0.66:
            return "high"
        if self.intensity >= 0.38:
            return "medium"
        return "low"

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "dominant": self.dominant,
            "ekman": {k: round(v, 4) for k, v in self.ekman.items()},
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "intensity": round(self.intensity, 3),
            "intensity_level": self.intensity_level,
            "confidence": round(self.confidence, 3),
            "agreement": round(self.agreement, 3),
            "modalities": self.modalities,
            "weights": {k: round(v, 3) for k, v in self.weights.items()},
        }


def _js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    def kl(a, b):
        return sum(a[k] * math.log((a[k] + 1e-9) / (b[k] + 1e-9)) for k in EKMAN if a[k] > 0)
    m = {k: 0.5 * (p[k] + q[k]) for k in EKMAN}
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)  # in nats, bounded by ln 2


class EmotionFusionEngine:
    def fuse(self, readings: list[ModalityReading],
             history: FusedEmotion | None = None) -> FusedEmotion:
        if not readings:
            raise ValueError("at least one modality reading is required")

        weights: dict[str, float] = {}
        dist = {k: 0.0 for k in EKMAN}
        v = a = inten = 0.0

        for r in readings:
            w = MODALITY_RELIABILITY.get(r.modality, 0.5) * max(r.confidence, 0.05)
            weights[r.modality] = w
            for k in EKMAN:
                dist[k] += w * r.ekman.get(k, 0.0)
            v += w * r.valence
            a += w * r.arousal
            inten += w * r.intensity

        if history is not None:
            wh = HISTORY_WEIGHT * history.confidence
            weights["history"] = wh
            for k in EKMAN:
                dist[k] += wh * history.ekman.get(k, 0.0)
            v += wh * history.valence
            a += wh * history.arousal
            # history does not inflate the intensity of the current moment
            inten += wh * min(history.intensity, max(r.intensity for r in readings))

        wsum = sum(weights.values()) or 1.0
        total = sum(dist.values()) or 1.0
        dist = {k: val / total for k, val in dist.items()}

        # Agreement between modalities (1 when only one modality is present).
        if len(readings) > 1:
            pairs = [(x, y) for i, x in enumerate(readings) for y in readings[i + 1:]]
            jsd = sum(_js_divergence(x.ekman, y.ekman) for x, y in pairs) / len(pairs)
            agreement = 1.0 - min(1.0, jsd / math.log(2))
        else:
            agreement = 1.0

        conf = sum(MODALITY_RELIABILITY.get(r.modality, 0.5) * r.confidence for r in readings)
        conf /= sum(MODALITY_RELIABILITY.get(r.modality, 0.5) for r in readings)
        conf *= 0.6 + 0.4 * agreement
        if history is not None and history.dominant == max(dist, key=dist.get):
            conf = min(0.99, conf + 0.05)  # temporally consistent

        dominant = max(dist, key=dist.get)
        # The most confident modality names the fine-grained state.
        lead = max(readings, key=lambda r: weights[r.modality])
        emotion = lead.label
        if emotion == "neutral" and dominant != "neutral" and dist[dominant] > 0.45:
            emotion = {"joy": "content", "sadness": "low", "anger": "frustrated",
                       "fear": "uneasy", "surprise": "surprised", "disgust": "upset"}[dominant]
        # Escalate to "distressed" for strongly negative, high-intensity states.
        intensity = inten / wsum
        valence = v / wsum
        if valence <= -0.55 and intensity >= 0.7 and emotion in {"sad", "anxious", "overwhelmed", "low", "uneasy", "stressed"}:
            emotion = "distressed"

        return FusedEmotion(
            emotion=emotion, ekman=dist, dominant=dominant, valence=valence,
            arousal=a / wsum, intensity=max(0.0, min(1.0, intensity)),
            confidence=max(0.05, min(0.99, conf)), agreement=agreement,
            modalities=[r.modality for r in readings], weights=weights,
        )

"""Emotional State Tracker — temporal smoothing and trend estimation.

Single predictions are noisy, so the companion reacts to a smoothed state:

    alpha_t   = 0.3 + 0.4 * confidence_t            (confidence-weighted EMA)
    V_ema_t   = alpha_t * V_t + (1 - alpha_t) * V_ema_{t-1}

Trend compares the current smoothed valence with the smoothed valence a few
turns earlier and also looks at the least-squares slope over the window:

    improving  : delta >  +0.12
    worsening  : delta <  -0.12
    stable     : otherwise
"""
from __future__ import annotations

from dataclasses import dataclass, field

TREND_THRESHOLD = 0.12
WINDOW = 6


@dataclass
class TrackedPoint:
    valence: float
    arousal: float
    intensity: float
    confidence: float
    emotion: str


@dataclass
class EmotionalTrend:
    trend: str                       # improving | stable | worsening | new
    smoothed_valence: float
    smoothed_arousal: float
    delta: float
    slope: float
    turns: int
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trend": self.trend,
            "smoothed_valence": round(self.smoothed_valence, 3),
            "smoothed_arousal": round(self.smoothed_arousal, 3),
            "delta": round(self.delta, 3),
            "slope": round(self.slope, 4),
            "turns": self.turns,
            "history": self.history,
        }


class EmotionalStateTracker:
    """Stateless helper: trend is recomputed from stored per-turn states."""

    @staticmethod
    def compute(points: list[TrackedPoint]) -> EmotionalTrend:
        if not points:
            return EmotionalTrend("new", 0.0, 0.3, 0.0, 0.0, 0)

        ema_v: list[float] = []
        ema_a = points[0].arousal
        for i, p in enumerate(points):
            alpha = 0.3 + 0.4 * p.confidence
            if i == 0:
                ema_v.append(p.valence)
                ema_a = p.arousal
            else:
                ema_v.append(alpha * p.valence + (1 - alpha) * ema_v[-1])
                ema_a = alpha * p.arousal + (1 - alpha) * ema_a

        window = ema_v[-WINDOW:]
        n = len(window)
        if n >= 2:
            xs = list(range(n))
            mx, my = sum(xs) / n, sum(window) / n
            den = sum((x - mx) ** 2 for x in xs) or 1.0
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, window)) / den
            delta = window[-1] - window[0]
        else:
            slope = delta = 0.0

        if len(points) < 2:
            trend = "new"
        elif delta > TREND_THRESHOLD or slope > TREND_THRESHOLD / 2:
            trend = "improving"
        elif delta < -TREND_THRESHOLD or slope < -TREND_THRESHOLD / 2:
            trend = "worsening"
        else:
            trend = "stable"

        recent = [
            {"emotion": p.emotion, "valence": round(p.valence, 3),
             "smoothed": round(ev, 3), "intensity": round(p.intensity, 3)}
            for p, ev in zip(points[-WINDOW:], ema_v[-WINDOW:])
        ]
        return EmotionalTrend(trend, ema_v[-1], ema_a, delta, slope, len(points), recent)

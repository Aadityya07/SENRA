"""Risk Detection & Safety Validation — independent of the LLM.

Safety must never depend on the language model noticing a crisis, so this
layer runs deterministic checks *before* generation (input risk assessment,
crisis detection, escalation) and *after* generation (responsible-AI output
validation).

Risk levels
    none      – ordinary conversation
    low       – negative affect, no risk language
    elevated  – passive hopelessness / distress that warrants gentle check-in
    crisis    – self-harm, suicidal intent, harm to others or immediate danger
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

LEVELS = ("none", "low", "elevated", "crisis")


def _rx(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts), re.IGNORECASE)


CRISIS_PATTERNS: dict[str, re.Pattern] = {
    "suicidal_intent": _rx(
        r"\b(kill|killing|end|ending|take|taking)\s+(myself|my\s+(own\s+)?life)\b",
        r"\bsuicid(e|al)\b",
        r"\b(want|wanna|going|plan(ning)?|ready)\s+to\s+die\b",
        r"\bwish\s+i\s+(was|were)\s+dead\b",
        r"\b(don'?t|do\s+not)\s+want\s+to\s+(live|be\s+alive|exist|wake\s+up)\b",
        r"\bend\s+it\s+all\b",
        r"\bno\s+(reason|point)\s+(to|in)\s+(live|living|go(ing)?\s+on)\b",
        r"\b(everyone|they|world)\s+(would\s+be|is|'d\s+be)\s+better\s+off\s+without\s+me\b",
        r"\bnot\s+be\s+(here|around)\s+(anymore|tomorrow)\b",
        r"\b(goodbye|bye)\s+forever\b",
        r"\bwrote\s+(a|my)\s+(suicide\s+)?note\b",
    ),
    "self_harm": _rx(
        r"\b(cut|cutting|hurt|hurting|harm|harming|burn|burning)\s+myself\b",
        r"\bself[\s-]?harm",
        r"\boverdos(e|ed|ing)\b",
        r"\bswallow(ed)?\s+(all\s+)?(the\s+)?pills\b",
    ),
    "harm_to_others": _rx(
        r"\b(kill|hurt|stab|shoot|attack)\s+(him|her|them|someone|somebody|people|everyone)\b",
        r"\bwant\s+(him|her|them)\s+dead\b",
    ),
    "immediate_danger": _rx(
        r"\b(he|she|they|someone)\s+(is|are|keeps)\s+(hitting|beating|hurting|abusing)\s+me\b",
        r"\bi'?m\s+not\s+safe\b",
        r"\b(being|been)\s+(abused|assaulted|threatened)\b",
        r"\bgot\s+(a|the)\s+(gun|knife|rope)\b",
    ),
}

ELEVATED_PATTERNS = _rx(
    r"\bhopeless\b", r"\bworthless\b", r"\bcan'?t\s+(go\s+on|take\s+(it|this)\s+anymore|do\s+this\s+anymore)\b",
    r"\bwhat'?s\s+the\s+point\b", r"\bgive\s+up\s+on\s+(everything|life)\b",
    r"\bnobody\s+would\s+(care|notice|miss\s+me)\b", r"\bdisappear\s+forever\b",
    r"\bhate\s+myself\b", r"\bi'?m\s+a\s+burden\b", r"\bempty\s+inside\b",
)

# Protective phrasing: "I would never kill myself" lowers to elevated.
PROTECTIVE = _rx(r"\b(would|will)\s+never\b", r"\bnot\s+going\s+to\b", r"\bnot\s+(suicidal|planning)\b",
                 r"\b(movie|song|book|game|character|essay|research|article)\b")

# Output validation: things SENRA must never say.
OUTPUT_RULES: list[tuple[str, re.Pattern, str]] = [
    ("claims_human", _rx(r"\bi\s*(am|'m)\s+(a\s+)?(real\s+)?(human|person)\b(?!\s+(?:being\s+)?like)",
                         r"\bas\s+a\s+human\s+(being\s+)?myself\b"), "Claimed to be human"),
    ("claims_professional", _rx(r"\bi\s*(am|'m)\s+(a|your)\s+(licensed\s+|certified\s+)?(therapist|psychiatrist|psychologist|doctor|counsel?lor)\b",
                                r"\bas\s+your\s+(therapist|doctor|counsel?lor)\b"), "Claimed to be a professional"),
    ("diagnosis", _rx(r"\byou\s+(definitely\s+|clearly\s+|probably\s+)?(have|suffer\s+from)\s+(clinical\s+)?(depression|bipolar|ptsd|ocd|adhd|anxiety\s+disorder|schizophrenia|bpd|a\s+mental\s+illness)\b",
                      r"\bi\s+diagnose\b"), "Attempted a diagnosis"),
    ("dependency", _rx(r"\b(i'?m|i\s+am)\s+all\s+you\s+need\b", r"\byou\s+don'?t\s+need\s+(anyone|anybody|other\s+people)\b",
                       r"\bonly\s+i\s+(understand|care\s+about)\s+you\b"), "Encouraged emotional dependency"),
    ("method_info", _rx(r"\b(lethal|fatal)\s+dose\b", r"\bhow\s+to\s+(hang|overdose|cut)\b",
                        r"\bmost\s+painless\s+way\b"), "Harmful method information"),
]

HELPLINES = [
    {"name": "Tele-MANAS (Govt. of India, 24x7)", "contact": "14416 / 1-800-891-4416", "href": "tel:14416"},
    {"name": "Emergency Services (India)", "contact": "112", "href": "tel:112"},
    {"name": "AASRA (24x7)", "contact": "+91 98204 66726", "href": "tel:+919820466726"},
    {"name": "Vandrevala Foundation (24x7)", "contact": "+91 9999 666 555", "href": "tel:+919999666555"},
    {"name": "Outside India", "contact": "findahelpline.com", "href": "https://findahelpline.com"},
]


@dataclass
class RiskAssessment:
    level: str = "none"
    score: float = 0.0
    categories: list[str] = field(default_factory=list)
    escalate: bool = False
    reasons: list[str] = field(default_factory=list)
    helplines: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "level": self.level, "score": round(self.score, 3),
            "categories": self.categories, "escalate": self.escalate,
            "reasons": self.reasons, "helplines": self.helplines,
        }


@dataclass
class OutputValidation:
    passed: bool
    violations: list[str]

    def to_dict(self) -> dict:
        return {"passed": self.passed, "violations": self.violations}


class SafetyLayer:
    def assess(self, text: str, valence: float, intensity: float,
               recent_levels: list[str] | None = None) -> RiskAssessment:
        text = text or ""
        categories = [name for name, rx in CRISIS_PATTERNS.items() if rx.search(text)]
        reasons: list[str] = []
        protective = bool(PROTECTIVE.search(text))

        if categories and not protective:
            level, score = "crisis", 0.95
            reasons.append("Crisis language detected: " + ", ".join(categories))
        elif categories and protective:
            level, score = "elevated", 0.6
            reasons.append("Risk language with protective/contextual phrasing")
        elif ELEVATED_PATTERNS.search(text):
            level, score = "elevated", 0.55
            categories.append("hopelessness")
            reasons.append("Hopelessness / passive distress language")
        elif valence <= -0.55 and intensity >= 0.75:
            # Strong negative affect alone is monitored, not escalated.
            level, score = "low", 0.35
            categories.append("acute_distress")
            reasons.append("High-intensity negative affect from emotion fusion (monitoring)")
        elif valence < -0.25:
            level, score = "low", 0.2
        else:
            level, score = "none", 0.0

        # Conversation history: repeated elevated turns raise attention.
        recent = recent_levels or []
        if level == "elevated" and sum(1 for l in recent[-4:] if l in ("elevated", "crisis")) >= 2:
            score = min(0.8, score + 0.2)
            reasons.append("Sustained distress across recent turns")

        escalate = level == "crisis"
        return RiskAssessment(
            level=level, score=score, categories=categories, escalate=escalate,
            reasons=reasons, helplines=HELPLINES if level in ("crisis", "elevated") else [],
        )

    @staticmethod
    def validate_output(text: str) -> OutputValidation:
        violations = [desc for _, rx, desc in OUTPUT_RULES if rx.search(text or "")]
        return OutputValidation(passed=not violations, violations=violations)

    @staticmethod
    def crisis_fallback() -> str:
        return (
            "I'm really glad you told me, and I'm taking what you said seriously. "
            "You deserve support from a real person right now — I'm an AI, and I can't keep you safe the way someone "
            "who can be with you can.\n\n"
            "Please reach out to **Tele-MANAS at 14416** (free, 24x7) or call **112** if you're in immediate danger. "
            "If you can, let someone you trust know how you're feeling, or stay near another person for now.\n\n"
            "I'm still here to talk while you reach out. Are you safe at this moment?"
        )

    @staticmethod
    def safe_fallback() -> str:
        return (
            "I want to be careful with how I respond to that. I'm an AI companion, not a professional, "
            "but I'm here to listen. Could you tell me a little more about what's on your mind?"
        )

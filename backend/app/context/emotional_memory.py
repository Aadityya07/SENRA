"""Emotional Memory Module — consented, user-controllable long-term context.

Stores only light-weight, non-sensitive signals:
  * profile     – preferred name, role (e.g. student)
  * trigger     – topics that repeatedly co-occur with negative affect
  * uplift      – topics that co-occur with positive affect
  * preference  – preferred comforting style (listen vs. advice)

Users can disable memory or wipe it at any time (privacy by design).
"""
from __future__ import annotations

import re

from ..storage.database import Database

TOPICS: dict[str, re.Pattern] = {
    "exams & studies": re.compile(r"\b(exams?|tests?|studies|study|studying|college|university|semester|marks|grades|assignment|viva|project review|placement)\b", re.I),
    "work": re.compile(r"\b(work|job|boss|office|manager|deadline|career|interview|internship|colleague)\b", re.I),
    "family": re.compile(r"\b(family|parents?|mom|mum|dad|mother|father|brother|sister|siblings?)\b", re.I),
    "relationships": re.compile(r"\b(girlfriend|boyfriend|partner|relationship|crush|breakup|broke up|ex)\b", re.I),
    "friendships": re.compile(r"\b(friends?|friendship|classmates?|roommates?)\b", re.I),
    "health": re.compile(r"\b(sick|ill|health|pain|headache|hospital|doctor)\b", re.I),
    "sleep": re.compile(r"\b(sleep|insomnia|can'?t sleep|tired|nightmares?)\b", re.I),
    "money": re.compile(r"\b(money|rent|bills?|debt|loan|salary|broke)\b", re.I),
    "self-image": re.compile(r"\b(ugly|weight|appearance|not good enough|failure|confidence)\b", re.I),
    "loneliness": re.compile(r"\b(lonely|alone|isolated|no friends)\b", re.I),
    "music": re.compile(r"\b(music|song|singing|guitar|piano)\b", re.I),
    "nature & walks": re.compile(r"\b(walk|nature|park|beach|mountains?|sunset)\b", re.I),
    "games & hobbies": re.compile(r"\b(gaming|games?|hobby|drawing|painting|reading|books?|movies?|anime|cricket|football)\b", re.I),
}

NAME_RX = re.compile(r"\b(?:my name is|call me|i am called|i'm called)\s+([A-Z][a-z]{1,20}|[a-z]{2,20})\b", re.I)
ROLE_RX = re.compile(r"\bi(?:'m| am) an? ((?:final[- ]year |first[- ]year |second[- ]year |third[- ]year )?(?:student|engineer|developer|teacher|designer|doctor|nurse|artist|writer|programmer|researcher|freelancer|manager|intern))\b", re.I)
LISTEN_RX = re.compile(r"\b(just (want|need) (someone|you) to listen|just listen|don'?t (give|need) (me )?advice|no advice)\b", re.I)
ADVICE_RX = re.compile(r"\b(what should i do|any (advice|tips|suggestions)|give me (advice|tips)|how (do|can) i (fix|handle|deal with))\b", re.I)
NOT_NAMES = {"sad", "tired", "fine", "okay", "ok", "good", "bad", "not", "so", "very", "just", "really", "here", "back"}


class EmotionalMemory:
    def __init__(self, db: Database) -> None:
        self.db = db

    def observe(self, user_id: str, text: str, valence: float, intensity: float) -> list[str]:
        """Extract memory signals from a user message. Returns what was stored."""
        stored: list[str] = []
        m = NAME_RX.search(text)
        if m and m.group(1).lower() not in NOT_NAMES:
            name = m.group(1).capitalize()
            self.db.upsert_memory(user_id, "profile", "name", name, 0.9)
            stored.append(f"name={name}")
        m = ROLE_RX.search(text)
        if m:
            self.db.upsert_memory(user_id, "profile", "role", m.group(1).lower(), 0.8)
            stored.append(f"role={m.group(1).lower()}")
        if LISTEN_RX.search(text):
            self.db.upsert_memory(user_id, "preference", "comfort_style", "listen", 0.8)
            stored.append("comfort_style=listen")
        elif ADVICE_RX.search(text):
            self.db.upsert_memory(user_id, "preference", "comfort_style", "advice", 0.6)
            stored.append("comfort_style=advice")

        if intensity >= 0.3:
            for topic, rx in TOPICS.items():
                if rx.search(text):
                    if valence <= -0.25:
                        self.db.upsert_memory(user_id, "trigger", topic, "negative", 0.5)
                        stored.append(f"trigger={topic}")
                    elif valence >= 0.3:
                        self.db.upsert_memory(user_id, "uplift", topic, "positive", 0.5)
                        stored.append(f"uplift={topic}")
        return stored

    def profile(self, user_id: str) -> dict:
        rows = self.db.get_memory(user_id)
        prof: dict = {"name": None, "role": None, "comfort_style": None, "triggers": [], "uplifts": []}
        for r in rows:
            if r["memory_type"] == "profile":
                prof[r["memory_key"]] = r["memory_value"]
            elif r["memory_type"] == "preference" and r["memory_key"] == "comfort_style":
                prof["comfort_style"] = r["memory_value"]
            elif r["memory_type"] == "trigger":
                prof["triggers"].append({"topic": r["memory_key"], "count": r["count"]})
            elif r["memory_type"] == "uplift":
                prof["uplifts"].append({"topic": r["memory_key"], "count": r["count"]})
        prof["triggers"] = prof["triggers"][:4]
        prof["uplifts"] = prof["uplifts"][:3]
        return prof

    @staticmethod
    def summarise(prof: dict) -> str:
        parts = []
        if prof.get("name"):
            parts.append(f"Their name is {prof['name']}.")
        if prof.get("role"):
            parts.append(f"They are a {prof['role']}.")
        if prof.get("triggers"):
            parts.append("Things that have weighed on them before: " +
                         ", ".join(t["topic"] for t in prof["triggers"]) + ".")
        if prof.get("uplifts"):
            parts.append("Things that tend to lift their mood: " +
                         ", ".join(t["topic"] for t in prof["uplifts"]) + ".")
        if prof.get("comfort_style") == "listen":
            parts.append("When upset, they prefer being listened to over advice.")
        elif prof.get("comfort_style") == "advice":
            parts.append("When upset, they appreciate gentle practical suggestions.")
        return " ".join(parts)

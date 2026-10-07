"""Run scripted conversations through the full SENRA pipeline and print the
per-module analysis together with the generated replies.

    python -m scripts.eval_conversations            (from the backend folder)
    python -m scripts.eval_conversations --only 2
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.llm.adapter import build_adapter  # noqa: E402
from app.pipeline import CompanionPipeline  # noqa: E402
from app.storage.database import Database  # noqa: E402

SCENARIOS: list[tuple[str, list[str]]] = [
    ("Greeting & identity", ["hi", "who are you? are you a real person?"]),
    ("Loneliness → improving", [
        "I've been feeling really lonely lately. Nobody in my hostel really talks to me.",
        "yeah, I just moved here for college and everyone already has their groups",
        "talking to you actually helps a bit. thanks",
    ]),
    ("Exam stress + task", [
        "My name is Aditya and I'm a final year student. My project review is tomorrow and I'm so stressed",
        "can you give me a quick plan for tonight to prepare for the presentation?",
    ]),
    ("Anger toward companion", ["You're not even listening to me!", "okay, sorry. it's just been a bad day"]),
    ("Pure knowledge task", ["Explain the difference between supervised and unsupervised learning with examples"]),
    ("Good news", ["I got selected for the internship I wanted!!"]),
    ("Crisis", ["I don't want to live anymore. everyone would be better off without me"]),
    ("Breakup", ["my girlfriend broke up with me yesterday after 3 years. i can't stop thinking about her"]),
    ("Family pressure", ["my parents keep comparing me with my cousin who got into IIT. nothing i do is ever enough for them"]),
    ("Failed exam", ["I failed my exam", "i studied so hard though. i don't know what i'm doing wrong"]),
    ("Burnout", ["i'm so tired of everything. work, college, people. i just want to disappear for a while"]),
]


async def main(only: int | None) -> None:
    db = Database(Path(tempfile.mkdtemp()) / "eval.db")
    pipe = CompanionPipeline(db, build_adapter())
    pipe.text_emotion.load()
    for idx, (name, turns) in enumerate(SCENARIOS, 1):
        if only and idx != only:
            continue
        print(f"\n{'=' * 90}\nSCENARIO {idx}: {name}\n{'=' * 90}")
        cid = None
        for msg in turns:
            print(f"\nUSER: {msg}")
            t0 = time.perf_counter()
            async for ev in pipe.run_turn("eval-user", cid, msg):
                if ev["event"] == "meta":
                    cid = ev["data"]["conversation_id"]
                elif ev["event"] == "analysis":
                    f, d, s = ev["data"]["fusion"], ev["data"]["decision"], ev["data"]["safety"]
                    tr = ev["data"]["context"]["trend"]["trend"]
                    print(f"  [emotion={f['emotion']} int={f['intensity']:.2f} conf={f['confidence']:.2f} "
                          f"val={f['valence']:+.2f} trend={tr} | intent={d['intent']} strategy={d['strategy']} "
                          f"bg={d['background']} | risk={s['level']}]")
                elif ev["event"] == "done":
                    lat = ev["data"]["latency"]
                    print(f"SENRA ({lat['total_ms']} ms, first token {lat['first_token_ms']} ms"
                          f"{', REPLACED' if ev['data']['replaced'] else ''}):\n{ev['data']['text']}")
                elif ev["event"] == "error":
                    print("ERROR:", ev["data"])
            _ = t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int)
    asyncio.run(main(ap.parse_args().only))

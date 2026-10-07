"""Humanizer — deterministic post-processing of LLM phrasing.

Small LLMs fall back on stock "assistant" phrases ("It sounds like…",
"It's totally understandable…") even when told not to. These rules rewrite
those phrases into plainer, more human wording. `StreamRewriter` applies the
same rules to a token stream with a short look-ahead buffer, so the user never
sees the original phrasing while the reply is streaming.
"""
from __future__ import annotations

import difflib
import re
from typing import Callable

Rule = tuple[re.Pattern, Callable[[re.Match], str] | str]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


RULES: list[Rule] = [
    # Leaked template placeholders, e.g. "Thanks, [user's name]."
    (re.compile(r",?\s*\[(?:the\s+)?(?:user'?s?\s+)?name\]", re.I), ""),
    # "It sounds like you're going through…" -> "You're going through…"
    (re.compile(r"\bIt sounds like (you're|you are|you've|you have|you|this|that|it|things|everything)\b"),
     lambda m: _cap(m.group(1))),
    (re.compile(r"\bit sounds like (you're|you are|you've|you have|you|this|that|it|things|everything)\b"),
     lambda m: m.group(1)),
    (re.compile(r"\bI hear you saying that\b"), "I'm really listening"),
    (re.compile(r"\bI hear (?:that )?you(?:'re| are)\b"), "you're"),
    (re.compile(r"\bI hear (?:that )?you\b(?=\s+\w+ed\b)"), "you"),
    (re.compile(r"\bI hear you\.\s*"), "I'm right here with you. "),
    (re.compile(r"\bI hear you,\s*"), ""),
    (re.compile(r"\bI (?:can )?(?:totally |completely )?understand how\b"), "I can only imagine how"),
    # "It's totally understandable that/why X" -> "No wonder X"
    (re.compile(r"\bIt[’']s (?:totally |completely |perfectly |so )?understandable (?:that|why) "), "No wonder "),
    (re.compile(r"\bIt[’']s (?:totally |completely |perfectly |so )?understandable to\b"), "It makes so much sense to"),
    (re.compile(r"\bit[’']s (?:totally |completely |perfectly |so )?understandable (?:that|why) "), "no wonder "),
    # Therapy-speak
    (re.compile(r",?\s*(?:and|which is) (?:that[’']s |that is )?(?:totally |completely )?valid\b"), ""),
    (re.compile(r"\breal and valid\b"), "real"),
    (re.compile(r"\bIt[’']s important to remember (?:that )?(\w)"), lambda m: m.group(1).upper()),
    # Drop lecture-y "Remember," and robotic "As an AI," sentence openers.
    (re.compile(r"\b(?:Remember|Just remember),\s+(\w)"), lambda m: m.group(1).upper()),
    (re.compile(r"\bAs an AI(?: language model)?,\s+(\w)"), lambda m: m.group(1).upper()),
]

# Rewrites above can leave "you" at the start of a sentence in lower case.
_SENTENCE_START = re.compile(r"(^|[.!?]\s+|\n\s*)you\b")
# A first paragraph wrapped in quotes ("…") reads like a script.
_QUOTED_OPENING = re.compile(r'^\s*["“]([^"”\n]{20,})["”][ \t]*(?=\n|$)')

HOLD = 48  # characters held back while streaming (longest rule match)

_CAP_WORD = re.compile(r"\b[A-Z][a-z]{2,}\b")
_INTERJECTION = r"(Oh|Hey|Hi|Aw|Ah|Okay|Ok|Wow)"


def _fix_name(text: str, name: str) -> str:
    """Correct misspellings of the user's name and drop it as a reply opener
    ("Oh Aditya, that's…" -> "Oh, that's…") — small models overuse it."""
    lname = name.lower()
    if len(name) >= 4:
        def fix(m: re.Match) -> str:
            w = m.group(0)
            if w != name and w[0].lower() == lname[0] and abs(len(w) - len(name)) <= 2 \
                    and difflib.SequenceMatcher(None, w.lower(), lname).ratio() >= 0.8:
                return name
            return w
        text = _CAP_WORD.sub(fix, text)
    opener = re.compile(rf"^\s*{_INTERJECTION}?,?\s*{re.escape(name)}\s*[,.!—-]+\s*")
    m = opener.match(text)
    if m:
        rest = text[m.end():]
        if m.group(1):
            keep_case = re.match(r"I\b|[A-Z]{2}", rest)
            text = f"{m.group(1)}, " + (rest if keep_case else rest[:1].lower() + rest[1:])
        else:
            text = _cap(rest)
    return text


def humanize(text: str, name: str | None = None) -> str:
    text = text.replace("▁", " ")  # SentencePiece whitespace leaking from the tokenizer
    text = re.sub(r"(?<=[^\s]) {2,}(?=[^\s])", " ", text)
    for rx, repl in RULES:
        text = rx.sub(repl, text)
    if name:
        text = _fix_name(text, name)
    text = _QUOTED_OPENING.sub(lambda m: m.group(1), text)
    return _SENTENCE_START.sub(lambda m: m.group(1) + "You", text)


class StreamRewriter:
    """Applies `humanize` to a token stream without ever retracting emitted text."""

    def __init__(self, name: str | None = None) -> None:
        self.raw = ""
        self.sent = ""
        self.name = name

    def feed(self, chunk: str) -> str:
        self.raw += chunk
        out = humanize(self.raw, self.name)
        safe = len(out) - HOLD
        if safe > len(self.sent) and out.startswith(self.sent):
            piece = out[len(self.sent):safe]
            self.sent += piece
            return piece
        return ""

    def flush(self) -> str:
        out = humanize(self.raw, self.name)
        if out.startswith(self.sent):
            piece = out[len(self.sent):]
            self.sent = out
            return piece
        return ""  # final text is re-sent with the `done` event anyway

"""Persistence layer (SQLite for the prototype; schema mirrors the planned
PostgreSQL design: users, sessions/conversations, messages, emotional states
and emotional memory). Raw audio/video is never stored."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    memory_enabled  INTEGER NOT NULL DEFAULT 1,
    preferences     TEXT NOT NULL DEFAULT '{}',
    created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT 'New conversation',
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    meta            TEXT NOT NULL DEFAULT '{}',
    created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS emotional_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    message_id      TEXT,
    modality        TEXT NOT NULL,
    emotion         TEXT NOT NULL,
    intensity       REAL NOT NULL,
    confidence      REAL NOT NULL,
    valence         REAL NOT NULL,
    arousal         REAL NOT NULL,
    risk_level      TEXT NOT NULL DEFAULT 'none',
    created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS emotional_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    memory_type     TEXT NOT NULL,
    memory_key      TEXT NOT NULL,
    memory_value    TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.5,
    count           INTEGER NOT NULL DEFAULT 1,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    UNIQUE(user_id, memory_type, memory_key)
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_state_conv ON emotional_states(conversation_id, id);
"""


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class Database:
    def __init__(self, path: Path) -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    # ------------------------------------------------------------- users
    def ensure_user(self, user_id: str) -> dict:
        rows = self._all("SELECT * FROM users WHERE user_id=?", (user_id,))
        if rows:
            u = rows[0]
        else:
            self._exec("INSERT INTO users(user_id, created_at) VALUES(?,?)", (user_id, time.time()))
            u = {"user_id": user_id, "memory_enabled": 1, "preferences": "{}"}
        u["preferences"] = json.loads(u["preferences"] or "{}")
        u["memory_enabled"] = bool(u["memory_enabled"])
        return u

    def set_memory_enabled(self, user_id: str, enabled: bool) -> None:
        self.ensure_user(user_id)
        self._exec("UPDATE users SET memory_enabled=? WHERE user_id=?", (int(enabled), user_id))

    # ----------------------------------------------------- conversations
    def create_conversation(self, user_id: str, title: str) -> str:
        cid, now = new_id(), time.time()
        self._exec("INSERT INTO conversations VALUES(?,?,?,?,?)", (cid, user_id, title, now, now))
        return cid

    def get_conversation(self, cid: str) -> dict | None:
        rows = self._all("SELECT * FROM conversations WHERE conversation_id=?", (cid,))
        return rows[0] if rows else None

    def touch_conversation(self, cid: str) -> None:
        self._exec("UPDATE conversations SET updated_at=? WHERE conversation_id=?", (time.time(), cid))

    def rename_conversation(self, cid: str, title: str) -> None:
        self._exec("UPDATE conversations SET title=? WHERE conversation_id=?", (title, cid))

    def list_conversations(self, user_id: str) -> list[dict]:
        return self._all(
            "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.conversation_id) AS message_count "
            "FROM conversations c WHERE user_id=? ORDER BY updated_at DESC LIMIT 100", (user_id,))

    def delete_conversation(self, cid: str) -> None:
        for table in ("messages", "emotional_states", "conversations"):
            self._exec(f"DELETE FROM {table} WHERE conversation_id=?", (cid,))

    # ----------------------------------------------------------- messages
    def add_message(self, cid: str, role: str, content: str, meta: dict | None = None) -> str:
        mid = new_id()
        self._exec("INSERT INTO messages VALUES(?,?,?,?,?,?)",
                   (mid, cid, role, content, json.dumps(meta or {}), time.time()))
        return mid

    def delete_message(self, mid: str) -> None:
        self._exec("DELETE FROM messages WHERE message_id=?", (mid,))

    def update_message_meta(self, mid: str, meta: dict) -> None:
        self._exec("UPDATE messages SET meta=? WHERE message_id=?", (json.dumps(meta), mid))

    def get_messages(self, cid: str, limit: int | None = None) -> list[dict]:
        if limit:
            rows = self._all("SELECT * FROM (SELECT * FROM messages WHERE conversation_id=? "
                             "ORDER BY created_at DESC LIMIT ?) ORDER BY created_at ASC", (cid, limit))
        else:
            rows = self._all("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC", (cid,))
        for r in rows:
            r["meta"] = json.loads(r["meta"] or "{}")
        return rows

    def count_user_messages(self, cid: str) -> int:
        return self._all("SELECT COUNT(*) AS n FROM messages WHERE conversation_id=? AND role='user'", (cid,))[0]["n"]

    # --------------------------------------------------- emotional states
    def add_emotional_state(self, cid: str, mid: str, modality: str, state: dict, risk_level: str) -> None:
        self._exec(
            "INSERT INTO emotional_states(conversation_id, message_id, modality, emotion, intensity, confidence, "
            "valence, arousal, risk_level, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (cid, mid, modality, state["emotion"], state["intensity"], state["confidence"],
             state["valence"], state["arousal"], risk_level, time.time()))

    def get_emotional_states(self, cid: str, limit: int = 50) -> list[dict]:
        return self._all(
            "SELECT * FROM (SELECT * FROM emotional_states WHERE conversation_id=? AND modality='fused' "
            "ORDER BY id DESC LIMIT ?) ORDER BY id ASC", (cid, limit))

    # --------------------------------------------------- emotional memory
    def upsert_memory(self, user_id: str, mtype: str, key: str, value: str, confidence: float) -> None:
        now = time.time()
        self._exec(
            "INSERT INTO emotional_memory(user_id, memory_type, memory_key, memory_value, confidence, count, created_at, updated_at) "
            "VALUES(?,?,?,?,?,1,?,?) ON CONFLICT(user_id, memory_type, memory_key) DO UPDATE SET "
            "memory_value=excluded.memory_value, count=count+1, updated_at=excluded.updated_at, "
            "confidence=MIN(0.99, emotional_memory.confidence + 0.1)",
            (user_id, mtype, key, value, confidence, now, now))

    def get_memory(self, user_id: str) -> list[dict]:
        return self._all("SELECT * FROM emotional_memory WHERE user_id=? ORDER BY count DESC, updated_at DESC", (user_id,))

    def delete_memory(self, user_id: str, memory_id: int | None = None) -> None:
        if memory_id is None:
            self._exec("DELETE FROM emotional_memory WHERE user_id=?", (user_id,))
        else:
            self._exec("DELETE FROM emotional_memory WHERE user_id=? AND id=?", (user_id, memory_id))

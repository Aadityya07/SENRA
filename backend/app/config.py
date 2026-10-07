"""Central configuration for the SENRA backend.

Every value can be overridden with an environment variable so the same code
runs on a laptop (local Gemma via Ollama) or a GPU server later.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("SENRA_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM (Reasoning Engine) -------------------------------------------
    llm_provider: str = os.getenv("SENRA_LLM_PROVIDER", "ollama")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    llm_model: str = os.getenv("SENRA_LLM_MODEL", "gemma3n:e2b")
    llm_temperature: float = _env_float("SENRA_LLM_TEMPERATURE", 0.7)
    llm_top_p: float = _env_float("SENRA_LLM_TOP_P", 0.9)
    llm_num_ctx: int = _env_int("SENRA_LLM_NUM_CTX", 8192)
    llm_keep_alive: str = os.getenv("SENRA_LLM_KEEP_ALIVE", "30m")

    # --- Emotion Perception -------------------------------------------------
    text_emotion_model: str = os.getenv(
        "SENRA_TEXT_EMOTION_MODEL", "SamLowe/roberta-base-go_emotions"
    )
    # Set to "0" to skip the transformer and use only the affective lexicon.
    enable_transformer: bool = os.getenv("SENRA_ENABLE_TRANSFORMER", "1") == "1"

    # --- Context / Memory ---------------------------------------------------
    history_turns: int = _env_int("SENRA_HISTORY_TURNS", 10)
    db_path: Path = field(default_factory=lambda: DATA_DIR / "senra.db")

    # --- Responsible AI -----------------------------------------------------
    # Gentle well-being nudge after this many user messages in one conversation.
    session_nudge_after: int = _env_int("SENRA_SESSION_NUDGE_AFTER", 30)

    cors_origins: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv(
            "SENRA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    )


settings = Settings()

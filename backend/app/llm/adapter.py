"""Reasoning Engine (LLM) — provider abstraction.

    LLM Provider  ->  LLM Adapter  ->  Response Orchestrator

The rest of SENRA depends only on `LLMAdapter`, so the local Gemma model can
be swapped for GLM / Gemini / OpenAI / Claude without touching other modules.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx

from ..config import settings

log = logging.getLogger("senra.llm")


class LLMError(RuntimeError):
    pass


class LLMAdapter(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def stream_chat(self, messages: list[dict], *, temperature: float | None = None,
                          max_tokens: int | None = None) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def health(self) -> dict:
        ...


class OllamaAdapter(LLMAdapter):
    name = "ollama"

    def __init__(self, base_url: str = settings.ollama_url, model: str = settings.llm_model) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0))

    async def stream_chat(self, messages: list[dict], *, temperature: float | None = None,
                          max_tokens: int | None = None) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": settings.llm_keep_alive,
            "options": {
                "temperature": settings.llm_temperature if temperature is None else temperature,
                "top_p": settings.llm_top_p,
                "top_k": 40,
                "repeat_penalty": 1.08,
                "num_ctx": settings.llm_num_ctx,
                "num_predict": max_tokens or 1024,
            },
        }
        try:
            async with self._client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")
                    raise LLMError(f"Ollama returned {resp.status_code}: {body[:300]}")
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise LLMError(data["error"])
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
        except httpx.ConnectError as exc:
            raise LLMError("Cannot reach Ollama. Is it running? (`ollama serve`)") from exc

    async def health(self) -> dict:
        try:
            r = await self._client.get(f"{self.base_url}/api/tags", timeout=3.0)
            models = [m["name"] for m in r.json().get("models", [])]
            return {"provider": self.name, "model": self.model, "reachable": True,
                    "model_available": any(m == self.model or m.startswith(self.model + ":") for m in models)}
        except Exception as exc:  # pragma: no cover
            return {"provider": self.name, "model": self.model, "reachable": False, "error": str(exc)}

    async def warm_up(self) -> None:
        """Load the model into GPU memory so the first reply is fast."""
        try:
            await self._client.post(f"{self.base_url}/api/generate",
                                    json={"model": self.model, "prompt": "", "keep_alive": settings.llm_keep_alive},
                                    timeout=120.0)
        except Exception as exc:  # pragma: no cover
            log.warning("LLM warm-up failed: %s", exc)


def build_adapter() -> LLMAdapter:
    if settings.llm_provider == "ollama":
        return OllamaAdapter()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

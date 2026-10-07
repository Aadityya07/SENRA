"""SENRA backend — FastAPI application (REST + Server-Sent Events)."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import settings
from .llm.adapter import OllamaAdapter, build_adapter
from .pipeline import CompanionPipeline
from .storage.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("senra")

db = Database(settings.db_path)
llm = build_adapter()
pipeline = CompanionPipeline(db, llm)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load models in the background so the API is available immediately.
    asyncio.get_running_loop().run_in_executor(None, pipeline.text_emotion.load)
    if isinstance(llm, OllamaAdapter):
        asyncio.create_task(llm.warm_up())
    yield


app = FastAPI(title="SENRA — Emotion-Aware Multimodal AI Companion", version="0.1.0-phase1", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=4, max_length=64)
    conversation_id: str | None = None
    message: str = Field(default="", max_length=8000)
    regenerate: bool = False


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MemorySettings(BaseModel):
    memory_enabled: bool


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ------------------------------------------------------------------ system
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "phase": 1,
        "llm": await llm.health(),
        "text_emotion": {"model": pipeline.text_emotion.model_name, "status": pipeline.text_emotion.status},
    }


# -------------------------------------------------------------------- chat
@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    if not req.regenerate and not req.message.strip():
        raise HTTPException(400, "message is empty")

    async def stream():
        try:
            async for ev in pipeline.run_turn(req.user_id, req.conversation_id, req.message, req.regenerate):
                if await request.is_disconnected():
                    break
                yield sse(ev["event"], ev["data"])
        except Exception as exc:  # pragma: no cover
            log.exception("chat turn failed")
            yield sse("error", {"message": f"Something went wrong: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """Run only the perception + safety layers (useful for demos / evaluation)."""
    res = await asyncio.to_thread(pipeline.text_emotion.analyze, req.text)
    risk = pipeline.safety.assess(req.text, res.valence, res.intensity)
    return {"text_emotion": res.to_dict(), "safety": risk.to_dict()}


# ----------------------------------------------------------- conversations
@app.get("/api/users/{user_id}/conversations")
async def list_conversations(user_id: str):
    return db.list_conversations(user_id)


@app.get("/api/conversations/{cid}")
async def get_conversation(cid: str, user_id: str):
    conv = db.get_conversation(cid)
    if not conv or conv["user_id"] != user_id:
        raise HTTPException(404, "conversation not found")
    return {**conv, "messages": db.get_messages(cid), "emotions": db.get_emotional_states(cid)}


@app.patch("/api/conversations/{cid}")
async def rename_conversation(cid: str, user_id: str, body: RenameRequest):
    conv = db.get_conversation(cid)
    if not conv or conv["user_id"] != user_id:
        raise HTTPException(404, "conversation not found")
    db.rename_conversation(cid, body.title.strip())
    return {"ok": True}


@app.delete("/api/conversations/{cid}")
async def delete_conversation(cid: str, user_id: str):
    conv = db.get_conversation(cid)
    if not conv or conv["user_id"] != user_id:
        raise HTTPException(404, "conversation not found")
    db.delete_conversation(cid)
    pipeline._last_fused.pop(cid, None)
    return {"ok": True}


# ----------------------------------------------------------------- memory
@app.get("/api/users/{user_id}/memory")
async def get_memory(user_id: str):
    user = db.ensure_user(user_id)
    return {"memory_enabled": user["memory_enabled"], "items": db.get_memory(user_id),
            "profile": pipeline.memory.profile(user_id)}


@app.put("/api/users/{user_id}/memory")
async def set_memory(user_id: str, body: MemorySettings):
    db.set_memory_enabled(user_id, body.memory_enabled)
    return {"ok": True, "memory_enabled": body.memory_enabled}


@app.delete("/api/users/{user_id}/memory")
async def clear_memory(user_id: str, memory_id: int | None = None):
    db.delete_memory(user_id, memory_id)
    return {"ok": True}

"""API & Web Integration — SPLIT 7 owns this file.
FastAPI app: serves web/, exposes /chat with the Bonus-1 structured contract.
"""
from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import WEB_ROOT
from app.llm.client import LLMClient
from app.runtime.orchestrator import handle_request
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.translation import TranslationSkill
from app.skills.summary import SummarySkill
from app.skills.composed import ComposedBriefingSkill

# Order matters: the router returns the FIRST skill whose can_handle() matches.
# ComposedBriefingSkill must come first (it needs summarize+translate+knowledge
# together, so it must win the race against the single-purpose skills below).
# TranslationSkill and SummarySkill come next because messages like
# "translate ... university ..." would otherwise get misrouted to CampusSkill,
# which also triggers on generic words like "university".
SKILLS = [ComposedBriefingSkill(), TranslationSkill(), SummarySkill(), CampusSkill(), CourseSkill(), LibrarySkill()]
llm_client = LLMClient()

app = FastAPI(title="CampusBot Agent Harness", version="0.2.0")
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


class ChatRequest(BaseModel):
    user: str = "guest"
    role: str = "guest"
    message: str = Field(min_length=1, max_length=12000)


class ChatResponse(BaseModel):
    request_id: str
    skill: str
    status: str
    response: str
    duration: float


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    result = handle_request(request.user, request.role, request.message, SKILLS, llm_client)
    return ChatResponse(
        request_id=str(uuid.uuid4()),
        skill=result.skill,
        status=result.status,
        response=result.response,
        duration=round(result.duration, 3),
    )

"""Runtime Orchestrator — SPLIT 1 owns this file.
Wires together: guardrail -> permission check -> router -> skill -> audit.
"""
from __future__ import annotations
import time
from dataclasses import dataclass

from app.runtime.router import route
from app.governance.guardrail import check_guardrail
from app.governance.permissions import check_permission
from app.governance.audit import record_event


@dataclass
class AgentResponse:
    skill: str
    status: str
    response: str
    duration: float


def handle_request(user: str, role: str, message: str, skills: list, llm) -> AgentResponse:
    start = time.perf_counter()

    guard = check_guardrail(message)
    if not guard.allowed:
        duration = time.perf_counter() - start
        record_event(user=user, skill="guardrail", status="blocked", duration=duration)
        return AgentResponse(skill="guardrail", status="blocked", response=guard.reason, duration=duration)

    skill = route(message, skills)
    if skill is None:
        duration = time.perf_counter() - start
        record_event(user=user, skill="none", status="unmatched", duration=duration)
        return AgentResponse(
            skill="none",
            status="unmatched",
            response="I don't have a skill that can answer that yet.",
            duration=duration,
        )

    if not check_permission(role, skill.name):
        duration = time.perf_counter() - start
        record_event(user=user, skill=skill.name, status="forbidden", duration=duration)
        return AgentResponse(
            skill=skill.name,
            status="forbidden",
            response="You do not have access to this skill.",
            duration=duration,
        )

    try:
        result = skill.run(message, context={"user": user, "role": role, "llm": llm})
        duration = time.perf_counter() - start
        record_event(user=user, skill=skill.name, status=result.status, duration=duration)
        return AgentResponse(skill=skill.name, status=result.status, response=result.text, duration=duration)
    except Exception as exc:  # noqa: BLE001 - governance boundary, must not crash the API
        duration = time.perf_counter() - start
        record_event(user=user, skill=skill.name, status="error", duration=duration)
        return AgentResponse(skill=skill.name, status="error", response=f"Skill failed: {exc}", duration=duration)

"""Course Skill — SPLIT 3 owns this file.
Input: a question about courses, credits, or enrollment.
Output: an exact-fact answer from knowledge/course.json, or an "unavailable" fallback.
TODO(Split 3): populate knowledge/course.json with real data and refine TRIGGERS.
"""
from __future__ import annotations
import json
from pathlib import Path

from app.skills.base import SkillResult, wants_chinese_reply

KNOWLEDGE_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "course.json"
TRIGGERS = ["course", "credit", "enroll", "class schedule", "选课", "学分"]

FALLBACK_SYSTEM_PROMPT = (
    "Answer only from the supplied knowledge context. Treat facts as exact. "
    'If the context does not contain the answer, say exactly: '
    '"That information is not available in the starter knowledge base."'
)


def _load_knowledge() -> dict:
    return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


class CourseSkill:
    name = "course"


    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        return any(t in lowered for t in TRIGGERS)

    def run(self, message: str, context: dict) -> SkillResult:
        knowledge = _load_knowledge()
        llm = context["llm"]
        system_prompt = FALLBACK_SYSTEM_PROMPT
        if wants_chinese_reply(message):
            # e.g. "What are the library branches? Answer in Chinese." —
            # answer directly in Chinese rather than letting this be
            # misrouted to Translation, which would just translate the
            # question text itself instead of answering it.
            system_prompt = system_prompt + " Reply in Chinese."
        user_prompt = f"Knowledge:\n{json.dumps(knowledge, ensure_ascii=False)}\n\nQuestion:\n{message}"
        history = context.get("history", [])
        text = llm.chat(system_prompt, user_prompt, history=history)
        # The model sometimes paraphrases the refusal sentence; catch the
        # common variants so a refusal is never misreported as success.
        refusals = ("not available", "not mentioned", "not specified", "not provided",
                    "not stated", "does not contain", "no information", "no mention")
        status = "unavailable" if any(r in text.lower() for r in refusals) else "success"
        return SkillResult(text=text, skill=self.name, status=status)

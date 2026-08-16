"""Campus Skill — SPLIT 3 owns this file.
Input: a question about SZU identity facts (name, motto, founding year, campuses).
Output: an exact-fact answer from knowledge/campus.json, or an "unavailable" fallback.

Trigger note: "university" is included and CampusSkill is placed LAST in the
skill list (see app/api/server.py). This is deliberate and safe: more
specific skills (library, course, translation, summary, composed) are all
checked BEFORE campus, so they get first refusal on any word overlap (e.g.
"Shenzhen University Library" correctly goes to Library, not Campus).
Campus then acts as the catch-all for generic SZU-identity questions,
including ones the lab PDF specifically expects to hit the "not available"
fallback ("Who is the current president?", "Where is the International
Office?") rather than silently going unmatched.
"""
from __future__ import annotations
import json
from pathlib import Path

from app.skills.base import SkillResult

KNOWLEDGE_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "campus.json"
TRIGGERS = [
    "motto", "founded", "established", "campus", "university",
    "president", "international office", "校训", "成立",
]

FALLBACK_SYSTEM_PROMPT = (
    "Answer only from the supplied knowledge context. Treat facts as exact. "
    'If the context does not contain the answer, say exactly: '
    '"That information is not available in the starter knowledge base."'
)


def _load_knowledge() -> dict:
    return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


class CampusSkill:
    name = "campus"

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        return any(t in lowered for t in TRIGGERS)

    def run(self, message: str, context: dict) -> SkillResult:
        knowledge = _load_knowledge()
        llm = context["llm"]
        user_prompt = f"Knowledge:\n{json.dumps(knowledge, ensure_ascii=False)}\n\nQuestion:\n{message}"
        text = llm.chat(FALLBACK_SYSTEM_PROMPT, user_prompt)
        status = "unavailable" if "not available" in text.lower() else "success"
        return SkillResult(text=text, skill=self.name, status=status)

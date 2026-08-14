"""Summary Skill — SPLIT 4 owns this file.
Also used as the middle step of the Bonus 3 composition chain
(Knowledge Skill -> Summary Skill -> Translation Skill), see composed.py.

Failure/unavailable behavior:
- If there isn't enough text to meaningfully summarize, returns
  status="unavailable" instead of calling the model.
- If the model returns an empty response, returns status="error".
"""
from __future__ import annotations
from app.skills.base import SkillResult

TRIGGERS = ["summarize", "summary", "总结"]
MIN_CONTENT_LENGTH = 15  # characters, after stripping trigger words

SYSTEM_PROMPT = "Summarize the user's text in 2-3 concise sentences."


def _content_length(message: str) -> int:
    stripped = message.lower()
    for t in TRIGGERS:
        stripped = stripped.replace(t, "")
    return len(stripped.strip(" .:,\"'?"))


class SummarySkill:
    name = "summary"

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        return any(t in lowered for t in TRIGGERS)

    def run(self, message: str, context: dict) -> SkillResult:
        if _content_length(message) < MIN_CONTENT_LENGTH:
            return SkillResult(
                text="There isn't enough text provided to summarize.",
                skill=self.name,
                status="unavailable",
            )

        llm = context["llm"]
        text = llm.chat(SYSTEM_PROMPT, message)
        if not text.strip():
            return SkillResult(
                text="Summary failed: the model returned no output.",
                skill=self.name,
                status="error",
            )
        return SkillResult(text=text, skill=self.name, status="success")

"""Translation Skill — SPLIT 4 owns this file.
Input: text plus a translation cue in the message (e.g. "translate ... into Chinese").
Output: translated text via the LLM.

Failure/unavailable behavior:
- If there's no actual content to translate (just the trigger word alone),
  returns status="unavailable" instead of calling the model.
- If the model returns an empty response, returns status="error" instead
  of silently reporting success with nothing to show.
"""
from __future__ import annotations
from app.skills.base import SkillResult

TRIGGERS = ["translate", "翻译", "in chinese", "into chinese", "in english", "into english"]

SYSTEM_PROMPT = "Translate only the text requested by the user. Reply with the translation only."


def _has_translatable_content(message: str) -> bool:
    stripped = message.lower()
    for t in TRIGGERS:
        stripped = stripped.replace(t, "")
    return len(stripped.strip(" .:,\"'?")) > 0


class TranslationSkill:
    name = "translation"

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        return any(t in lowered for t in TRIGGERS)

    def run(self, message: str, context: dict) -> SkillResult:
        if not _has_translatable_content(message):
            return SkillResult(
                text="No text was found to translate. Please include the text you want translated.",
                skill=self.name,
                status="unavailable",
            )

        llm = context["llm"]
        text = llm.chat(SYSTEM_PROMPT, message)
        if not text.strip():
            return SkillResult(
                text="Translation failed: the model returned no output.",
                skill=self.name,
                status="error",
            )
        return SkillResult(text=text, skill=self.name, status="success")

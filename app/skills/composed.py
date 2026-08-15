"""Composed Briefing Skill (Bonus 3 — Skill Composition) — SPLIT 4 owns this file.
Chains: Knowledge Skill (campus/course/library) -> Summary Skill -> Translation Skill.

Trigger example: "Summarize the library info and translate it into Chinese."
This actually calls three skills in sequence and threads one's output into
the next's input — it is not just a standalone summarizer.

Important: the knowledge skill is asked a CLEANED question with the
summarize/translate scaffolding words stripped out. Small local models can
get confused and answer "not available" when a factual question is tangled
up with instructions like "summarize" and "translate into Chinese" in the
same prompt, even though the fact is genuinely in the knowledge base. This
was observed as flaky/inconsistent behavior on identical repeated input.
"""
from __future__ import annotations
import re
from app.skills.base import SkillResult
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.summary import SummarySkill
from app.skills.translation import TranslationSkill

SUMMARIZE_TRIGGERS = ["summarize", "summary", "brief", "总结"]
TRANSLATE_TRIGGERS = ["translate", "in chinese", "into chinese", "翻译"]

# Longer/more specific phrases first, so partial overlaps don't leave debris behind.
_STRIP_PHRASES = [
    "and translate it into chinese",
    "translate it into chinese",
    "and translate into chinese",
    "translate into chinese",
    "into chinese",
    "in chinese",
    "and translate",
    "translate",
    "summarize",
    "summary",
    "brief",
    "总结并翻译成中文",
    "总结并翻译",
    "翻译成中文",
    "翻译",
    "总结",
]

# The knowledge skills this composition can pull facts from.
# Library/Course checked before Campus for the same reason as server.py's
# SKILLS ordering: Campus's remaining triggers are more generic.
KNOWLEDGE_SKILLS = [LibrarySkill(), CourseSkill(), CampusSkill()]


def _clean_knowledge_query(message: str) -> str:
    """Strip summarize/translate scaffolding so the knowledge skill sees a
    plain factual question instead of a tangled multi-instruction sentence."""
    cleaned = message
    for phrase in _STRIP_PHRASES:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" .,:;\"'")
    # If stripping left nothing usable, fall back to the original message
    # rather than sending an empty question to the knowledge skill.
    return cleaned if len(cleaned) >= 3 else message


class ComposedBriefingSkill:
    name = "composed_briefing"

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        wants_summary = any(t in lowered for t in SUMMARIZE_TRIGGERS)
        wants_translation = any(t in lowered for t in TRANSLATE_TRIGGERS)
        touches_knowledge = any(k.can_handle(message) for k in KNOWLEDGE_SKILLS)
        return wants_summary and wants_translation and touches_knowledge

    def run(self, message: str, context: dict) -> SkillResult:
        # Step 1: Knowledge Skill — get the underlying facts, using a cleaned
        # question so the model isn't confused by summarize/translate wording.
        knowledge_skill = next((k for k in KNOWLEDGE_SKILLS if k.can_handle(message)), None)
        if knowledge_skill is None:
            return SkillResult(
                text="No matching knowledge skill was found to brief on.",
                skill=self.name,
                status="unavailable",
            )
        knowledge_query = _clean_knowledge_query(message)
        knowledge_result = knowledge_skill.run(knowledge_query, context)
        if knowledge_result.status != "success":
            return SkillResult(text=knowledge_result.text, skill=self.name, status=knowledge_result.status)

        # Step 2: Summary Skill — condense the knowledge answer.
        # Pass the text directly, without prefixing literal "summarize:"
        # wording — the skill's own system prompt already tells the model
        # what to do, and embedding the trigger word here risks confusing
        # a small model in exactly the way the knowledge step did.
        summary_skill = SummarySkill()
        summary_result = summary_skill.run(knowledge_result.text, context)
        if summary_result.status != "success":
            return SkillResult(text=summary_result.text, skill=self.name, status=summary_result.status)

        # Step 3: Translation Skill — translate the summary, same reasoning.
        translation_skill = TranslationSkill()
        translation_result = translation_skill.run(summary_result.text, context)
        if translation_result.status != "success":
            return SkillResult(text=translation_result.text, skill=self.name, status=translation_result.status)

        return SkillResult(text=translation_result.text, skill=self.name, status="success")

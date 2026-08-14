"""Composed Briefing Skill (Bonus 3 — Skill Composition) — SPLIT 4 owns this file.
Chains: Knowledge Skill (campus/course/library) -> Summary Skill -> Translation Skill.

Trigger example: "Summarize the library info and translate it into Chinese."
This actually calls three skills in sequence and threads one's output into
the next's input — it is not just a standalone summarizer.
"""
from __future__ import annotations
from app.skills.base import SkillResult
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.summary import SummarySkill
from app.skills.translation import TranslationSkill

SUMMARIZE_TRIGGERS = ["summarize", "summary", "brief", "总结"]
TRANSLATE_TRIGGERS = ["translate", "in chinese", "into chinese", "翻译"]

# The knowledge skills this composition can pull facts from
KNOWLEDGE_SKILLS = [CampusSkill(), CourseSkill(), LibrarySkill()]


class ComposedBriefingSkill:
    name = "composed_briefing"

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        wants_summary = any(t in lowered for t in SUMMARIZE_TRIGGERS)
        wants_translation = any(t in lowered for t in TRANSLATE_TRIGGERS)
        touches_knowledge = any(k.can_handle(message) for k in KNOWLEDGE_SKILLS)
        return wants_summary and wants_translation and touches_knowledge

    def run(self, message: str, context: dict) -> SkillResult:
        # Step 1: Knowledge Skill — get the underlying facts
        knowledge_skill = next((k for k in KNOWLEDGE_SKILLS if k.can_handle(message)), None)
        if knowledge_skill is None:
            return SkillResult(
                text="No matching knowledge skill was found to brief on.",
                skill=self.name,
                status="unavailable",
            )
        knowledge_result = knowledge_skill.run(message, context)
        if knowledge_result.status != "success":
            return SkillResult(text=knowledge_result.text, skill=self.name, status=knowledge_result.status)

        # Step 2: Summary Skill — condense the knowledge answer
        summary_skill = SummarySkill()
        summary_prompt = f"summarize: {knowledge_result.text}"
        summary_result = summary_skill.run(summary_prompt, context)
        if summary_result.status != "success":
            return SkillResult(text=summary_result.text, skill=self.name, status=summary_result.status)

        # Step 3: Translation Skill — translate the summary
        translation_skill = TranslationSkill()
        translation_prompt = f"translate into Chinese: {summary_result.text}"
        translation_result = translation_skill.run(translation_prompt, context)
        if translation_result.status != "success":
            return SkillResult(text=translation_result.text, skill=self.name, status=translation_result.status)

        return SkillResult(text=translation_result.text, skill=self.name, status="success")

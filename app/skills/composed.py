"""Composed briefing workflow with retry and partial-result recovery."""
from __future__ import annotations

from typing import Any

from app.governance.permissions import check_permission
from app.skills.base import Skill, SkillResult
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.summary import SummarySkill
from app.skills.translation import TranslationSkill

SUMMARIZE_TRIGGERS = ["summarize", "summary", "brief", "总结"]
TRANSLATE_TRIGGERS = ["translate", "in chinese", "into chinese", "翻译"]
KNOWLEDGE_SKILLS = [CampusSkill(), CourseSkill(), LibrarySkill()]


class ComposedBriefingSkill:
    name = "composed_briefing"

    def __init__(
        self,
        knowledge_skills: list[Skill] | None = None,
        summary_skill: Skill | None = None,
        translation_skill: Skill | None = None,
    ) -> None:
        """Dependencies are injectable to keep workflow tests deterministic."""
        self.knowledge_skills = knowledge_skills or KNOWLEDGE_SKILLS
        self.summary_skill = summary_skill or SummarySkill()
        self.translation_skill = translation_skill or TranslationSkill()

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        wants_summary = any(trigger in lowered for trigger in SUMMARIZE_TRIGGERS)
        wants_translation = any(trigger in lowered for trigger in TRANSLATE_TRIGGERS)
        touches_knowledge = any(skill.can_handle(message) for skill in self.knowledge_skills)
        return wants_summary and wants_translation and touches_knowledge

    def run(self, message: str, context: dict) -> SkillResult:
        knowledge_skill = next(
            (skill for skill in self.knowledge_skills if skill.can_handle(message)), None
        )
        if knowledge_skill is None:
            return SkillResult(
                text="No matching knowledge skill was found to brief on.",
                skill=self.name,
                status="unavailable",
            )

        steps: list[dict[str, Any]] = []
        knowledge = self._run_with_recovery(knowledge_skill, message, context, steps)
        if knowledge is None:
            return self._partial_result("The knowledge lookup failed; the workflow could not continue.", steps)

        summary = self._run_with_recovery(
            self.summary_skill, f"summarize: {knowledge.text}", context, steps
        )
        if summary is None:
            return self._partial_result(
                f"Workflow partially completed. Knowledge result: {knowledge.text}", steps
            )

        translation = self._run_with_recovery(
            self.translation_skill, f"translate into Chinese: {summary.text}", context, steps
        )
        if translation is None:
            return self._partial_result(
                "Workflow partially completed. The summary was generated, but translation failed. "
                f"Summary: {summary.text}", steps
            )

        return SkillResult(
            text=translation.text,
            skill=self.name,
            metadata={"workflow": "knowledge-summary-translation", "steps": steps},
        )

    def _run_with_recovery(
        self, skill: Skill, message: str, context: dict, steps: list[dict[str, Any]]
    ) -> SkillResult | None:
        """Run one workflow step at most twice without leaking exceptions."""
        step: dict[str, Any] = {"skill": skill.name, "status": "failed", "attempts": 0}
        steps.append(step)
        if not check_permission(context["role"], skill.name):
            step["error"] = "Permission denied."
            return None

        for attempt in range(1, 3):
            step["attempts"] = attempt
            try:
                result = skill.run(message, context)
            except Exception as exc:  # noqa: BLE001 - workflow isolation boundary
                error = f"{type(exc).__name__}: {exc}"
            else:
                if result.status == "success":
                    step["status"] = "success" if attempt == 1 else "recovered"
                    return result
                error = result.text or f"Skill returned status '{result.status}'."
            step["error"] = error[:300]
        return None

    def _partial_result(self, text: str, steps: list[dict[str, Any]]) -> SkillResult:
        return SkillResult(
            text=text,
            skill=self.name,
            status="partial",
            metadata={"workflow": "knowledge-summary-translation", "steps": steps},
        )

import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime.orchestrator import handle_request
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.translation import TranslationSkill
from app.skills.summary import SummarySkill
from app.skills.composed import ComposedBriefingSkill
from app.skills.base import SkillResult
from tests.fakes import FakeLLMClient, EmptyLLMClient

SKILLS = [ComposedBriefingSkill(), TranslationSkill(), SummarySkill(), CampusSkill(), CourseSkill(), LibrarySkill()]


class TestComposedBriefing(unittest.TestCase):
    """Bonus 3: Knowledge -> Summary -> Translation composition."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_composed_chain_routes_and_succeeds(self):
        result = handle_request(
            "u1", "admin",
            "Summarize the library info and translate it into Chinese.",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "composed_briefing")
        self.assertEqual(result.status, "success")
        self.assertEqual([step["skill"] for step in result.steps], ["library", "summary", "translation"])
        self.assertTrue(all(step["attempts"] == 1 for step in result.steps))

    def test_plain_knowledge_question_not_misrouted_to_composed(self):
        result = handle_request("u1", "admin", "What is the motto?", SKILLS, self.llm)
        self.assertEqual(result.skill, "campus")


class TestFailurePaths(unittest.TestCase):
    """Task 1 requirement: predictable failure/unavailable behavior per skill."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_translation_with_no_content_is_unavailable(self):
        result = handle_request("u1", "admin", "translate", SKILLS, self.llm)
        self.assertEqual(result.status, "unavailable")

    def test_summary_with_too_little_content_is_unavailable(self):
        result = handle_request("u1", "admin", "summarize: hi", SKILLS, self.llm)
        self.assertEqual(result.status, "unavailable")

    def test_translation_empty_model_response_is_error(self):
        result = handle_request("u1", "admin", "translate: hello there", SKILLS, EmptyLLMClient())
        self.assertEqual(result.status, "error")


class TestRoutingRegression(unittest.TestCase):
    """Regression test: a translate request containing 'university' must not
    be misrouted to the campus skill just because campus also matches that word."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_translate_with_university_keyword_routes_to_translation(self):
        result = handle_request(
            "u1", "admin",
            "translate: Welcome to Shenzhen University",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "translation")
        self.assertEqual(result.status, "success")


class _WorkflowSkill:
    def __init__(self, name, outcomes, handles=False):
        self.name = name
        self.outcomes = list(outcomes)
        self.handles = handles

    def can_handle(self, message):
        return self.handles

    def run(self, message, context):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            return SkillResult("temporary error", self.name, "error")
        return SkillResult(outcome, self.name)


class TestWorkflowRecovery(unittest.TestCase):
    """Bonus: steps are ordered, retried once, and retain usable partial output."""

    def _workflow(self, summary_outcomes=("summary",), translation_outcomes=("译文",)):
        library = _WorkflowSkill("library", ["library facts"], handles=True)
        summary = _WorkflowSkill("summary", summary_outcomes)
        translation = _WorkflowSkill("translation", translation_outcomes)
        return ComposedBriefingSkill([library], summary, translation)

    def _run(self, workflow):
        return handle_request(
            "u1", "admin", "summarize the library and translate into Chinese", [workflow], FakeLLMClient()
        )

    def test_other_knowledge_skill_can_start_workflow(self):
        campus = _WorkflowSkill("campus", ["campus facts"], handles=True)
        workflow = ComposedBriefingSkill([campus], _WorkflowSkill("summary", ["summary"]),
                                         _WorkflowSkill("translation", ["译文"]))
        result = self._run(workflow)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.steps[0]["skill"], "campus")

    def test_failed_first_attempt_is_recovered(self):
        result = self._run(self._workflow(translation_outcomes=(None, "译文")))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.steps[-1]["status"], "recovered")
        self.assertEqual(result.steps[-1]["attempts"], 2)

    def test_two_failures_return_partial_summary(self):
        result = self._run(self._workflow(translation_outcomes=(None, None)))
        self.assertEqual(result.status, "partial")
        self.assertIn("summary", result.response)
        self.assertEqual(result.steps[-1]["status"], "failed")
        self.assertEqual(result.steps[-1]["attempts"], 2)

    def test_exception_is_isolated_and_retried(self):
        result = self._run(self._workflow(summary_outcomes=(RuntimeError("temporary failure"), RuntimeError("temporary failure"))))
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.steps[1]["status"], "failed")
        self.assertEqual(result.steps[1]["attempts"], 2)
        self.assertIn("RuntimeError", result.steps[1]["error"])


if __name__ == "__main__":
    unittest.main()

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
from tests.fakes import FakeLLMClient, EmptyLLMClient

SKILLS = [ComposedBriefingSkill(), TranslationSkill(), SummarySkill(), CourseSkill(), LibrarySkill(), CampusSkill()]


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

    def test_plain_knowledge_question_not_misrouted_to_composed(self):
        result = handle_request("u1", "admin", "What is the motto?", SKILLS, self.llm)
        self.assertEqual(result.skill, "campus")

    def test_composed_chain_not_confused_by_scaffolding_words(self):
        """Regression: a small model that gets confused by literal
        'summarize'/'translate' wording appearing in its own prompt must
        still get a clean, unconfused question at each step of the chain.
        Observed in practice as flaky/inconsistent results on identical
        repeated input with the real local model."""

        class ConfusableLLM:
            def chat(self, system_prompt, user_prompt):
                lowered = user_prompt.lower()
                if "translate" in lowered or "summarize" in lowered:
                    return "That information is not available in the starter knowledge base."
                return "The libraries are located at No. 3688 Nanhai Avenue, Nanshan District, Shenzhen, China."

        result = handle_request(
            "u1", "admin",
            "Summarize the library info and translate it into Chinese.",
            SKILLS, ConfusableLLM(),
        )
        self.assertEqual(result.status, "success")
        self.assertNotIn("not available", result.response.lower())


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

    def test_library_question_mentioning_university_routes_to_library(self):
        """A library question that happens to contain 'university' (e.g. because
        it says 'Shenzhen University Library') must route to library, not campus."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_course_question_mentioning_university_routes_to_course(self):
        result = handle_request(
            "u1", "admin",
            "What courses does Shenzhen University offer?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "course")


if __name__ == "__main__":
    unittest.main()

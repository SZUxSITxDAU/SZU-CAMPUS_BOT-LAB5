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
            def chat(self, system_prompt, user_prompt, history=None):
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

    def test_composed_chain_uses_literal_skill_calls_with_few_shot_prompts(self):
        """The composed chain genuinely calls Knowledge -> Summary ->
        Translation skills in sequence (matching the PDF's Bonus 3 diagram
        literally). For already-short content, Summary passes through
        unchanged (see summary.py) rather than risking degradation, so this
        typically produces 2 real LLM calls (knowledge + translation), and
        the full content must survive intact into the final translation."""

        class TrackingLLM:
            def __init__(self):
                self.calls = []

            def chat(self, system_prompt, user_prompt, history=None):
                self.calls.append((system_prompt, user_prompt))
                if "translate" in system_prompt.lower():
                    return "深圳大学图书馆的地址是深圳市南山区南海大道3688号。"
                return (
                    "The main branches of Shenzhen University Library are the North "
                    "Library in Huidian Building, Yuehai Campus, the South Library in "
                    "Huizhi Building, Yuehai Campus, and the Central Library in Qiming "
                    "Building, Lihu Campus. The official address is No. 3688 Nanhai "
                    "Avenue, Nanshan District, Shenzhen, China."
                )

        llm = TrackingLLM()
        result = handle_request(
            "u1", "admin",
            "Summarize the library info and translate it into Chinese.",
            SKILLS, llm,
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(len(llm.calls), 2)  # knowledge + translation (summary passthrough)
        translation_input = llm.calls[-1][1]
        self.assertIn("Nanhai Avenue", translation_input)
        self.assertIn("Central Library", translation_input)
        # The translation system prompt should include the few-shot example.
        translation_system_prompt = llm.calls[-1][0]
        self.assertIn("Example:", translation_system_prompt)


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

    def test_answer_in_chinese_phrase_routes_to_knowledge_not_translation(self):
        """Regression: 'answer in Chinese' tacked onto a real question must
        route to the knowledge skill (which then answers IN Chinese), not
        to Translation (which would just translate the question text
        itself back to the user instead of answering it)."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library? answer in chinese",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_translate_the_answer_phrase_routes_to_knowledge_not_translation(self):
        """Regression: this is worse than the 'answer in chinese' case —
        Translation has NO knowledge base access, so if it grabs a real
        question like this, it hallucinates a plausible-looking but
        completely fabricated answer instead of erroring or refusing.
        'translate the answer' must be recognized as referring to a
        FUTURE answer, not text given directly to translate right now."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library? translate the answer to chinese",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_translate_it_pronoun_in_same_message_routes_to_knowledge(self):
        """Regression: 'translate it' with no separate text given (all in
        one message, e.g. 'What are the branches? and can u translate it
        into chinese') has nothing for 'it' to refer to except the answer
        about to be given — must route to the knowledge skill, not
        Translation. Also covers a real observed typo ('chines')."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library? and can u translate it into chines",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

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

    def test_missing_knowledge_question_with_university_reaches_campus_fallback(self):
        """The PDF's baseline test expects 'Who is the current president of
        Shenzhen University?' to reach Campus's 'not available' fallback, not
        go unmatched. 'university' must still route here when nothing more
        specific (library/course/translate/summarize) also matches."""
        result = handle_request(
            "u1", "admin",
            "Who is the current president of Shenzhen University?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "campus")

    def test_international_office_question_reaches_campus_fallback(self):
        """The PDF's other baseline missing-knowledge question has no
        'university' in it at all, so campus needs an explicit trigger
        for this exact phrase."""
        result = handle_request(
            "u1", "admin",
            "Where is the International Office?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "campus")


if __name__ == "__main__":
    unittest.main()

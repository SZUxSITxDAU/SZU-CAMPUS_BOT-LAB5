import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.skills.campus import CampusSkill
from tests.fakes import FakeLLMClient


class TestCampusSkill(unittest.TestCase):
    def setUp(self):
        self.skill = CampusSkill()
        self.llm = FakeLLMClient()

    def test_handles_motto_question(self):
        self.assertTrue(self.skill.can_handle("What is the motto?"))

    def test_missing_knowledge_does_not_invent_answer(self):
        result = self.skill.run(
            "Who is the current president?",
            context={"llm": self.llm},
        )
        self.assertEqual(result.status, "unavailable")
        self.assertIn("not available", result.text.lower())


class TestKnowledgeSkillsAreHistoryFree(unittest.TestCase):
    """Regression: session history passed into the knowledge skills made the
    model continue in whatever language the conversation drifted into
    (observed live: 'SZU的 motto 是 ...' after Chinese turns) and made
    identical questions non-deterministic. Knowledge answers must depend
    only on the knowledge file and the question."""

    def test_knowledge_and_summary_skills_ignore_session_history(self):
        from app.skills.course import CourseSkill
        from app.skills.library import LibrarySkill
        from app.skills.summary import SummarySkill

        received = []

        class RecordingLLM(FakeLLMClient):
            def chat(self, system_prompt, user_prompt, history=None):
                received.append(history)
                return super().chat(system_prompt, user_prompt, history=history)

        poisoned = [
            {"role": "user", "content": "translate to chinese"},
            {"role": "assistant", "content": "欢迎来到深圳大学"},
        ]
        context = {"llm": RecordingLLM(), "history": poisoned}
        CampusSkill().run("What is the motto?", context)
        CourseSkill().run("How many credits is CS201?", context)
        LibrarySkill().run("Where is the library?", context)
        SummarySkill().run(
            "Summarize: a long enough piece of text to pass the length check.",
            context,
        )
        self.assertEqual(len(received), 4)
        for h in received:
            self.assertFalse(h, "a knowledge/summary skill passed history to the LLM")

    def test_translation_skill_still_receives_history(self):
        from app.skills.translation import TranslationSkill

        received = []

        class RecordingLLM(FakeLLMClient):
            def chat(self, system_prompt, user_prompt, history=None):
                received.append(history)
                return super().chat(system_prompt, user_prompt, history=history)

        history = [
            {"role": "user", "content": "Where is the library?"},
            {"role": "assistant", "content": "No. 3688 Nanhai Avenue."},
        ]
        TranslationSkill().run(
            "translate to chinese", {"llm": RecordingLLM(), "history": history}
        )
        self.assertEqual(received, [history])


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

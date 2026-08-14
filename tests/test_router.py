import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime.router import route
from app.skills.campus import CampusSkill
from app.skills.library import LibrarySkill
from app.skills.translation import TranslationSkill


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.skills = [CampusSkill(), LibrarySkill(), TranslationSkill()]

    def test_routes_campus_question(self):
        skill = route("What is the motto?", self.skills)
        self.assertEqual(skill.name, "campus")

    def test_routes_library_question(self):
        skill = route("Where is the library?", self.skills)
        self.assertEqual(skill.name, "library")

    def test_unrelated_request_not_misrouted(self):
        skill = route("asdkjqwe random gibberish zzz", self.skills)
        self.assertIsNone(skill)


if __name__ == "__main__":
    unittest.main()

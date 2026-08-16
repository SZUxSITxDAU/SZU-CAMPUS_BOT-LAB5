import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime import memory


class TestSessionMemory(unittest.TestCase):
    def setUp(self):
        # each test gets a unique session id so tests don't interfere
        self.session_id = f"test-{self._testMethodName}"

    def test_empty_session_has_no_history(self):
        self.assertEqual(memory.get_history("nonexistent-session"), [])

    def test_record_and_retrieve_one_exchange(self):
        memory.record_exchange(self.session_id, "hello", "hi there")
        history = memory.get_history(self.session_id)
        self.assertEqual(history, [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ])

    def test_sessions_are_isolated(self):
        session_a = f"{self.session_id}-A"
        session_b = f"{self.session_id}-B"
        memory.record_exchange(session_a, "msg A", "reply A")
        memory.record_exchange(session_b, "msg B", "reply B")
        self.assertNotEqual(memory.get_history(session_a), memory.get_history(session_b))
        self.assertIn({"role": "user", "content": "msg A"}, memory.get_history(session_a))
        self.assertNotIn({"role": "user", "content": "msg A"}, memory.get_history(session_b))

    def test_history_trims_to_max_turns(self):
        for i in range(memory.MAX_TURNS + 5):
            memory.record_exchange(self.session_id, f"msg{i}", f"resp{i}")
        history = memory.get_history(self.session_id)
        self.assertEqual(len(history), memory.MAX_TURNS * 2)
        # the oldest surviving message should NOT be msg0 (it got trimmed)
        self.assertNotIn({"role": "user", "content": "msg0"}, history)

    def test_clear_session_removes_history(self):
        memory.record_exchange(self.session_id, "hello", "hi")
        memory.clear_session(self.session_id)
        self.assertEqual(memory.get_history(self.session_id), [])


if __name__ == "__main__":
    unittest.main()

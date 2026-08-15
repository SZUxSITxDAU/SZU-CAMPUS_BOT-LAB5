import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.governance.audit import record_event, LOG_FILE


class TestAudit(unittest.TestCase):
    def test_record_event_creates_log_line(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        before = LOG_FILE.read_text(encoding="utf-8").splitlines() if LOG_FILE.exists() else []
        record_event(user="test_user", skill="campus", status="success", duration=0.1)
        after = LOG_FILE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(after), len(before) + 1)
        self.assertIn("test_user", after[-1])


if __name__ == "__main__":
    unittest.main()

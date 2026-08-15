import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.server import ChatRequest, chat
from app.runtime.orchestrator import AgentResponse


class TestWorkflowApiResponse(unittest.TestCase):
    def test_chat_exposes_workflow_steps(self):
        workflow_steps = [{"skill": "library", "status": "success", "attempts": 1}]
        response = AgentResponse("composed_briefing", "success", "translated", 0.01, workflow_steps)
        with patch("app.api.server.handle_request", return_value=response):
            result = chat(ChatRequest(message="summarize the library and translate into Chinese", role="admin"))
        self.assertEqual(result.steps, workflow_steps)


if __name__ == "__main__":
    unittest.main()

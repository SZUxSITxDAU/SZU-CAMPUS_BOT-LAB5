"""Deterministic fake LLM backends so tests run without Ollama — SPLIT 7 owns this file."""
from __future__ import annotations


class FakeLLMClient:
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        lowered_user = user_prompt.lower()
        lowered_system = system_prompt.lower()
        if "president" in lowered_user or "international office" in lowered_user:
            return "That information is not available in the starter knowledge base."
        if "translate" in lowered_system:
            return "已翻译内容"
        if "summarize" in lowered_system:
            return "Short summary of the provided text."
        return "Shenzhen University was established in 1983."


class EmptyLLMClient:
    """Simulates a model that returns nothing, to test each skill's error path."""

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return ""

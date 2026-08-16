"""Skill interface contract — SPLIT 2 owns this file.
This is the seam every Skill and the Router agree on. Do not change this
signature without telling every skill owner (Splits 3 and 4).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SkillResult:
    text: str
    skill: str
    status: str = "success"  # "success" | "unavailable" | "error"


class Skill(Protocol):
    name: str

    def can_handle(self, message: str) -> bool:
        """Return True if this skill should handle the message."""
        ...

    def run(self, message: str, context: dict) -> "SkillResult":
        """Execute the skill and return a SkillResult."""
        ...


CHINESE_HINT_WORDS = ["chinese", "chines", "中文"]  # "chines" covers a real observed typo


def wants_chinese_reply(message: str) -> bool:
    """Detect a language preference like 'answer in Chinese' embedded in an
    otherwise-normal question, so a knowledge skill can answer directly in
    Chinese instead of the question being misrouted to the Translation
    skill (which would just translate the question text itself, not
    answer it)."""
    lowered = message.lower()
    return any(hint in lowered for hint in CHINESE_HINT_WORDS)

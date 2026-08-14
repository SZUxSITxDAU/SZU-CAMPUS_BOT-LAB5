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

"""Skill Router — SPLIT 2 owns this file.
Rule-based selection: ask each registered skill if it can_handle() the
message, return the first match. Extend the matching rules per-skill,
inside each skill's own can_handle(), not here.
"""
from __future__ import annotations
from app.skills.base import Skill


def route(message: str, skills: list) -> "Skill | None":
    for skill in skills:
        if skill.can_handle(message):
            return skill
    return None

"""Permission control — SPLIT 5 owns this file.
Simple role -> allowed skill set (Bonus 2 / Task 3 Option C).
"""
from __future__ import annotations

ROLE_PERMISSIONS = {
    "guest": {"campus"},
    "member": {"campus", "course", "library", "translation"},
    "admin": {"campus", "course", "library", "translation", "summary", "composed_briefing"},
}


def check_permission(role: str, skill_name: str) -> bool:
    allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["guest"])
    return skill_name in allowed

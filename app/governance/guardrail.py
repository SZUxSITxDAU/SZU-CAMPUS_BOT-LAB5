"""Guardrail — SPLIT 5 owns this file.
Blocks obvious prompt-injection / unsafe requests before they reach a Skill.
Extend BLOCKED_PATTERNS with more rules as needed.
"""
from __future__ import annotations
from dataclasses import dataclass

BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore the above",
    "reveal your system prompt",
    "show private data",
    "disregard your instructions",
]


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""


def check_guardrail(message: str) -> GuardrailResult:
    lowered = message.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in lowered:
            return GuardrailResult(allowed=False, reason="Request blocked by guardrail policy.")
    return GuardrailResult(allowed=True)

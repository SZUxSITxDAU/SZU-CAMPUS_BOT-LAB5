"""Conversation Memory — SPLIT 1 owns this file (Runtime Core).

Scope, deliberately kept minimal (this is extra functionality beyond the
lab's required/bonus tasks, not something the grading rubric asks for):

- In-memory only. Resets when the server restarts. No persistence to disk.
- Per session_id (the frontend generates one per browser tab, see
  web/app.js), not per logged-in user — there's no real auth in this app.
- Keeps the last MAX_TURNS exchanges per session; older ones are dropped.

Important limitation, worth being upfront about: this app's Skill Router
is keyword-trigger based, not conversational. Memory here means the LLM
sees recent turns as CONTEXT when it answers, so pronouns/follow-up
phrasing make more sense to it — it does NOT mean a follow-up message
without its own trigger word will route to the right skill. E.g. asking
"Where is the library?" then "What about the other campus?" as a
follow-up still needs "campus" to appear in that second message for the
router to send it anywhere at all.
"""
from __future__ import annotations
from collections import defaultdict

MAX_TURNS = 5  # exchanges (user+assistant pairs) kept per session

_session_history: "dict[str, list[dict]]" = defaultdict(list)


def get_history(session_id: str) -> "list[dict]":
    """Returns prior turns for this session as Ollama-format message dicts
    ({"role": "user"/"assistant", "content": str}), oldest first."""
    return list(_session_history[session_id])


def record_exchange(session_id: str, user_message: str, assistant_response: str) -> None:
    """Append one user+assistant turn, trimming to the last MAX_TURNS."""
    history = _session_history[session_id]
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_response})
    # Keep only the last MAX_TURNS exchanges (each exchange = 2 entries)
    max_entries = MAX_TURNS * 2
    if len(history) > max_entries:
        del history[: len(history) - max_entries]


def clear_session(session_id: str) -> None:
    _session_history.pop(session_id, None)

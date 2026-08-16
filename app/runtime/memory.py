"""Conversation Memory — SPLIT 1 owns this file (Runtime Core).

Scope, deliberately kept minimal (this is extra functionality beyond the
lab's required/bonus tasks, not something the grading rubric asks for):

- In-memory only. Resets when the server restarts. No persistence to disk.
- Per session_id (the frontend generates one per browser tab, see
  web/app.js), not per logged-in user — there's no real auth in this app.
- Keeps the last MAX_TURNS exchanges per session; older ones are dropped.

Who consumes history, deliberately narrow: ONLY the Translation skill —
it exists so a follow-up like "translate to chinese" can act on the
previous answer. Knowledge skills (campus/course/library), summary, and
the composed chain run history-free: their answers depend only on the
knowledge files and the message, and passing prior turns into them made
the model continue in whatever language the conversation drifted into
and made identical questions give different answers.

Important limitation, worth being upfront about: this app's Skill Router
is keyword-trigger based, not conversational — a follow-up message
without its own trigger word will not route anywhere. E.g. asking
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


# Only outcomes that are real conversational content belong in memory.
# Control-plane refusals (blocked / forbidden / unmatched / error) must NOT be
# recorded: replaying "You do not have access to this skill." as a prior
# assistant turn poisons later LLM calls — observed live as the translation
# skill regurgitating its own few-shot example after a guest's denied attempt
# was retried as member in the same session.
CONVERSATIONAL_STATUSES = {"success", "unavailable"}


def should_record(status: str) -> bool:
    """True if an exchange with this outcome should enter session memory."""
    return status in CONVERSATIONAL_STATUSES


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

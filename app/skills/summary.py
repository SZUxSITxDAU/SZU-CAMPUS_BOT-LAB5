"""Summary Skill — SPLIT 4 owns this file.
Also used as the middle step of the Bonus 3 composition chain
(Knowledge Skill -> Summary Skill -> Translation Skill), see composed.py.

Design note: when composed.py hands this skill a short knowledge answer
(typically ~300 chars), it passes the text through UNCHANGED instead of
calling the LLM. Chaining a small local model through an extra
summarization hop on already-concise text tends to lose real content and
drift into vague meta-commentary (e.g. "the information is available") —
passthrough avoids that failure mode while still genuinely summarizing
longer input when summarization would actually help.

The passthrough requires context["from_composition"], because it is only
sound when the input is knowledge text. When this skill runs directly the
input is the user's own request, and an unconditional passthrough echoed
that request back as a successful summary.

Failure/unavailable behavior:
- If there isn't enough text to meaningfully summarize, returns
  status="unavailable" instead of calling the model.
- If the model returns an empty response, returns status="error".
"""
from __future__ import annotations
from app.skills.base import SkillResult

TRIGGERS = ["summarize", "summarise", "summary", "总结"]
MIN_CONTENT_LENGTH = 15  # characters, after stripping trigger words
PASSTHROUGH_MAX_LENGTH = 400  # chars; below this, skip the LLM summarization hop

SYSTEM_PROMPT = (
    "Summarize the following text in 2-3 concise sentences. State the "
    "actual facts directly, preserving specific names, addresses, and "
    "numbers. Do not describe the text abstractly (do not say things like "
    "'the information is provided' or 'is available').\n\n"
    "Example:\n"
    "Input: Shenzhen University has two campuses. Yuehai Campus is the main "
    "campus, established in 1983. Lihu Campus was added later as the "
    "university expanded and now hosts several engineering colleges.\n"
    "Output: Shenzhen University has two campuses: Yuehai (the original "
    "campus, established 1983) and Lihu, which was added later and now "
    "hosts several engineering colleges.\n\n"
    "Now summarize the following text the same way:"
)


def _content_length(message: str) -> int:
    stripped = message.lower()
    for t in TRIGGERS:
        stripped = stripped.replace(t, "")
    return len(stripped.strip(" .:,\"'?"))


class SummarySkill:
    name = "summary"

    def can_handle(self, message: str) -> bool:
        lowered = message.lower()
        return any(t in lowered for t in TRIGGERS)

    def run(self, message: str, context: dict) -> SkillResult:
        content_length = _content_length(message)
        if content_length < MIN_CONTENT_LENGTH:
            return SkillResult(
                text="There isn't enough text provided to summarize.",
                skill=self.name,
                status="unavailable",
            )

        # Already concise — pass through unchanged rather than risk an LLM
        # hop degrading real content into vague commentary.
        # Only valid when composed.py handed us KNOWLEDGE TEXT. Reached
        # directly, the input is the user's own request, and passing it
        # through echoed the request back as a successful "summary"
        # (e.g. "Summarize the library info" -> "Summarize the library info").
        if context.get("from_composition") and len(message.strip()) <= PASSTHROUGH_MAX_LENGTH:
            return SkillResult(text=message.strip(), skill=self.name, status="success")

        llm = context["llm"]
        # No session history: the text to summarize is fully contained in
        # the message, and prior turns only invite language/style bleed.
        text = llm.chat(SYSTEM_PROMPT, message)
        if not text.strip():
            return SkillResult(
                text="Summary failed: the model returned no output.",
                skill=self.name,
                status="error",
            )
        return SkillResult(text=text, skill=self.name, status="success")

"""Translation Skill — SPLIT 4 owns this file.
Input: text plus a translation cue in the message (e.g. "translate ... into Chinese").
Output: translated text via the LLM.

Trigger note: only "translate"/"翻译" trigger this skill — NOT generic
phrases like "in chinese"/"into chinese" on their own. Those phrases are
ambiguous: "Translate X into Chinese" is a real translation request, but
"What is X? Answer in Chinese" is a knowledge question with a language
preference, not a request to translate the question text itself. The
latter is handled by the knowledge skills (see base.py's
wants_chinese_reply), which answer directly in Chinese rather than having
their own question echoed back translated.

Prompt design note: the system prompt includes a concrete worked example
(few-shot), not just an instruction. Small models are much more likely to
literally translate when shown one clear input->output pair to pattern-match
against, versus only being told "translate this" in the abstract — the
latter leaves more room to drift into describing/commenting on the text
instead of transforming it.

Failure/unavailable behavior:
- If there's no actual content to translate (just the trigger word alone),
  returns status="unavailable" instead of calling the model.
- If the model returns an empty response, returns status="error" instead
  of silently reporting success with nothing to show.
"""
from __future__ import annotations
from app.skills.base import SkillResult

TRIGGERS = ["translate", "翻译"]

# Phrases like "translate the answer to Chinese" or "answer in Chinese"
# reference a FUTURE/derived answer to a question, not text given directly
# to translate right now. Same idea for "translate it"/"translate that" —
# a pronoun with nothing earlier IN THIS SAME MESSAGE for it to refer to
# (e.g. "What are the library branches? and can you translate it into
# Chinese" — there's no separate piece of text being handed over, "it"
# means "the answer you're about to give"). If present, this is really a
# knowledge question with a language preference — defer to the knowledge
# skills instead (see base.py's wants_chinese_reply), which have real data
# to answer from and (via conversation memory) can resolve a genuine
# pronoun reference to an earlier turn correctly, unlike Translation.
REFERENCE_PHRASES = [
    "the answer", "your answer", "answer in chinese", "answer to chinese",
    "answer into chinese", "translate it", "translate that",
    "回答", "答案", "翻译它", "翻译这个",
]


def _references_something_else(message: str) -> bool:
    lowered = message.lower()
    return any(p in lowered for p in REFERENCE_PHRASES)


def references_future_answer(message: str) -> bool:
    """Public view of the rule above, so composed.py can apply the SAME
    definition instead of duplicating the phrase list. A message that refers
    to an answer not yet given belongs to a knowledge skill (which answers
    directly in Chinese), not to Translation and not to composition."""
    return _references_something_else(message)

SYSTEM_PROMPT = (
    "Translate the given text into Chinese. Output ONLY the Chinese "
    "translation — no English, no commentary, no description of the text, "
    "no meta-statements like 'the text says' or 'this is about'. Preserve "
    "every specific fact (names, addresses, numbers) exactly.\n\n"
    "Example:\n"
    "Input: The library is located at 123 Main Street, next to the science building.\n"
    "Output: 图书馆位于主街123号，紧邻科学楼。\n\n"
    "Now translate the following text the same way:"
)


def _has_translatable_content(message: str) -> bool:
    stripped = message.lower()
    for t in TRIGGERS:
        stripped = stripped.replace(t, "")
    return len(stripped.strip(" .:,\"'?")) > 0


class TranslationSkill:
    name = "translation"

    def can_handle(self, message: str) -> bool:
        if _references_something_else(message):
            return False
        lowered = message.lower()
        return any(t in lowered for t in TRIGGERS)

    def run(self, message: str, context: dict) -> SkillResult:
        if not _has_translatable_content(message):
            return SkillResult(
                text="No text was found to translate. Please include the text you want translated.",
                skill=self.name,
                status="unavailable",
            )

        llm = context["llm"]
        history = context.get("history", [])
        text = llm.chat(SYSTEM_PROMPT, message, history=history)
        if not text.strip():
            return SkillResult(
                text="Translation failed: the model returned no output.",
                skill=self.name,
                status="error",
            )
        return SkillResult(text=text, skill=self.name, status="success")

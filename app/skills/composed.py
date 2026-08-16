"""Composed Briefing Skill (Bonus 3 — Skill Composition) — SPLIT 4 owns this file.
Chains: Knowledge Skill (campus/course/library) -> Summary Skill -> Translation Skill.

Trigger example: "Summarize the library info and translate it into Chinese."
This actually calls three skills in sequence and threads one's output into
the next's input — it is not just a standalone summarizer.

Important: the knowledge skill is asked a CLEANED question with the
summarize/translate scaffolding words stripped out. Small local models can
get confused and answer "not available" when a factual question is tangled
up with instructions like "summarize" and "translate into Chinese" in the
same prompt, even though the fact is genuinely in the knowledge base. This
was observed as flaky/inconsistent behavior on identical repeated input.
"""
from __future__ import annotations
import re
from app.skills.base import SkillResult
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.summary import SummarySkill
from app.skills.translation import TranslationSkill, references_future_answer

SUMMARIZE_TRIGGERS = ["summarize", "summary", "brief", "总结"]
TRANSLATE_TRIGGERS = ["translate", "in chinese", "into chinese", "翻译"]

# Longer/more specific phrases first, so partial overlaps don't leave debris behind.
_STRIP_PHRASES = [
    "and translate it into chinese",
    "translate it into chinese",
    "and translate into chinese",
    "translate into chinese",
    "and translate to chinese",
    "translate to chinese",
    "into chinese",
    "in chinese",
    "to chinese",
    "and translate",
    "translate",
    "summarize",
    "summary",
    "brief",
    "总结并翻译成中文",
    "总结并翻译",
    "翻译成中文",
    "翻译",
    "总结",
]

# The knowledge skills this composition can pull facts from.
# Library/Course checked before Campus for the same reason as server.py's
# SKILLS ordering: Campus's remaining triggers are more generic.
KNOWLEDGE_SKILLS = [LibrarySkill(), CourseSkill(), CampusSkill()]


def _wants_summary(message: str) -> bool:
    lowered = message.lower()
    return any(t in lowered for t in SUMMARIZE_TRIGGERS)


def _wants_translation(message: str) -> bool:
    """Permissive: used INSIDE run() to decide whether to apply the
    translation step once composition has already been chosen."""
    lowered = message.lower()
    return any(t in lowered for t in TRANSLATE_TRIGGERS)


# "translate: <text>" (with a colon) is the user handing over a specific piece
# of text to transform, not asking a question about the knowledge base first.
# That belongs to the Translation skill alone. Note this is deliberately
# narrower than "starts with translate": "Translate the library address into
# Chinese" IS a knowledge question and must still compose.
_DIRECT_HANDOFF = re.compile(r"^\s*(translate|翻译)\s*[:：]", re.IGNORECASE)

# "Summarize: <text>" / "Summarize this article: <text>" — a colon shortly
# after the summarize cue means the user is handing over literal text to
# condense, not asking about the knowledge base — even when that text happens
# to mention a knowledge trigger word like "university". Mirrors the
# translate-handoff rules below; such messages belong to SummarySkill alone.
_SUMMARY_HANDOFF = re.compile(r"^\s*(summarize|summary|总结)[^:：]{0,30}[:：]", re.IGNORECASE)

# 'Translate "Welcome to Shenzhen University" into Chinese.' — the lab PDF's
# baseline question 5 and one of the web UI's suggestion buttons. A quoted
# span right after "translate" is LITERAL text being handed over, exactly
# like the colon form, even when the quoted text happens to contain a
# knowledge trigger word such as "university" (which campus.py matches).
# Covers straight ("), curly (“ ”), and single quotes.
_QUOTED_HANDOFF = re.compile(r"^\s*(translate|翻译)[^\"“”']{0,40}[\"“”']", re.IGNORECASE)


def _translation_requests_composition(message: str) -> bool:
    """Stricter: used in can_handle() to decide whether a translation cue is
    a reason to COMPOSE (answer from knowledge, then translate) rather than
    to translate text the user supplied directly.

    Excluded, because each belongs to a different skill:
      - "translate: <text>"        -> Translation (direct text handoff)
      - 'translate "<text>" ...'   -> Translation (quoted literal handoff)
      - "... answer in chinese"    -> knowledge skill answers in Chinese
      - "... translate it/that"    -> knowledge skill (pronoun, see translation.py)
    """
    if not _wants_translation(message):
        return False
    if _DIRECT_HANDOFF.match(message) or _QUOTED_HANDOFF.match(message):
        return False
    return not references_future_answer(message)


def _clean_knowledge_query(message: str) -> str:
    """Strip summarize/translate scaffolding so the knowledge skill sees a
    plain factual question instead of a tangled multi-instruction sentence."""
    cleaned = message
    for phrase in _STRIP_PHRASES:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    # Removing phrases mid-sentence leaves double spaces behind.
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;\"'")
    # If stripping left nothing usable, fall back to the original message
    # rather than sending an empty question to the knowledge skill.
    if len(cleaned) < 3:
        return message
    return _as_answerable_question(cleaned)


_INTERROGATIVE_STARTS = ("what", "where", "when", "who", "which", "how", "why", "list")


def _as_answerable_question(cleaned: str) -> str:
    """Stripping the scaffolding often leaves a noun fragment rather than a
    question — "Summarize the library info" cleans down to "the library info".
    Small local models answer a fragment with vague meta-commentary ("the
    library information is provided in the knowledge base") instead of the
    facts, so a fragment is reshaped into an explicit request for the facts.
    Real questions are left exactly as they are."""
    lowered = cleaned.lower()
    if "?" in cleaned or lowered.startswith(_INTERROGATIVE_STARTS):
        return cleaned
    return f"List all known facts about {cleaned}."


class ComposedBriefingSkill:
    name = "composed_briefing"

    def can_handle(self, message: str) -> bool:
        # Either transform alone is enough to need this skill, as long as the
        # message also asks about knowledge-base facts. Requiring BOTH used to
        # leave two gaps: "What are the courses in SZU? Translate to chinese"
        # fell through to Translation (which has no knowledge to translate) and
        # "Summarize the library info" fell through to Summary (which had no
        # knowledge either, and echoed the request back). Both now compose.
        if _SUMMARY_HANDOFF.match(message):
            # Literal text handed over for summarization — SummarySkill's job,
            # even if the text mentions knowledge trigger words.
            return False
        touches_knowledge = any(k.can_handle(message) for k in KNOWLEDGE_SKILLS)
        return touches_knowledge and (
            _wants_summary(message) or _translation_requests_composition(message)
        )

    def required_skills(self, message: str) -> "set[str]":
        """The Skills this composition will actually invoke for this message.

        Governance checks these instead of the composition's own name, so a
        role keeps exactly the access the permission table grants it. A member
        (campus/course/library/translation per the lab's role example) can ask
        a knowledge question and have the answer translated, because it uses
        only Skills that member already holds — while a Skill the role does
        not hold, such as summary, is still refused."""
        needed = set()
        knowledge_skill = next((k for k in KNOWLEDGE_SKILLS if k.can_handle(message)), None)
        if knowledge_skill is not None:
            needed.add(knowledge_skill.name)
        if _wants_summary(message):
            needed.add("summary")
        if _wants_translation(message):
            needed.add("translation")
        return needed or {self.name}

    def run(self, message: str, context: dict) -> SkillResult:
        # The chain is self-contained: every step receives its input as
        # explicit text, so session history adds nothing here — and passing
        # it through actively harms: a prior Q&A in context made the small
        # model blend the previous answer into the knowledge step (observed
        # live as "the library's two campuses are Yuehai and Lihu" after a
        # campuses question). Run every step with a clean, history-free
        # context.
        chain_context = {**context, "history": []}

        # Step 1: Knowledge Skill — get the underlying facts, using a cleaned
        # question so the model isn't confused by summarize/translate wording.
        knowledge_skill = next((k for k in KNOWLEDGE_SKILLS if k.can_handle(message)), None)
        if knowledge_skill is None:
            return SkillResult(
                text="No matching knowledge skill was found to brief on.",
                skill=self.name,
                status="unavailable",
            )
        knowledge_query = _clean_knowledge_query(message)
        knowledge_result = knowledge_skill.run(knowledge_query, chain_context)
        if knowledge_result.status != "success":
            return SkillResult(text=knowledge_result.text, skill=self.name, status=knowledge_result.status)

        # Steps 2 and 3 are applied only if the user actually asked for them,
        # so "<knowledge question> translate to chinese" is not forced through
        # a pointless summarization hop, and a summarize-only request is not
        # forced through translation.
        text = knowledge_result.text

        # Step 2: Summary Skill — condense the knowledge answer.
        # Pass the text directly, without prefixing literal "summarize:"
        # wording — the skill's own system prompt already tells the model
        # what to do, and embedding the trigger word here risks confusing
        # a small model in exactly the way the knowledge step did.
        # from_composition tells Summary the input is knowledge text, so its
        # short-text passthrough is safe to use here (see summary.py).
        if _wants_summary(message):
            step_context = {**chain_context, "from_composition": True}
            summary_result = SummarySkill().run(text, step_context)
            if summary_result.status != "success":
                return SkillResult(text=summary_result.text, skill=self.name, status=summary_result.status)
            text = summary_result.text

        # Step 3: Translation Skill — translate what we have, same reasoning.
        if _wants_translation(message):
            translation_result = TranslationSkill().run(text, chain_context)
            if translation_result.status != "success":
                return SkillResult(text=translation_result.text, skill=self.name, status=translation_result.status)
            text = translation_result.text

        return SkillResult(text=text, skill=self.name, status="success")

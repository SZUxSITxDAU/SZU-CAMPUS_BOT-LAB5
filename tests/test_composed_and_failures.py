import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime.orchestrator import handle_request
from app.skills.campus import CampusSkill
from app.skills.course import CourseSkill
from app.skills.library import LibrarySkill
from app.skills.translation import TranslationSkill
from app.skills.summary import SummarySkill
from app.skills.composed import ComposedBriefingSkill, _clean_knowledge_query
from tests.fakes import FakeLLMClient, EmptyLLMClient

SKILLS = [ComposedBriefingSkill(), TranslationSkill(), SummarySkill(), CourseSkill(), LibrarySkill(), CampusSkill()]


class TestComposedBriefing(unittest.TestCase):
    """Bonus 3: Knowledge -> Summary -> Translation composition."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_composed_chain_routes_and_succeeds(self):
        result = handle_request(
            "u1", "admin",
            "Summarize the library info and translate it into Chinese.",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "composed_briefing")
        self.assertEqual(result.status, "success")

    def test_plain_knowledge_question_not_misrouted_to_composed(self):
        result = handle_request("u1", "admin", "What is the motto?", SKILLS, self.llm)
        self.assertEqual(result.skill, "campus")

    def test_composed_chain_not_confused_by_scaffolding_words(self):
        """Regression: a small model that gets confused by literal
        'summarize'/'translate' wording appearing in its own prompt must
        still get a clean, unconfused question at each step of the chain.
        Observed in practice as flaky/inconsistent results on identical
        repeated input with the real local model."""

        class ConfusableLLM:
            def chat(self, system_prompt, user_prompt, history=None):
                lowered = user_prompt.lower()
                if "translate" in lowered or "summarize" in lowered:
                    return "That information is not available in the starter knowledge base."
                return "The libraries are located at No. 3688 Nanhai Avenue, Nanshan District, Shenzhen, China."

        result = handle_request(
            "u1", "admin",
            "Summarize the library info and translate it into Chinese.",
            SKILLS, ConfusableLLM(),
        )
        self.assertEqual(result.status, "success")
        self.assertNotIn("not available", result.response.lower())

    def test_composed_chain_uses_literal_skill_calls_with_few_shot_prompts(self):
        """The composed chain genuinely calls Knowledge -> Summary ->
        Translation skills in sequence (matching the PDF's Bonus 3 diagram
        literally). For already-short content, Summary passes through
        unchanged (see summary.py) rather than risking degradation, so this
        typically produces 2 real LLM calls (knowledge + translation), and
        the full content must survive intact into the final translation."""

        class TrackingLLM:
            def __init__(self):
                self.calls = []

            def chat(self, system_prompt, user_prompt, history=None):
                self.calls.append((system_prompt, user_prompt))
                if "translate" in system_prompt.lower():
                    return "深圳大学图书馆的地址是深圳市南山区南海大道3688号。"
                return (
                    "The main branches of Shenzhen University Library are the North "
                    "Library in Huidian Building, Yuehai Campus, the South Library in "
                    "Huizhi Building, Yuehai Campus, and the Central Library in Qiming "
                    "Building, Lihu Campus. The official address is No. 3688 Nanhai "
                    "Avenue, Nanshan District, Shenzhen, China."
                )

        llm = TrackingLLM()
        result = handle_request(
            "u1", "admin",
            "Summarize the library info and translate it into Chinese.",
            SKILLS, llm,
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(len(llm.calls), 2)  # knowledge + translation (summary passthrough)
        translation_input = llm.calls[-1][1]
        self.assertIn("Nanhai Avenue", translation_input)
        self.assertIn("Central Library", translation_input)
        # The translation system prompt should include the few-shot example.
        translation_system_prompt = llm.calls[-1][0]
        self.assertIn("Example:", translation_system_prompt)


class TestPartialComposition(unittest.TestCase):
    """Regression: a knowledge question that asks for only ONE transform
    (translate OR summarize, not both) must still reach the knowledge base.
    Composition used to require both trigger types, so these fell through to
    Translation/Summary, neither of which loads any knowledge."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_knowledge_plus_translate_only_composes(self):
        result = handle_request(
            "u1", "admin",
            "What are the courses in SZU? Translate to chinese",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "composed_briefing")
        self.assertEqual(result.status, "success")
        # FakeLLMClient returns Chinese only from the translation prompt, so
        # this also proves the translation step actually ran.
        self.assertEqual(result.response, "已翻译内容")

    def test_knowledge_plus_summarize_only_composes(self):
        result = handle_request("u1", "admin", "Summarize the library info", SKILLS, self.llm)
        self.assertEqual(result.skill, "composed_briefing")
        self.assertEqual(result.status, "success")

    def test_summarize_only_request_is_not_echoed_back(self):
        """The exact echo bug: the summary was the user's own request verbatim."""
        message = "Summarize the library info"
        result = handle_request("u1", "admin", message, SKILLS, self.llm)
        self.assertNotEqual(result.response.strip().lower(), message.lower())

    def test_translate_only_request_does_not_summarize(self):
        """A translate-only request must skip the summarization hop entirely."""
        calls = []

        class RecordingLLM(FakeLLMClient):
            def chat(self, system_prompt, user_prompt, history=None):
                calls.append(system_prompt)
                return super().chat(system_prompt, user_prompt, history=history)

        handle_request(
            "u1", "admin",
            "What are the courses in SZU? Translate to chinese",
            SKILLS, RecordingLLM(),
        )
        self.assertFalse(
            any("summarize" in prompt.lower() for prompt in calls),
            "translate-only request should not invoke the Summary skill",
        )

    def test_british_spelling_summarise_composes_and_translates(self):
        """Regression: 'Summarise' (British spelling) matched no trigger at
        all, so the whole request fell through to the plain library skill —
        which listed the facts in English and never translated. Both
        spellings must reach composition, and the translation step must run."""
        result = handle_request(
            "u1", "admin",
            "Summarise the library info and translate it into Chinese",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "composed_briefing")
        self.assertEqual(result.status, "success")
        # FakeLLMClient returns Chinese only from the translation prompt,
        # proving the translation step actually ran.
        self.assertEqual(result.response, "已翻译内容")

    def test_summarize_colon_handoff_is_not_hijacked_by_composition(self):
        """"Summarize: <pasted text>" hands over literal text to condense.
        It must reach SummarySkill directly, even when the pasted text
        mentions knowledge trigger words like 'university' — mirroring the
        translate: handoff rule."""
        result = handle_request(
            "u1", "admin",
            "Summarize: Shenzhen University was established in 1983 and has "
            "grown into a major comprehensive university with over 40,000 "
            "students across two campuses.",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "summary")
        self.assertEqual(result.status, "success")

    def test_chain_steps_run_without_session_history(self):
        """Regression: session history passed into the chain's internal steps
        made the model blend the PREVIOUS answer into the knowledge step
        (observed live: a campuses Q&A before 'Summarize the library info and
        translate it into Chinese.' produced 'the library's two campuses are
        Yuehai and Lihu'). Every step's input is explicit text, so the chain
        must run history-free regardless of what the session context holds."""
        seen_histories = []

        class HistoryRecordingLLM(FakeLLMClient):
            def chat(self, system_prompt, user_prompt, history=None):
                seen_histories.append(list(history or []))
                return super().chat(system_prompt, user_prompt, history=history)

        poisoned = [
            {"role": "user", "content": "What are the two campuses?"},
            {"role": "assistant", "content": "Yuehai Campus and Lihu Campus."},
        ]
        result = ComposedBriefingSkill().run(
            "Summarize the library info and translate it into Chinese.",
            context={"llm": HistoryRecordingLLM(), "history": poisoned},
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(seen_histories, "chain made no LLM calls")
        for h in seen_histories:
            self.assertEqual(h, [], "a chain step received session history")

    def test_fragment_query_is_reshaped_into_a_facts_request(self):
        """"Summarize the library info" cleans down to the fragment "the
        library info", which a small model answers with vague commentary
        instead of facts. Fragments must become an explicit facts request;
        real questions must be left untouched."""
        self.assertEqual(
            _clean_knowledge_query("Summarize the library info"),
            "List all known facts about the library info.",
        )
        self.assertEqual(
            _clean_knowledge_query("What are the courses in SZU? Translate to chinese"),
            "What are the courses in SZU?",
        )

    def test_summary_reached_directly_does_not_echo_input(self):
        """Without from_composition, Summary must not pass its input through."""
        result = SummarySkill().run(
            "Please condense this paragraph for me.",
            context={"llm": self.llm, "history": []},
        )
        self.assertNotEqual(result.text, "Please condense this paragraph for me.")


class TestFailurePaths(unittest.TestCase):
    """Task 1 requirement: predictable failure/unavailable behavior per skill."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_translation_with_no_content_is_unavailable(self):
        result = handle_request("u1", "admin", "translate", SKILLS, self.llm)
        self.assertEqual(result.status, "unavailable")

    def test_summary_with_too_little_content_is_unavailable(self):
        result = handle_request("u1", "admin", "summarize: hi", SKILLS, self.llm)
        self.assertEqual(result.status, "unavailable")

    def test_translation_empty_model_response_is_error(self):
        result = handle_request("u1", "admin", "translate: hello there", SKILLS, EmptyLLMClient())
        self.assertEqual(result.status, "error")


class TestRoutingRegression(unittest.TestCase):
    """Regression test: a translate request containing 'university' must not
    be misrouted to the campus skill just because campus also matches that word."""

    def setUp(self):
        self.llm = FakeLLMClient()

    def test_translate_with_university_keyword_routes_to_translation(self):
        result = handle_request(
            "u1", "admin",
            "translate: Welcome to Shenzhen University",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "translation")
        self.assertEqual(result.status, "success")

    def test_lab_baseline_quoted_translate_routes_to_translation(self):
        """Lab PDF Part A Step 3, question 5 — also a web UI suggestion
        button. The quoted text contains 'university' (a campus trigger),
        so composition must recognize the quoted span as a literal text
        handoff and leave this to the Translation skill."""
        result = handle_request(
            "u1", "member",
            'Translate "Welcome to Shenzhen University" into Chinese.',
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "translation")
        self.assertEqual(result.status, "success")

    def test_curly_quoted_translate_routes_to_translation(self):
        """Same as above but with the curly quotes the web UI button
        actually sends (index.html uses “ ”, not straight quotes)."""
        result = handle_request(
            "u1", "member",
            "Translate “Welcome to Shenzhen University” into Chinese.",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "translation")
        self.assertEqual(result.status, "success")

    def test_answer_in_chinese_phrase_routes_to_knowledge_not_translation(self):
        """Regression: 'answer in Chinese' tacked onto a real question must
        route to the knowledge skill (which then answers IN Chinese), not
        to Translation (which would just translate the question text
        itself back to the user instead of answering it)."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library? answer in chinese",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_translate_the_answer_phrase_routes_to_knowledge_not_translation(self):
        """Regression: this is worse than the 'answer in chinese' case —
        Translation has NO knowledge base access, so if it grabs a real
        question like this, it hallucinates a plausible-looking but
        completely fabricated answer instead of erroring or refusing.
        'translate the answer' must be recognized as referring to a
        FUTURE answer, not text given directly to translate right now."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library? translate the answer to chinese",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_translate_it_pronoun_in_same_message_routes_to_knowledge(self):
        """Regression: 'translate it' with no separate text given (all in
        one message, e.g. 'What are the branches? and can u translate it
        into chinese') has nothing for 'it' to refer to except the answer
        about to be given — must route to the knowledge skill, not
        Translation. Also covers a real observed typo ('chines')."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library? and can u translate it into chines",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_library_question_mentioning_university_routes_to_library(self):
        """A library question that happens to contain 'university' (e.g. because
        it says 'Shenzhen University Library') must route to library, not campus."""
        result = handle_request(
            "u1", "admin",
            "What are the main branches of Shenzhen University Library?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "library")

    def test_course_question_mentioning_university_routes_to_course(self):
        result = handle_request(
            "u1", "admin",
            "What courses does Shenzhen University offer?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "course")

    def test_missing_knowledge_question_with_university_reaches_campus_fallback(self):
        """The PDF's baseline test expects 'Who is the current president of
        Shenzhen University?' to reach Campus's 'not available' fallback, not
        go unmatched. 'university' must still route here when nothing more
        specific (library/course/translate/summarize) also matches."""
        result = handle_request(
            "u1", "admin",
            "Who is the current president of Shenzhen University?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "campus")

    def test_international_office_question_reaches_campus_fallback(self):
        """The PDF's other baseline missing-knowledge question has no
        'university' in it at all, so campus needs an explicit trigger
        for this exact phrase."""
        result = handle_request(
            "u1", "admin",
            "Where is the International Office?",
            SKILLS, self.llm,
        )
        self.assertEqual(result.skill, "campus")


if __name__ == "__main__":
    unittest.main()

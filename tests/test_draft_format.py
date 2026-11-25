"""Gemini output quirks: list-valued fields and numbers written as words."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsletter import checks, pipeline  # noqa: E402
from newsletter.card import _bullets  # noqa: E402

SHEET = {"id": 1, "facts": [{"fact": "Claude Code is used by 55% of developers.",
                             "evidence": "Claude Code is used by 55% of developers in the survey"}]}


class DraftFormatTests(unittest.TestCase):
    def test_list_text_becomes_clean_bullets_without_brackets(self):
        post = {"stories": [{"story_id": 1, "text": ["First fact here.", "Second fact here."]}]}
        text = pipeline.normalise_draft(post)["stories"][0]["text"]
        self.assertIsInstance(text, str)
        bullets = _bullets(text)
        self.assertEqual(bullets, "- First fact here.\n- Second fact here.")
        self.assertNotIn("[", bullets)
        self.assertNotIn("'", bullets)

    def test_spelled_out_number_is_rejected(self):
        post = {"headline": "h", "question": "q", "stories": [
            {"story_id": 1, "title": "t", "why_it_matters": "w",
             "text": "Claude Code is used by fifty-five percent of developers."}]}
        problems = checks.code_problems(post, [SHEET])
        self.assertTrue(any("as digits" in p for p in problems), problems)

    def test_digits_matching_facts_pass(self):
        post = {"headline": "h", "question": "q", "stories": [
            {"story_id": 1, "title": "t", "why_it_matters": "w",
             "text": "Claude Code is used by 55% of developers."}]}
        self.assertEqual(checks.code_problems(post, [SHEET]), [])

    def test_plural_number_words_are_allowed(self):
        post = {"headline": "h", "question": "q", "stories": [
            {"story_id": 1, "title": "t", "why_it_matters": "w",
             "text": "Thousands of developers use Claude Code."}]}
        self.assertEqual(checks.code_problems(post, [SHEET]), [])

    def test_digit_plus_million_is_allowed(self):
        sheet = {"id": 1, "facts": [{"fact": "Intentful saved 1 million hours and $2.5 billion.",
                                     "evidence": "Intentful saved 1 million hours and $2.5 billion in costs"}]}
        post = {"headline": "h", "question": "q", "stories": [
            {"story_id": 1, "title": "t", "why_it_matters": "w",
             "text": "Intentful saved 1 million hours and $2.5 billion."}]}
        self.assertEqual(checks.code_problems(post, [sheet]), [])

    def test_bare_million_word_is_rejected(self):
        post = {"headline": "h", "question": "q", "stories": [
            {"story_id": 1, "title": "t", "why_it_matters": "w",
             "text": "Intentful saved one million hours."}]}
        self.assertTrue(any("as digits" in p for p in checks.code_problems(post, [SHEET])))


if __name__ == "__main__":
    unittest.main()

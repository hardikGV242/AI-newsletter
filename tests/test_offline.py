"""Offline tests. No internet, no AI key, no Teams needed.

Run from the project folder:   python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from newsletter import card, checks, feeds, pipeline, state, teams, util  # noqa: E402

ARTICLE_AI = (
    "Acme AI released the Orbit model on 12 March 2027 for all paid plans. "
    "The company says Orbit answers questions 30% faster than its previous model. "
    "It is available through the web app and the API. "
    "A free tier is planned for later this year. "
    "Developers can read the documentation to get started and try it in a few minutes."
)
ARTICLE_SF = (
    "Salesforce announced that the Forecast Helper agent is generally available in "
    "Enterprise Edition and above starting 5 April 2027. Admins can turn it on in Setup. "
    "In early tests, customers reduced forecast prep time by 25%. "
    "Pricing details will be shared by account teams. "
    "The release is part of a wider set of updates for sales teams this season."
)
FACTS_AI = [
    {"id": "f1", "fact": "Acme AI released the Orbit model on 12 March 2027.",
     "evidence": "Acme AI released the Orbit model on 12 March 2027 for all paid plans."},
    {"id": "f2", "fact": "Acme AI says Orbit answers questions 30% faster than its previous model.",
     "evidence": "Orbit answers questions 30% faster than its previous model."},
    {"id": "f3", "fact": "Orbit is available in the web app and through the API.",
     "evidence": "It is available through the web app and the API."},
    {"id": "f4", "fact": "A free tier is planned for later this year and is not available yet.",
     "evidence": "A free tier is planned for later this year."},
]
FACTS_SF = [
    {"id": "f1", "fact": "The Forecast Helper agent is generally available in Enterprise Edition and above from 5 April 2027.",
     "evidence": "the Forecast Helper agent is generally available in Enterprise Edition and above starting 5 April 2027"},
    {"id": "f2", "fact": "Admins can turn it on in Setup.",
     "evidence": "Admins can turn it on in Setup."},
    {"id": "f3", "fact": "In early tests, customers reduced forecast prep time by 25%.",
     "evidence": "In early tests, customers reduced forecast prep time by 25%."},
    {"id": "f4", "fact": "Pricing details will be shared by account teams.",
     "evidence": "Pricing details will be shared by account teams."},
]
AI_ITEM = {"title": "Acme AI launches Orbit", "url": "https://example.com/ai/orbit",
           "published": "2026-11-30T01:00:00+00:00", "source": "Example AI Blog",
           "category": "ai", "tier": 1, "summary": "s", "feed_text": ARTICLE_AI}
SF_ITEM = {"title": "Forecast Helper agent is generally available",
           "url": "https://example.com/sf/forecast",
           "published": "2026-11-30T01:00:00+00:00", "source": "Example SF News",
           "category": "salesforce", "tier": 1, "summary": "s", "feed_text": ARTICLE_SF}


def make_sheets():
    out = []
    for i, (item, facts, article) in enumerate(
            [(AI_ITEM, FACTS_AI, ARTICLE_AI), (SF_ITEM, FACTS_SF, ARTICLE_SF)], 1):
        kept, dropped = checks.verify_facts(facts, article)
        assert not dropped, dropped
        out.append({"id": i, "category": item["category"], "title": item["title"],
                    "url": item["url"], "source": item["source"], "facts": kept,
                    "availability": "unknown", "dropped": []})
    return out


class FakeLLM:
    """Stands in for the AI service with fixed, predictable answers."""

    def __init__(self, wrong_number=False, claims_pass=True):
        self.wrong_number = wrong_number
        self.claims_pass = claims_pass

    def draft(self, friday):
        pct = "40%" if self.wrong_number else "30%"
        post = {
            "headline": "Two launches worth a quick look",
            "stories": [
                {"story_id": 1, "title": "A new AI model arrives",
                 "text": ("Acme AI released a new model called Orbit on 12 March 2027 for all paid plans. "
                          f"The company says it answers questions {pct} faster than its previous model. "
                          "You can use it in the web app and through the API. A free tier is planned "
                          "for later this year, but it is not available yet."),
                 "why_it_matters": "Faster answers could save you a few minutes every day."},
                {"story_id": 2, "title": "Forecast Helper is here for sales teams",
                 "text": ("Salesforce says the Forecast Helper agent is generally available in Enterprise "
                          "Edition and above starting 5 April 2027. Admins can turn it on in Setup. "
                          "In early tests, customers reduced forecast prep time by 25%. "
                          "Pricing details will be shared by account teams."),
                 "why_it_matters": "Admins may want to look at Setup before the sales team asks."},
            ],
            "jargon": {"term": "API", "explanation": "A way for one program to talk to another program."},
            "question": "Which of today's stories are you most curious about?",
            "quiz": [],
        }
        if friday:
            post["quiz"] = [
                {"q": "Which model did Acme AI release?", "options": ["Orbit", "Comet", "Nova"], "answer": 0},
                {"q": "Where can the Forecast Helper be turned on?", "options": ["In Setup", "In Slack", "In email"], "answer": 0},
                {"q": "Is the Orbit free tier available yet?", "options": ["Yes", "No, it is planned", "Only on weekends"], "answer": 1},
            ]
        return post

    def complete_json(self, system, user, max_tokens=2500):
        if "choosing the best story" in user:
            ids = re.findall(r'"id": (\d+),\s+"title"', user)
            return {"ranking": [{"id": int(i), "score": 8, "reason": "ok"} for i in ids]}
        if "Read the article below" in user:
            if "Acme AI launches Orbit" in user:
                return {"facts": FACTS_AI, "availability": "available"}
            return {"facts": FACTS_SF, "availability": "generally available"}
        if "writing today's 3-minute Teams digest" in user:
            return self.draft("TODAY IS FRIDAY" in user)
        if "checking a draft" in user:
            if self.claims_pass:
                return {"verdict": "pass", "problems": []}
            return {"verdict": "fail", "problems": ["claims are not supported"]}
        raise AssertionError("unexpected prompt")


def fake_collect(_sources, _max_age, _now):
    return [dict(AI_ITEM), dict(SF_ITEM)], []


def fake_fetch(item, _max_chars, min_chars=600):
    return item["feed_text"]


class ChecksTests(unittest.TestCase):
    def test_made_up_evidence_is_dropped(self):
        facts = FACTS_AI + [{"id": "f9", "fact": "Orbit is free forever.",
                             "evidence": "Orbit will always be completely free for everyone."}]
        kept, dropped = checks.verify_facts(facts, ARTICLE_AI)
        self.assertEqual(len(kept), 4)
        self.assertEqual(len(dropped), 1)

    def test_number_not_in_its_evidence_is_dropped(self):
        facts = [{"id": "f1", "fact": "Orbit is 50% faster.",
                  "evidence": "Orbit answers questions 30% faster than its previous model."}]
        kept, dropped = checks.verify_facts(facts, ARTICLE_AI)
        self.assertEqual(kept, [])
        self.assertIn("50", dropped[0])

    def test_clean_post_passes_every_code_check(self):
        sheets = make_sheets()
        post = FakeLLM().draft(friday=True)
        self.assertEqual(checks.shape_problems(post, sheets, friday=True), [])
        self.assertEqual(checks.code_problems(post, sheets), [])

    def test_changed_number_is_caught(self):
        sheets = make_sheets()
        post = FakeLLM(wrong_number=True).draft(friday=False)
        problems = checks.code_problems(post, sheets)
        self.assertTrue(any("40" in p for p in problems), problems)

    def test_number_from_the_other_story_is_caught(self):
        sheets = make_sheets()
        post = FakeLLM().draft(friday=False)
        post["stories"][0]["text"] += " It also cut prep time by 25%."
        self.assertTrue(checks.code_problems(post, sheets))

    def test_invented_quote_and_link_are_caught(self):
        sheets = make_sheets()
        post = FakeLLM().draft(friday=False)
        post["stories"][0]["text"] += ' The CEO said "this changes everything for every team".'
        post["stories"][1]["text"] += " Read more at https://example.com/x"
        problems = " ".join(checks.code_problems(post, sheets))
        self.assertIn("quoted phrase", problems)
        self.assertIn("link", problems)

    def test_quiz_only_allowed_on_friday(self):
        sheets = make_sheets()
        post = FakeLLM().draft(friday=True)
        self.assertTrue(checks.shape_problems(post, sheets, friday=False))
        post["quiz"] = []
        self.assertTrue(checks.shape_problems(post, sheets, friday=True))


class FeedTests(unittest.TestCase):
    SOURCE = {"name": "Test", "category": "ai", "tier": 1}

    def test_rss(self):
        xml = (b'<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
               b'<title>T</title><item><title>Hello &amp; welcome</title><link>https://example.com/a</link>'
               b'<pubDate>Mon, 30 Nov 2026 03:00:00 GMT</pubDate>'
               b'<description>&lt;p&gt;Short summary&lt;/p&gt;</description>'
               b'<content:encoded><![CDATA[<p>Full body text</p>]]></content:encoded></item></channel></rss>')
        items = feeds.parse_feed(xml, self.SOURCE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hello & welcome")
        self.assertEqual(items[0]["summary"], "Short summary")
        self.assertEqual(items[0]["feed_text"], "Full body text")

    def test_atom(self):
        xml = (b'<feed xmlns="http://www.w3.org/2005/Atom"><title>T</title><entry><title>Atom story</title>'
               b'<link rel="alternate" href="https://example.com/b"/>'
               b'<updated>2026-11-30T03:00:00Z</updated><summary>Sum</summary></entry></feed>')
        items = feeds.parse_feed(xml, self.SOURCE)
        self.assertEqual(items[0]["url"], "https://example.com/b")

    def test_entity_definitions_are_refused(self):
        xml = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x "y">]><rss><channel></channel></rss>'
        with self.assertRaises(ValueError):
            feeds.parse_feed(xml, self.SOURCE)

    def test_html_to_text_skips_menus_and_scripts(self):
        page = ("<html><nav>Menu menu menu menu menu menu</nav><script>var a = 1;</script>"
                "<article><p>This is a real paragraph with enough words in it.</p></article></html>")
        text = feeds.html_to_text(page, 5000)
        self.assertIn("real paragraph", text)
        self.assertNotIn("Menu", text)
        self.assertNotIn("var a", text)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = util.load_json(ROOT / "config.json")
        self.tmp = tempfile.TemporaryDirectory()
        self.sent = []
        self.alerts = []
        patches = [
            mock.patch.object(feeds, "collect", fake_collect),
            mock.patch.object(feeds, "fetch_article", fake_fetch),
            mock.patch.object(teams, "post_card", lambda url, msg: self.sent.append(msg) or 200),
            mock.patch.dict(os.environ, {"TEAMS_WEBHOOK_URL": "https://example.invalid/hook"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def go(self, llm, when, **kw):
        return pipeline.run(self.cfg, llm, now=when, state_dir=self.tmp.name,
                            log=lambda *a: None, alert=self.alerts.append, **kw)

    def history(self):
        return state.load(str(Path(self.tmp.name) / "history.json"))["posts"]

    def test_normal_day_posts_a_checked_story_post(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        outcome = self.go(FakeLLM(), monday)
        self.assertEqual(outcome["kind"], "story")
        self.assertEqual(len(self.sent), 1)
        text = json.dumps(self.sent[0])
        self.assertIn("Orbit", text)
        self.assertIn("https://example.com/sf/forecast", text)  # source link added by code
        self.assertLess(len(text.encode()), 27 * 1024)
        self.assertEqual(self.history()[0]["kind"], "story")
        self.assertTrue((Path(self.tmp.name) / "runs" / "2026-11-30.json").exists())
        self.assertEqual(self.alerts, [])

    def test_never_posts_twice_in_one_day(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        self.go(FakeLLM(), monday)
        self.go(FakeLLM(), monday)
        self.assertEqual(len(self.sent), 1)

    def test_weekend_is_skipped(self):
        saturday = datetime(2026, 12, 5, 4, 0, tzinfo=timezone.utc)
        self.assertIsNone(self.go(FakeLLM(), saturday))
        self.assertEqual(self.sent, [])

    def test_wrong_number_means_backup_post(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        outcome = self.go(FakeLLM(wrong_number=True), monday)
        self.assertEqual(outcome["kind"], "backup")
        self.assertNotIn("40%", json.dumps(self.sent[0]))
        self.assertEqual(len(self.alerts), 1)

    def test_failed_claim_check_means_backup_post(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        outcome = self.go(FakeLLM(claims_pass=False), monday)
        self.assertEqual(outcome["kind"], "backup")

    def test_no_stories_at_all_means_backup_post(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        with mock.patch.object(feeds, "collect", lambda *a: ([], ["feed down"])):
            outcome = self.go(FakeLLM(), monday)
        self.assertEqual(outcome["kind"], "backup")
        self.assertEqual(len(self.sent), 1)

    def test_friday_quiz_then_answers_on_monday(self):
        friday = datetime(2026, 12, 4, 4, 0, tzinfo=timezone.utc)
        self.go(FakeLLM(), friday)
        self.assertIn("Reveal Answers", json.dumps(self.sent[0]))
        self.assertEqual(len(self.history()[0]["quiz"]), 3)
        monday = datetime(2026, 12, 7, 4, 0, tzinfo=timezone.utc)
        self.go(FakeLLM(), monday)
        self.assertNotIn("Reveal Answers", json.dumps(self.sent[1]))
        self.assertTrue(self.history()[0]["quiz_revealed"])

    def test_same_story_is_not_repeated(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        tuesday = datetime(2026, 12, 1, 4, 0, tzinfo=timezone.utc)
        self.go(FakeLLM(), monday)
        outcome = self.go(FakeLLM(), tuesday)
        self.assertEqual(outcome["kind"], "backup")

    def test_dry_run_posts_and_saves_nothing(self):
        monday = datetime(2026, 11, 30, 4, 0, tzinfo=timezone.utc)
        self.go(FakeLLM(), monday, dry_run=True)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.history(), [])


class ConfigTests(unittest.TestCase):
    def test_every_backup_post_builds_a_valid_card(self):
        cfg = util.load_json(ROOT / "config.json")
        for backup in util.load_json(ROOT / "backup_posts.json"):
            message = card.build(cfg, cfg["themes"]["0"], {"kind": "backup", "backup": backup},
                                 None, "Mon 30 Nov 2026")
            self.assertLess(len(json.dumps(message).encode()), 27 * 1024)
            self.assertNotIn("http", backup["body"])

    def test_config_and_sources_are_valid(self):
        cfg = util.load_json(ROOT / "config.json")
        self.assertEqual(sorted(cfg["themes"]), ["0", "1", "2", "3", "4"])
        sources = util.load_json(ROOT / "sources.json")
        self.assertTrue({"ai", "salesforce"} <= {s["category"] for s in sources})

    def test_all_prompt_files_exist_and_have_no_unfilled_markers_after_fill(self):
        for name in ("select.md", "facts.md", "write.md", "claims.md", "style_guide.md"):
            self.assertTrue((ROOT / "prompts" / name).read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()

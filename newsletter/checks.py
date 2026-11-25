"""Automatic safety checks. These replace the human editor.

Chain of trust:
  article  ->  fact sheet   : every fact must carry a quote that really is in the article
  fact sheet -> post        : numbers, quotes and links in the post must come from the facts
  post -> AI claim check    : a second AI read-through (done in pipeline.py)
"""
import re

from . import util

QUOTED = re.compile(r'"([^"]{4,})"')


# ---------- article -> fact sheet ----------

def verify_facts(facts, article_text):
    """Keep only facts whose evidence quote is found in the article.

    Also drops a fact if its sentence uses a strong number that its own
    evidence does not contain. Returns (kept, dropped_descriptions).
    """
    haystack = util.norm_text(article_text)
    kept, dropped = [], []
    for fact in facts or []:
        fact_text = str(fact.get("fact", "")).strip()
        evidence = str(fact.get("evidence", "")).strip()
        if not fact_text or len(evidence) < 15:
            dropped.append(f"{fact.get('id', '?')}: missing text or evidence")
            continue
        if util.norm_text(evidence) not in haystack:
            dropped.append(f"{fact.get('id', '?')}: evidence not found in article")
            continue
        evidence_numbers = {n for n, _ in util.number_tokens(evidence)}
        bad = [n for n, strong in util.number_tokens(fact_text)
               if strong and n not in evidence_numbers]
        if bad:
            dropped.append(f"{fact.get('id', '?')}: number {bad[0]} not in its evidence")
            continue
        kept.append({"id": str(fact.get("id", f"f{len(kept) + 1}")),
                     "fact": fact_text, "evidence": evidence})
    return kept, dropped


# ---------- fact sheet -> post ----------

def sheet_numbers(sheet):
    out = set()
    for fact in sheet["facts"]:
        out |= {n for n, _ in util.number_tokens(fact["fact"] + " " + fact["evidence"])}
    return out


def sheet_corpus(sheet):
    return util.norm_text(" ".join(f["fact"] + " " + f["evidence"] for f in sheet["facts"]))


# Numbers written as words ("fifty-five percent", "two thousand twenty-six") would
# slip past the digit check above, so they are not allowed. Plurals such as
# "thousands of" are fine because they are not exact numbers.
# "1 million" / "$2.5 billion" (a digit before the scale word) is normal and allowed.
SPELLED_NUMBER = re.compile(
    r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\b"
    r"|(?<![\d.,]\s)(?<![\d.,])\b(million|billion|trillion)\b", re.I)


def _text_problems(text, where, allowed_numbers, corpus):
    problems = []
    spelled = SPELLED_NUMBER.search(text or "")
    if spelled:
        problems.append(f"{where}: write numbers as digits exactly as in the facts "
                        f"(found '{spelled.group(0)}')")
    for number, strong in util.number_tokens(text):
        if strong and number not in allowed_numbers:
            problems.append(f"{where}: the number {number} is not in the source facts")
    for span in QUOTED.findall(util.norm_text(text)):
        if len(span.split()) >= 3 and span not in corpus:
            problems.append(f"{where}: a quoted phrase is not in the source facts")
    if re.search(r"https?://|www\.", text, re.I):
        problems.append(f"{where}: contains a web link (links are added automatically)")
    return problems


def shape_problems(post, sheets, friday):
    """Is the draft complete and the right size?"""
    problems = []
    if not isinstance(post, dict):
        return ["draft is not a JSON object"]
    for key in ("headline", "stories", "question"):
        if not post.get(key):
            problems.append(f"missing '{key}'")
    stories = post.get("stories") or []
    wanted = {s["id"] for s in sheets}
    got = [s.get("story_id") for s in stories if isinstance(s, dict)]
    if sorted(got) != sorted(wanted):
        problems.append("each story must appear exactly once, with its story_id")
    words = 0
    for story in stories:
        if not isinstance(story, dict):
            continue
        for key in ("title", "text", "why_it_matters"):
            if not str(story.get(key, "")).strip():
                problems.append(f"a story is missing '{key}'")
        count = len(str(story.get("text", "")).split())
        words += count + len(str(story.get("why_it_matters", "")).split())
        if count < 15 or count > 70:
            problems.append(f"a story text has {count} words (should be 20 to 55)")
        if len(str(story.get("why_it_matters", "")).split()) > 45:
            problems.append("a Client Impact line is too long (one sentence)")
    if words > 350:
        problems.append("the post is too long")
    quiz = post.get("quiz") or []
    if friday:
        if not (2 <= len(quiz) <= 3):
            problems.append("Friday needs a quiz of 2 or 3 questions")
        for i, item in enumerate(quiz, 1):
            options = item.get("options") if isinstance(item, dict) else None
            answer = item.get("answer") if isinstance(item, dict) else None
            if (not item.get("q") or not isinstance(options, list)
                    or not 3 <= len(options) <= 4
                    or not isinstance(answer, int) or not 0 <= answer < len(options)):
                problems.append(f"quiz question {i} is not valid")
    elif quiz:
        problems.append("only Friday posts may have a quiz")
    return problems


def code_problems(post, sheets, extra_sheets=()):
    """Numbers, quotes and links in the draft must come from the fact sheets."""
    problems = []
    all_sheets = list(sheets) + list(extra_sheets)
    union_numbers, union_corpus = set(), ""
    for sheet in all_sheets:
        union_numbers |= sheet_numbers(sheet)
        union_corpus += " " + sheet_corpus(sheet)

    by_id = {s["id"]: s for s in sheets}
    for story in post.get("stories", []):
        sheet = by_id.get(story.get("story_id"))
        if not sheet:
            problems.append("a story points to an unknown story_id")
            continue
        allowed, corpus = sheet_numbers(sheet), sheet_corpus(sheet)
        for key in ("tag", "title", "text", "why_it_matters"):
            problems += _text_problems(str(story.get(key, "")), f"story {sheet['id']} {key}",
                                       allowed, corpus)

    problems += _text_problems(str(post.get("headline", "")), "headline",
                               union_numbers, union_corpus)
    jargon = post.get("jargon") or {}
    problems += _text_problems(f"{jargon.get('term', '')} {jargon.get('explanation', '')}",
                               "jargon", union_numbers, union_corpus)
    problems += _text_problems(str(post.get("question", "")), "question",
                               union_numbers, union_corpus)
    for i, item in enumerate(post.get("quiz") or [], 1):
        text = " ".join([str(item.get("q", ""))] + [str(o) for o in item.get("options", [])])
        problems += _text_problems(text, f"quiz {i}", union_numbers, union_corpus)
    return problems

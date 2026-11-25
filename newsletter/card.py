"""Builds the Teams message (an Adaptive Card) in the "SF & AI Daily Pulse" layout.

Per story: [TAG] headline, a 1-2 sentence summary, a Client Impact line and a
"Read on <source>" button. Friday adds a quiz with a "Reveal Answers" button.
"""

import re

LETTERS = "ABCD"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
# A bullet the AI may have written itself: "- ", "* ", "• ", "▪ ", "1. ", "2) "
_MARKER = re.compile(r"^(?:\s*(?:[-*•▪◦‣⁃]|\d+[.)])\s+)+")


def _bullets(text):
    """Turn the story text into a Markdown bullet list, one sentence per bullet.

    Works whether the AI sent a paragraph or its own list: existing bullet
    markers are removed first so Teams never shows a bullet inside a bullet.
    """
    parts = []
    for line in str(text).splitlines():
        line = _MARKER.sub("", line).strip()
        parts += [p.strip() for p in _SENTENCE_END.split(line) if p.strip()]
    return "\n".join(f"- {p}" for p in parts)


def _tb(text, **extra):
    block = {"type": "TextBlock", "text": text, "wrap": True}
    block.update(extra)
    return block


def _container(items, **extra):
    block = {"type": "Container", "separator": True, "spacing": "Medium", "items": items}
    block.update(extra)
    return block


def _story(story, sheet):
    tag = (story.get("tag") or ("AI RADAR" if sheet["category"] == "ai" else "SALESFORCE")).upper()
    color = "Good" if sheet["category"] == "ai" else "Accent"
    return _container([
        _tb(f"[{tag}] {story['title']}", weight="Bolder", color=color),
        _tb(_bullets(story["text"]), spacing="Small"),
        _tb(f"**Client Impact:** {story['why_it_matters']}", spacing="Small", isSubtle=True),
        {"type": "ActionSet", "spacing": "Small", "actions": [
            {"type": "Action.OpenUrl", "title": f"Read on {sheet['source']}", "url": sheet["url"]},
        ]},
    ])


def _quiz(quiz):
    items = [_tb("\U0001f3af Friday 60-Second Knowledge Check", weight="Bolder", color="Attention")]
    for i, item in enumerate(quiz, 1):
        options = "\n".join(f"{letter}) {opt}" for letter, opt in zip(LETTERS, item["options"]))
        items.append(_tb(f"**Q{i}. {item['q']}**\n\n{options}", spacing="Small"))
    answers = "\n\n".join(
        f"**Q{i}:** {LETTERS[item['answer']]}) {item['options'][item['answer']]}"
        for i, item in enumerate(quiz, 1))
    items.append({"type": "ActionSet", "actions": [{
        "type": "Action.ShowCard", "title": "Reveal Answers",
        "card": {"type": "AdaptiveCard", "body": [_tb(answers)]},
    }]})
    return _container(items)


def build(cfg, theme, outcome, reveal, date_label):
    # theme and reveal are kept for compatibility. Friday answers now sit in the
    # same post behind "Reveal Answers", so no separate reveal is shown later.
    body = [
        _tb(cfg.get("newsletter_name", "⚡ SF & AI Daily Pulse"), size="Large", weight="Bolder"),
        _tb(f"{date_label} • {cfg.get('subtitle', 'Curated by Gemini for our Salesforce Team')}",
            isSubtle=True, spacing="None"),
    ]

    if outcome["kind"] == "story":
        post = outcome["post"]
        sheets = {s["id"]: s for s in outcome["sheets"]}
        for story in post["stories"]:
            body.append(_story(story, sheets[story["story_id"]]))
        if post.get("quiz"):
            body.append(_quiz(post["quiz"]))
        question = post["question"]
    else:
        backup = outcome["backup"]
        body.append(_container([
            _tb(f"[{backup['label'].upper()}] {backup['headline']}", weight="Bolder", color="Accent"),
            _tb(backup["body"], spacing="Small"),
        ]))
        question = backup["question"]

    body.append(_container([_tb(f"\U0001f4ac {question}", weight="Bolder")], style="emphasis"))

    if cfg.get("feedback_link"):
        body.append({"type": "ActionSet", "actions": [{
            "type": "Action.OpenUrl", "title": "Submit Team Tip / POC Feedback",
            "url": cfg["feedback_link"]}]})

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
            },
        }],
    }

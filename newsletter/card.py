"""Builds the Teams message (an Adaptive Card) from the finished post."""

LETTERS = "ABCD"


def _tb(text, **extra):
    block = {"type": "TextBlock", "text": text, "wrap": True}
    block.update(extra)
    return block


def build(cfg, theme, outcome, reveal, date_label):
    body = [_tb(f"{cfg['newsletter_name']} · {theme['name']} · {date_label}",
                size="Small", isSubtle=True)]

    if outcome["kind"] == "story":
        post = outcome["post"]
        sheets = {s["id"]: s for s in outcome["sheets"]}
        body.append(_tb(post["headline"], size="Large", weight="Bolder", spacing="Small"))
        for story in post["stories"]:
            sheet = sheets[story["story_id"]]
            label = "\U0001f916 AI" if sheet["category"] == "ai" else "☁️ Salesforce"
            body.append(_tb(label, weight="Bolder", color="Accent", spacing="Medium"))
            body.append(_tb(f"**{story['title']}**", spacing="Small"))
            body.append(_tb(story["text"], spacing="Small"))
            body.append(_tb(f"\U0001f4a1 *Why it matters for us:* {story['why_it_matters']}",
                            spacing="Small"))
            body.append(_tb(f"Source: [{sheet['source']}]({sheet['url']})",
                            size="Small", isSubtle=True, spacing="Small"))
        jargon = post["jargon"]
        body.append(_tb(f"\U0001f4d6 **Jargon Buster: {jargon['term']}**. {jargon['explanation']}",
                        spacing="Medium"))
        if post.get("quiz"):
            body.append(_tb("\U0001f9e0 **Friday Quiz**", spacing="Medium"))
            for i, item in enumerate(post["quiz"], 1):
                body.append(_tb(f"**{i}. {item['q']}**", spacing="Small"))
                for letter, option in zip(LETTERS, item["options"]):
                    body.append(_tb(f"{letter}. {option}", spacing="None"))
        body.append(_tb(f"\U0001f4ac **{post['question']}**", spacing="Medium"))
    else:
        backup = outcome["backup"]
        body.append(_tb(backup["headline"], size="Large", weight="Bolder", spacing="Small"))
        body.append(_tb(f"**{backup['label']}**", color="Accent", spacing="Medium"))
        body.append(_tb(backup["body"], spacing="Small"))
        body.append(_tb(f"\U0001f4ac **{backup['question']}**", spacing="Medium"))

    if reveal:
        lines = ["✅ **Last Friday's quiz answers**"]
        for i, item in enumerate(reveal["quiz"], 1):
            lines.append(f"{i}. {LETTERS[item['answer']]}. {item['options'][item['answer']]}")
        body.append(_tb("\n\n".join(lines), spacing="Medium"))

    body.append(_tb(
        "React: \U0001f44d learned something · \U0001f4a1 will try it · "
        "\U0001f914 want more. Written by AI from the linked sources. "
        "Spot a mistake? Reply in the thread.",
        size="Small", isSubtle=True, spacing="Medium"))

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.2",
                "msteams": {"width": "Full"},
                "body": body,
            },
        }],
    }

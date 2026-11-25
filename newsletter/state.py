"""Remembers what was posted, so stories are not repeated and Friday's quiz can use the week's facts.

Stored in state/history.json (and one detailed log per day in state/runs/).
The scheduler commits these files back to the repository after each run.
"""
import json
import os
from datetime import date, timedelta

from . import util


def load(path):
    if not os.path.exists(path):
        return {"posts": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, state, keep_days=90):
    cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
    state["posts"] = [p for p in state["posts"] if p["date"] >= cutoff]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _recent(state, today, days):
    cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    return [p for p in state["posts"] if cutoff <= p["date"] < today or p["date"] == today]


def recent_urls(state, today, days):
    return {util.norm_url(s["url"]) for p in _recent(state, today, days)
            for s in p.get("stories", [])}


def recent_headlines(state, today, days):
    return [p["headline"] for p in _recent(state, today, days) if p.get("headline")]


def quiz_pool(state, today, days=6):
    """Fact sheets from the last few days of story posts (used for the Friday quiz)."""
    pool = []
    for post in _recent(state, today, days):
        if post["date"] == today:
            continue
        for story in post.get("stories", []):
            pool.append({"title": story["title"], "source": story.get("source", ""),
                         "facts": story["facts"]})
    return pool[-6:]


def pending_quiz(state, today):
    """Latest earlier post whose quiz answers have not been shown yet."""
    for post in reversed(state["posts"]):
        if post["date"] < today and post.get("quiz") and not post.get("quiz_revealed"):
            return post
    return None


def next_backup(backups, state):
    """Pick the backup post that was used least recently."""
    last_used = {}
    for index, post in enumerate(state["posts"]):
        if post["kind"] == "backup":
            last_used[post.get("backup_id")] = index
    return min(backups, key=lambda b: last_used.get(b["id"], -1))

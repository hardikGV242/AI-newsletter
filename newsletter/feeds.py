"""Read news feeds (RSS or Atom) and fetch article text from approved sites."""
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

from . import util


def _local(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def strip_tags(markup):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", markup or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_feed(xml_bytes, source):
    """Turn an RSS or Atom document into a list of story dicts."""
    if b"<!ENTITY" in xml_bytes[:5000]:
        raise ValueError("feed contains entity definitions; refusing to parse")
    root = ET.fromstring(xml_bytes)
    items = []
    for node in root.iter():
        kind = _local(node.tag)
        if kind not in ("item", "entry"):
            continue
        fields = {}
        for child in node:
            name = _local(child.tag)
            if name == "link" and kind == "entry":
                if child.get("rel", "alternate") == "alternate" and child.get("href"):
                    fields.setdefault("link", child.get("href"))
            elif name not in fields:
                fields[name] = (child.text or "").strip()
        link = fields.get("link", "")
        published = parse_date(fields.get("pubDate") or fields.get("published")
                               or fields.get("updated") or fields.get("date"))
        if not link or not fields.get("title") or published is None:
            continue
        body = fields.get("encoded") or fields.get("content") or ""
        summary = strip_tags(fields.get("description") or fields.get("summary") or "")
        items.append({
            "title": strip_tags(fields["title"]),
            "url": link,
            "published": published.isoformat(),
            "source": source["name"],
            "category": source["category"],
            "tier": source.get("tier", 2),
            "summary": summary[:500],
            "feed_text": strip_tags(body) if body else summary,
        })
    return items


def collect(sources, max_age_hours, now):
    """Read every enabled feed. Returns (fresh_items, error_messages)."""
    cutoff = now - timedelta(hours=max_age_hours)
    items, errors = [], []
    for source in sources:
        if not source.get("enabled", True):
            continue
        try:
            _, body, _ = util.http_request(source["url"], timeout=30)
            found = parse_feed(body, source)
        except Exception as err:  # one broken feed must not stop the others
            errors.append(f"{source['name']}: {err}")
            continue
        for item in found:
            if datetime.fromisoformat(item["published"]) >= cutoff:
                items.append(item)
    return items, errors


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg"}
    BLOCK = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "td", "th"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.current = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self.skip_depth:
            self.current.append(data)

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.current)).strip()
        self.current = []
        if len(text) >= 20:
            self.paragraphs.append(text)


def html_to_text(markup, max_chars):
    parser = _TextExtractor()
    parser.feed(markup)
    parser._flush()
    out, total = [], 0
    for para in parser.paragraphs:
        if total + len(para) > max_chars:
            break
        out.append(para)
        total += len(para) + 1
    return "\n".join(out)


def fetch_article(item, max_chars, min_chars=600):
    """Return the article's plain text, or None when we cannot get enough of it."""
    text = ""
    try:
        _, body, headers = util.http_request(item["url"], timeout=30)
        charset = headers.get_content_charset() if headers else None
        text = html_to_text(body.decode(charset or "utf-8", "replace"), max_chars)
    except Exception:
        text = ""
    if len(text) < min_chars:
        fallback = (item.get("feed_text") or "")[:max_chars]
        if len(fallback) >= min_chars:
            return fallback
        return None
    return text

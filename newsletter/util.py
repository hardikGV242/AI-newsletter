"""Small helpers: text cleaning, number finding, JSON extraction, HTTP with retries.

Only the Python standard library is used, so nothing needs to be installed.
"""
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlsplit

USER_AGENT = "Mozilla/5.0 (compatible; TeamNewsletterBot/1.0)"
RETRY_CODES = (429, 500, 502, 503, 504, 529)


class HttpError(Exception):
    def __init__(self, code, body=""):
        super().__init__(f"HTTP {code}: {str(body)[:300]}")
        self.code = code
        self.body = body


def http_request(url, data=None, headers=None, method=None, timeout=30, retries=3):
    """Send an HTTP request. Returns (status, body_bytes, headers).

    Retries on rate limits and temporary server errors with a growing pause.
    Raises HttpError when it still fails.
    """
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")
            if err.code in RETRY_CODES and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise HttpError(err.code, body)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise HttpError(0, str(err))
    raise HttpError(0, "no attempts made")


def load_dotenv(path):
    """Read KEY=VALUE lines from a local .env file (does not override real env vars)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def norm_text(text):
    """Lower-case, straighten quotes and dashes, collapse spaces. Used for matching."""
    s = unicodedata.normalize("NFKC", text or "")
    s = (s.replace("‘", "'").replace("’", "'")
          .replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-").replace(" ", " "))
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_url(url):
    """Make two links to the same page compare equal (drops query, fragment, trailing /)."""
    p = urlsplit((url or "").strip())
    return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}"


_NUMBER = re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?%?")


def number_tokens(text):
    """Find numbers in text. Returns a list of (normalised_number, is_strong).

    'Strong' numbers (2+ digits, decimals, percentages, money) must be backed by
    the source. Single bare digits like '3' are too common in normal writing.
    """
    found = []
    for match in _NUMBER.finditer(text or ""):
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        strong = len(digits) >= 2 or "%" in raw or "." in raw or raw[0] in "$€£"
        norm = raw.replace(",", "").lstrip("$€£").rstrip("%")
        found.append((norm, strong))
    return found


def extract_json(text):
    """Pull the first JSON object or list out of a model reply (handles code fences)."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON found in reply")
    obj, _ = json.JSONDecoder().raw_decode(text[min(starts):])
    return obj


def fill(template, **values):
    """Replace {{KEY}} markers in one pass (so inserted text is never re-scanned)."""
    return re.sub(r"\{\{(\w+)\}\}",
                  lambda m: str(values.get(m.group(1), m.group(0))), template)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

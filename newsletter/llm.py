"""Talks to the AI service. Uses the Google Gemini API (the free tier is enough).

To use a different AI provider, change only this file: keep the two methods
`complete()` and `complete_json()` working the same way.

Free-tier friendly behaviour:
- Calls are spaced out (min_interval seconds) to stay under per-minute limits.
- HTTP 429 (quota): wait the delay Gemini asks for, if it is short, then try the
  same model once more. A long delay means a daily quota, so the next model is used.
- HTTP 5xx (busy): wait a bit and try the same model once more, then the next one.
- 404 (model not found): go straight to the next model.
"""
import json
import os
import re
import time

from . import util

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_FALLBACKS = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
BUSY_CODES = (500, 502, 503, 504)
MAX_QUOTA_WAIT = 90   # seconds; longer waits are treated as "quota used up for today"
BUSY_WAIT = 20        # seconds to wait before retrying a busy model


def _retry_delay(body):
    """Read the 'retryDelay' (for example "37s") from a Gemini 429 error body."""
    match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', str(body or ""))
    return float(match.group(1)) if match else None


class LLM:
    def __init__(self, model=None, api_key=None, fallback_models=None, min_interval=4.0,
                 sleep=time.sleep, log=print):
        first = model or os.environ.get("NEWSLETTER_MODEL")
        fallbacks = DEFAULT_FALLBACKS if fallback_models is None else fallback_models
        models = ([first] if first else []) + list(fallbacks)
        self.models = list(dict.fromkeys(m for m in models if m))  # keep order, no repeats
        if not self.models:
            raise RuntimeError("no Gemini model configured")
        self.model = self.models[0]
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.min_interval = float(min_interval)
        self._sleep = sleep
        self._log = log
        self._last_call = 0.0
        self._exhausted = set()  # models whose daily quota is used up in this run

    def _pace(self):
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()

    def _call(self, model, system, user, max_tokens, want_json):
        config = {
            "temperature": 0.2,
            # Newer Gemini models "think" first, and that counts against the
            # output limit, so leave plenty of room for the real answer.
            "maxOutputTokens": max(max_tokens * 4, 8192),
        }
        if want_json:
            config["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }
        self._pace()
        # retries=1: waiting is handled here, where we know Gemini's retryDelay.
        _, body, _ = util.http_request(
            f"{API_BASE}/{model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            method="POST",
            timeout=180,
            retries=1,
        )
        reply = json.loads(body)
        candidates = reply.get("candidates") or []
        if not candidates:
            reason = (reply.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise RuntimeError(f"Gemini returned no answer ({reason})")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            finish = candidates[0].get("finishReason", "unknown")
            raise RuntimeError(f"Gemini returned an empty answer (finishReason={finish})")
        return text

    def complete(self, system, user, max_tokens=2500, want_json=False):
        last_err = None
        for model in self.models:
            if model in self._exhausted:
                continue
            for attempt in range(2):
                try:
                    text = self._call(model, system, user, max_tokens, want_json)
                    self.model = model
                    return text
                except util.HttpError as err:
                    last_err = err
                    if err.code == 429:
                        delay = _retry_delay(err.body)
                        if attempt == 0 and delay is not None and delay <= MAX_QUOTA_WAIT:
                            self._log(f"[llm] {model}: rate limited, waiting {delay:.0f}s")
                            self._sleep(delay + 1)
                            continue
                        self._log(f"[llm] {model}: quota used up, switching model")
                        self._exhausted.add(model)
                        break
                    if err.code in BUSY_CODES or err.code == 0:
                        if attempt == 0:
                            self._log(f"[llm] {model}: busy (HTTP {err.code}), waiting {BUSY_WAIT}s")
                            self._sleep(BUSY_WAIT)
                            continue
                        self._log(f"[llm] {model}: still busy, switching model")
                        break
                    if err.code == 404:
                        self._log(f"[llm] {model}: model not found, switching model")
                        self._exhausted.add(model)
                        break
                    raise
        raise last_err or RuntimeError("all Gemini models are unavailable")

    def complete_json(self, system, user, max_tokens=2500):
        """Ask for JSON. If the reply is not valid JSON, ask once more."""
        text = self.complete(system, user, max_tokens, want_json=True)
        try:
            return util.extract_json(text)
        except ValueError:
            retry = user + "\n\nYour previous reply was not valid JSON. Reply with the JSON only."
            return util.extract_json(self.complete(system, retry, max_tokens, want_json=True))

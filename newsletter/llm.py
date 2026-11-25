"""Talks to the AI service. Uses the Anthropic Messages API.

To use a different AI provider, change only this file: keep the two methods
`complete()` and `complete_json()` working the same way.
"""
import json
import os

from . import util

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class LLM:
    def __init__(self, model=None, api_key=None):
        self.model = model or os.environ.get("NEWSLETTER_MODEL") or "claude-sonnet-5-5"
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

    def complete(self, system, user, max_tokens=2500):
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        _, body, _ = util.http_request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            method="POST",
            timeout=180,
        )
        reply = json.loads(body)
        return "".join(b.get("text", "") for b in reply.get("content", [])
                       if b.get("type") == "text")

    def complete_json(self, system, user, max_tokens=2500):
        """Ask for JSON. If the reply is not valid JSON, ask once more."""
        text = self.complete(system, user, max_tokens)
        try:
            return util.extract_json(text)
        except ValueError:
            retry = user + "\n\nYour previous reply was not valid JSON. Reply with the JSON only."
            return util.extract_json(self.complete(system, retry, max_tokens))

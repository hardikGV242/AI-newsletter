"""Sends the finished post to Microsoft Teams through a Workflows webhook link."""
import json

from . import util

MAX_BYTES = 27 * 1024  # Teams webhook messages must stay under 28 KB


def post_payload(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError(f"message is {len(data)} bytes, over the 28 KB Teams limit")
    status, body, _ = util.http_request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST", timeout=30)
    if not 200 <= status < 300:
        raise util.HttpError(status, body.decode("utf-8", "replace"))
    return status


def post_card(url, card_payload):
    return post_payload(url, card_payload)


def post_text(url, text):
    """Plain text message (used for alerts and the webhook test)."""
    return post_payload(url, {"text": text})

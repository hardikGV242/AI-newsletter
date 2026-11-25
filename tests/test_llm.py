"""Offline tests for the Gemini retry / fallback logic. No network, no real waiting."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from newsletter import llm as llm_mod, util  # noqa: E402

OK_BODY = json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}).encode()


def quota_error(seconds):
    return util.HttpError(429, json.dumps({"error": {"details": [{"retryDelay": f"{seconds}s"}]}}))


class LLMRetryTests(unittest.TestCase):
    def make(self, responses):
        """responses: list of bytes (success) or HttpError (failure), used in order."""
        self.calls, self.slept = [], []
        queue = list(responses)

        def fake_request(url, **_kw):
            self.calls.append(url.split("/models/")[1].split(":")[0])
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return 200, item, None

        patcher = mock.patch.object(util, "http_request", fake_request)
        patcher.start()
        self.addCleanup(patcher.stop)
        return llm_mod.LLM(model="m1", api_key="k", fallback_models=["m2", "m3"],
                           min_interval=0, sleep=self.slept.append, log=lambda *a: None)

    def test_short_429_waits_then_retries_same_model(self):
        llm = self.make([quota_error(30), OK_BODY])
        self.assertEqual(llm.complete_json("s", "u"), {"ok": True})
        self.assertEqual(self.calls, ["m1", "m1"])
        self.assertEqual(self.slept, [31])

    def test_long_429_switches_model_and_remembers(self):
        llm = self.make([quota_error(3600), OK_BODY, OK_BODY])
        llm.complete("s", "u")
        llm.complete("s", "u")
        self.assertEqual(self.calls, ["m1", "m2", "m2"])  # m1 not tried again this run

    def test_busy_model_retries_once_then_falls_back(self):
        llm = self.make([util.HttpError(503), util.HttpError(503), OK_BODY])
        llm.complete("s", "u")
        self.assertEqual(self.calls, ["m1", "m1", "m2"])
        self.assertEqual(self.slept, [llm_mod.BUSY_WAIT])

    def test_missing_model_is_skipped(self):
        llm = self.make([util.HttpError(404), OK_BODY])
        llm.complete("s", "u")
        self.assertEqual(self.calls, ["m1", "m2"])

    def test_all_models_fail_raises(self):
        llm = self.make([util.HttpError(404)] * 3)
        with self.assertRaises(util.HttpError):
            llm.complete("s", "u")

    def test_bad_key_is_not_retried(self):
        llm = self.make([util.HttpError(400)])
        with self.assertRaises(util.HttpError):
            llm.complete("s", "u")
        self.assertEqual(self.calls, ["m1"])


if __name__ == "__main__":
    unittest.main()

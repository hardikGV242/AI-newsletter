"""Command line.  Run:  python -m newsletter <command>

Commands
  run             build today's post and send it to Teams
  check-sources   test every news feed in sources.json
  check-llm       test the AI key
  test-webhook    send a test message to the Teams channel
"""
import argparse
import os
import sys
import traceback
from datetime import datetime, timezone

from . import card as card_mod
from . import feeds, pipeline, teams, util
from .llm import LLM

ROOT = pipeline.ROOT


def _alert(text):
    url = os.environ.get("TEAMS_ALERT_WEBHOOK_URL")
    if not url:
        print("(no TEAMS_ALERT_WEBHOOK_URL set, alert not sent)", text)
        return
    try:
        teams.post_text(url, "⚠️ " + text)
    except Exception as err:
        print("Could not send alert:", err)


def cmd_run(args):
    cfg = util.load_json(ROOT / "config.json")
    llm = LLM(model=cfg.get("model"))
    try:
        pipeline.run(cfg, llm, dry_run=args.dry_run, force=args.force,
                     weekday=args.weekday, alert=_alert)
    except Exception as err:
        traceback.print_exc()
        if not args.dry_run:
            _alert(f"Newsletter job FAILED: {type(err).__name__}: {err}")
        return 1
    return 0


def cmd_check_sources(_args):
    sources = util.load_json(ROOT / "sources.json")
    bad = 0
    now = datetime.now(timezone.utc)
    for source in sources:
        if not source.get("enabled", True):
            print(f"-  {source['name']}: disabled")
            continue
        try:
            _, body, _ = util.http_request(source["url"], timeout=30)
            items = feeds.parse_feed(body, source)
            fresh = [i for i in items
                     if (now - datetime.fromisoformat(i["published"])).total_seconds() < 48 * 3600]
            print(f"OK {source['name']}: {len(items)} items, {len(fresh)} from the last 48 hours")
            if not items:
                bad += 1
        except Exception as err:
            bad += 1
            print(f"FAIL {source['name']}: {err}\n     {source['url']}")
    print(f"\n{bad} feed(s) need attention. Set \"enabled\": false in sources.json "
          "for any you do not want, or fix the URL.")
    return 1 if bad == len(sources) else 0


def cmd_check_llm(_args):
    cfg = util.load_json(ROOT / "config.json")
    llm = LLM(model=cfg.get("model"))
    print(f"Model: {llm.model}")
    print("Reply:", llm.complete("You are a connection test.", "Reply with the single word OK.", 20))
    return 0


def cmd_test_webhook(args):
    url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not url:
        print("TEAMS_WEBHOOK_URL is not set (put it in .env).")
        return 1
    if args.card:
        cfg = util.load_json(ROOT / "config.json")
        backup = util.load_json(ROOT / "backup_posts.json")[0]
        message = card_mod.build(cfg, cfg["themes"]["0"], {"kind": "backup", "backup": backup},
                                 None, datetime.now().strftime("%a %d %b %Y"))
        status = teams.post_card(url, message)
    else:
        status = teams.post_text(url, "✅ Newsletter bot test: if you can read this, "
                                      "the Teams webhook works.")
    print(f"Teams answered with status {status}. Now look in the channel.")
    print("If nothing appears within a minute, open the Workflows app > your workflow > "
          "Run history to see why.")
    return 0


def main():
    util.load_dotenv(str(ROOT / ".env"))
    parser = argparse.ArgumentParser(prog="newsletter")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="build and post today's newsletter")
    run.add_argument("--dry-run", action="store_true", help="build it but do not post or save")
    run.add_argument("--force", action="store_true",
                     help="ignore weekend, skip dates and 'already posted today'")
    run.add_argument("--weekday", type=int, choices=range(0, 7),
                     help="pretend it is this weekday (0=Mon) to test a theme")
    sub.add_parser("check-sources")
    sub.add_parser("check-llm")
    hook = sub.add_parser("test-webhook")
    hook.add_argument("--card", action="store_true", help="send a sample card instead of text")
    args = parser.parse_args()
    handlers = {"run": cmd_run, "check-sources": cmd_check_sources,
                "check-llm": cmd_check_llm, "test-webhook": cmd_test_webhook}
    try:
        code = handlers[args.command](args)
    except RuntimeError as err:  # setup problems such as a missing key
        print(f"\nSETUP PROBLEM: {err}\nSee README.md, steps 2 and 3, and your .env file.")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()

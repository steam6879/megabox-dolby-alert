#!/usr/bin/env python3
"""Cinema booking-open alert (Megabox, Lotte Cinema).

For every target in config.json, fetch the showtimes of the listed branches, keep the
ones matching the screen kinds and title keywords, and send a Telegram message when a
(branch, date, movie) combination appears for the first time.

Already-notified combinations are stored in state/snapshot.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

from providers import PROVIDERS, common

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
SNAPSHOT_PATH = ROOT / "state" / "snapshot.json"


# --------------------------------------------------------------------------- #
# Filtering / diff
# --------------------------------------------------------------------------- #
def _squash(text: str) -> str:
    """Lowercase and drop spaces/punctuation so '포드v페라리' matches '포드 V 페라리'."""
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def matches(show: dict, target: dict) -> bool:
    kinds = [str(k) for k in (target.get("theater_kinds") or [])]
    if kinds and show["screen_kind"] not in kinds:
        return False
    keywords = [_squash(k) for k in (target.get("keywords") or []) if _squash(k)]
    if not keywords:
        return True
    title = _squash(show["movie"]) + "|" + _squash(show["movie_en"])
    return any(k in title for k in keywords)


def group_matches(shows: list[dict], target: dict) -> dict[str, dict]:
    """Group by (branch, date, movie) so extra showtimes on an already-notified day stay quiet."""
    groups: dict[str, dict] = {}
    for s in shows:
        if not matches(s, target):
            continue
        key = f"{s['branch_id']}|{s['date']}|{s['movie_id']}"
        g = groups.setdefault(
            key,
            {k: s[k] for k in ("chain", "branch_id", "branch_name", "date", "view_date", "movie", "screen_name", "url")}
            | {"times": []},
        )
        g["times"].append({"start": s["start"], "rest": s["rest"], "total": s["total"], "bookable": s["bookable"]})
    for g in groups.values():
        g["times"].sort(key=lambda t: t["start"] or "")
    return groups


def load_snapshot() -> dict:
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {"notified": {}}


def save_snapshot(snap: dict) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prune_snapshot(snap: dict) -> None:
    """Forget entries whose show date has passed. Keys look like 'target::branch|YYYYMMDD|movie'."""
    today = common.today_kst()
    snap["notified"] = {k: v for k, v in snap["notified"].items() if k.split("|")[1] >= today}


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #
def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            # Fail loudly in Actions instead of silently printing
            raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secrets are not set.")
        print("[telegram] No TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, printing only.\n" + text)
        return
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram send failed: HTTP {resp.status_code} {resp.text[:200]}")


def format_message(target_name: str, new_groups: list[dict]) -> str:
    lines = [f"🎬 [{target_name}] 새 회차가 열렸어요!", ""]
    by_branch: dict[tuple, list[dict]] = {}
    for g in new_groups:
        by_branch.setdefault((g["chain"], g["branch_id"]), []).append(g)
    for groups in by_branch.values():
        groups.sort(key=lambda g: (g["date"], g["movie"]))
        lines.append(f"📍 {groups[0]['branch_name']}")
        for g in groups:
            times = ", ".join(
                f"{t['start']}({t['rest']}/{t['total']})" + ("" if t["bookable"] else "·예매불가") for t in g["times"]
            )
            lines.append(f"• {g['view_date']} {g['movie']} — {g['screen_name']}")
            lines.append(f"   {times}")
        lines.append(f"👉 {groups[0]['url']}")
        lines.append("")
    lines.append("(괄호: 잔여석/전체석)")
    return "\n".join(lines).strip()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(config: dict, dry_run: bool = False) -> int:
    snap = load_snapshot()
    prune_snapshot(snap)
    session = requests.Session()
    cache: dict[tuple, list[dict]] = {}  # (chain, branch) -> showtimes, fetched once per run
    total_new = 0

    for target in config["targets"]:
        if not target.get("enabled", True):
            continue
        chain = target.get("chain", "megabox")
        if chain not in PROVIDERS:
            raise ValueError(f"Unknown chain '{chain}' in target '{target['name']}'")
        new_groups: list[dict] = []
        for branch in target["branches"]:
            branch = str(branch)
            if (chain, branch) not in cache:
                cache[(chain, branch)] = PROVIDERS[chain].fetch_showtimes(session, branch)
            groups = group_matches(cache[(chain, branch)], target)
            for key, g in groups.items():
                snap_key = f"{target['name']}::{key}"
                if snap_key not in snap["notified"]:
                    new_groups.append(g)
                    snap["notified"][snap_key] = datetime.now(common.KST).isoformat(timespec="seconds")
            print(f"[{target['name']}] {chain}:{branch} matches={len(groups)}")

        if new_groups:
            total_new += len(new_groups)
            msg = format_message(target["name"], new_groups)
            print(msg)
            if not dry_run:
                send_telegram(msg)

    if not dry_run:
        save_snapshot(snap)
    print(f"Done: {total_new} new item(s) notified")
    return total_new


def main() -> None:
    parser = argparse.ArgumentParser(description="Cinema booking-open alert")
    parser.add_argument("--dry-run", action="store_true", help="print results without sending alerts or saving state")
    parser.add_argument("--test-message", action="store_true", help="send a Telegram connection test message")
    args = parser.parse_args()

    if args.test_message:
        send_telegram("✅ 영화 예매 오픈 알리미 Telegram 연결 테스트 성공!")
        print("Test message sent.")
        return

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    try:
        run(config, dry_run=args.dry_run)
    except Exception as e:  # a silently broken bot is the worst outcome, so report failures too
        err = f"⚠️ 영화 예매 알리미 조회 실패: {type(e).__name__}: {e}"
        print(err, file=sys.stderr)
        if not args.dry_run and config.get("notify_on_error", True):
            try:
                send_telegram(err)
            except Exception as te:
                print(f"(failed to send the error alert too: {te})", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

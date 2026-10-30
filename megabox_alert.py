#!/usr/bin/env python3
"""메가박스 특별관 예매 오픈 알리미.

config.json에 적힌 지점(brchNo)의 상영시간표를 조회해서,
지정한 상영관 종류(예: DBC = 돌비시네마)와 영화 제목 키워드에 맞는 회차가
새로 열리면 Telegram으로 알림을 보낸다.

이미 알린 (지점, 날짜, 영화) 조합은 state/snapshot.json에 저장해서 다시 알리지 않는다.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

KST = timezone(timedelta(hours=9))
BASE = "https://www.megabox.co.kr"
SCHEDULE_URL = f"{BASE}/on/oh/ohc/Brch/schedulePage.do"
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
SNAPSHOT_PATH = ROOT / "state" / "snapshot.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE,
}

REQUEST_DELAY_SEC = 1.0  # 날짜별 요청 사이 간격 (서버 부담 줄이기)


# --------------------------------------------------------------------------- #
# Megabox API
# --------------------------------------------------------------------------- #
class MegaboxError(RuntimeError):
    pass


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def fetch_schedule(session: requests.Session, brch_no: str, play_de: str, first: bool) -> dict:
    """한 지점의 특정 날짜 상영시간표를 가져온다.

    first=True면 응답에 예매 가능 날짜 목록(movieFormDeList)이 함께 온다.
    """
    body = {
        "masterType": "brch",
        "detailType": "spcl",
        "theabKindCd": "",
        "brchNo": brch_no,
        "firstAt": "Y" if first else "N",
        "brchNo1": brch_no,
        "crtDe": today_kst(),
        "playDe": play_de,
    }
    headers = dict(HEADERS, Referer=f"{BASE}/theater/time?brchNo={brch_no}")
    resp = session.post(SCHEDULE_URL, json=body, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise MegaboxError(f"HTTP {resp.status_code} (brchNo={brch_no}, playDe={play_de})")
    try:
        data = resp.json()
    except ValueError as e:
        raise MegaboxError(f"JSON 파싱 실패: {resp.text[:200]!r}") from e
    if data.get("statCd") not in (0, "0", None) or "megaMap" not in data:
        raise MegaboxError(f"비정상 응답: statCd={data.get('statCd')} msg={data.get('msg')}")
    return data["megaMap"]


def collect_showtimes(session: requests.Session, brch_no: str) -> list[dict]:
    """지점의 '상영 일정이 있는' 모든 날짜를 돌면서 회차 목록을 모은다."""
    first = fetch_schedule(session, brch_no, today_kst(), first=True)
    dates = [d["playDe"] for d in (first.get("movieFormDeList") or []) if d.get("formAt") == "Y"]

    showtimes: list[dict] = []
    for i, de in enumerate(dates):
        if de == first.get("playDe"):
            m = first
        else:
            time.sleep(REQUEST_DELAY_SEC)
            m = fetch_schedule(session, brch_no, de, first=False)
        showtimes.extend(m.get("movieFormList") or [])
    return showtimes


# --------------------------------------------------------------------------- #
# Filtering / diff
# --------------------------------------------------------------------------- #
def clean(text: str | None) -> str:
    return html.unescape(text or "").strip()


def matches(show: dict, target: dict) -> bool:
    kinds = target.get("theater_kinds") or []
    if kinds and show.get("theabKindCd") not in kinds:
        return False
    keywords = [k.lower() for k in (target.get("keywords") or [])]
    if not keywords:
        return True
    title = f"{clean(show.get('movieNm'))} {clean(show.get('movieEngNm'))}".lower()
    return any(k in title for k in keywords)


def group_matches(showtimes: list[dict], target: dict) -> dict[str, dict]:
    """(지점, 날짜, 영화) 단위로 묶는다. 같은 날 회차가 늘어나는 것까지 매번 알리면 시끄러우니까."""
    groups: dict[str, dict] = {}
    for s in showtimes:
        if not matches(s, target):
            continue
        key = f"{s['brchNo']}|{s['playDe']}|{s['movieNo']}"
        g = groups.setdefault(
            key,
            {
                "brchNo": s["brchNo"],
                "branch": clean(s.get("brchNm")),
                "playDe": s["playDe"],
                "viewDe": clean(s.get("viewDe")),
                "movie": clean(s.get("movieNm")),
                "theater": clean(s.get("theabExpoNm")),
                "times": [],
            },
        )
        g["times"].append(
            {
                "start": s.get("playStartTime"),
                "rest": s.get("restSeatCnt"),
                "total": s.get("totSeatCnt"),
                "bookable": s.get("bokdAbleAt") == "Y",
            }
        )
    for g in groups.values():
        g["times"].sort(key=lambda t: t["start"] or "")
    return groups


def load_snapshot() -> dict:
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {"notified": {}}


def save_snapshot(snap: dict) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def prune_snapshot(snap: dict) -> None:
    """이미 지난 날짜 기록은 지운다."""
    today = today_kst()
    snap["notified"] = {k: v for k, v in snap["notified"].items() if k.split("|")[1] >= today}


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #
def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없어 콘솔에만 출력합니다.\n" + text)
        return
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram 전송 실패: HTTP {resp.status_code} {resp.text[:200]}")


def format_message(target_name: str, new_groups: list[dict]) -> str:
    lines = [f"🎬 [{target_name}] 새 회차가 열렸어요!", ""]
    by_branch: dict[str, list[dict]] = {}
    for g in new_groups:
        by_branch.setdefault(g["brchNo"], []).append(g)
    for brch_no, groups in by_branch.items():
        groups.sort(key=lambda g: (g["playDe"], g["movie"]))
        lines.append(f"📍 {groups[0]['branch']}")
        for g in groups:
            times = ", ".join(
                f"{t['start']}({t['rest']}/{t['total']})" + ("" if t["bookable"] else "·예매불가")
                for t in g["times"]
            )
            lines.append(f"• {g['viewDe']} {g['movie']} — {g['theater']}")
            lines.append(f"   {times}")
        lines.append(f"👉 {BASE}/theater/time?brchNo={brch_no}")
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

    # 같은 지점을 여러 target이 쓰면 한 번만 조회
    branch_cache: dict[str, list[dict]] = {}
    total_new = 0

    for target in config["targets"]:
        if not target.get("enabled", True):
            continue
        new_groups: list[dict] = []
        for brch_no in target["branches"]:
            if brch_no not in branch_cache:
                branch_cache[brch_no] = collect_showtimes(session, brch_no)
            groups = group_matches(branch_cache[brch_no], target)
            for key, g in groups.items():
                snap_key = f"{target['name']}::{key}"
                if snap_key not in snap["notified"]:
                    new_groups.append(g)
                    snap["notified"][snap_key] = datetime.now(KST).isoformat(timespec="seconds")
            print(f"[{target['name']}] brchNo={brch_no}: 조건 일치 {len(groups)}건")

        if new_groups:
            total_new += len(new_groups)
            msg = format_message(target["name"], new_groups)
            print(msg)
            if not dry_run:
                send_telegram(msg)

    if not dry_run:
        save_snapshot(snap)
    print(f"완료: 새로 알린 항목 {total_new}건")
    return total_new


def main() -> None:
    parser = argparse.ArgumentParser(description="메가박스 예매 오픈 알리미")
    parser.add_argument("--dry-run", action="store_true", help="알림·snapshot 저장 없이 결과만 출력")
    parser.add_argument("--test-message", action="store_true", help="Telegram 설정 확인용 테스트 메시지 전송")
    args = parser.parse_args()

    if args.test_message:
        send_telegram("✅ 메가박스 알리미 Telegram 연결 테스트 성공!")
        print("테스트 메시지를 보냈습니다.")
        return

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    try:
        run(config, dry_run=args.dry_run)
    except Exception as e:  # 조용히 고장나는 게 제일 위험하니 실패도 알린다
        err = f"⚠️ 메가박스 알리미 조회 실패: {type(e).__name__}: {e}"
        print(err, file=sys.stderr)
        if not args.dry_run and config.get("notify_on_error", True):
            try:
                send_telegram(err)
            except Exception as te:
                print(f"(오류 알림 전송도 실패: {te})", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

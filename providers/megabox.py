"""Megabox (메가박스) showtime provider.

Branch id: ``brchNo`` from the branch page URL, e.g. ``4062`` for Songdo.
Screen kind: ``theabKindCd`` such as ``DBC`` (Dolby Cinema).
"""

from __future__ import annotations

import html
import time

from . import common

BASE = "https://www.megabox.co.kr"
SCHEDULE_URL = f"{BASE}/on/oh/ohc/Brch/schedulePage.do"


def _clean(text):
    return html.unescape(text or "").strip()


def _fetch_day(session, brch_no: str, play_de: str, first: bool) -> dict:
    body = {
        "masterType": "brch",
        "detailType": "spcl",
        "theabKindCd": "",
        "brchNo": brch_no,
        "firstAt": "Y" if first else "N",
        "brchNo1": brch_no,
        "crtDe": common.today_kst(),
        "playDe": play_de,
    }
    headers = {
        "User-Agent": common.USER_AGENT,
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE,
        "Referer": f"{BASE}/theater/time?brchNo={brch_no}",
    }
    resp = session.post(SCHEDULE_URL, json=body, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise common.FetchError(f"Megabox HTTP {resp.status_code} (brchNo={brch_no}, playDe={play_de})")
    try:
        data = resp.json()
    except ValueError as e:
        raise common.FetchError(f"Megabox returned non-JSON: {resp.text[:200]!r}") from e
    if data.get("statCd") not in (0, "0", None) or "megaMap" not in data:
        raise common.FetchError(f"Megabox unexpected response: statCd={data.get('statCd')} msg={data.get('msg')}")
    return data["megaMap"]


def _normalize(s: dict) -> dict:
    return {
        "chain": "megabox",
        "branch_id": s["brchNo"],
        "branch_name": "메가박스 " + _clean(s.get("brchNm")),
        "date": s["playDe"],
        "view_date": _clean(s.get("viewDe")),
        "movie_id": s["movieNo"],
        "movie": _clean(s.get("movieNm")),
        "movie_en": _clean(s.get("movieEngNm")),
        "screen_kind": s.get("theabKindCd") or "",
        "screen_name": _clean(s.get("theabExpoNm")),
        "start": s.get("playStartTime"),
        "rest": s.get("restSeatCnt"),
        "total": s.get("totSeatCnt"),
        "bookable": s.get("bokdAbleAt") == "Y",
        "url": f"{BASE}/theater/time?brchNo={s['brchNo']}",
    }


def fetch_showtimes(session, branch: str) -> list[dict]:
    first = _fetch_day(session, branch, common.today_kst(), first=True)
    dates = [d["playDe"] for d in (first.get("movieFormDeList") or []) if d.get("formAt") == "Y"]
    shows: list[dict] = []
    for de in dates:
        if de == first.get("playDe"):
            day = first
        else:
            time.sleep(common.REQUEST_DELAY_SEC)
            day = _fetch_day(session, branch, de, first=False)
        shows.extend(_normalize(s) for s in (day.get("movieFormList") or []))
    return shows

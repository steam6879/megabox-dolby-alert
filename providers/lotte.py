"""Lotte Cinema (롯데시네마) showtime provider.

Branch id: ``CinemaID``, e.g. ``3008`` for Bupyeong Station (부평역사).
Screen kind: ``ScreenDivisionCode`` as a string, e.g. ``901`` (광음시네마), ``940`` (수퍼플렉스).
"""

from __future__ import annotations

import json
import time

from . import common

BASE = "https://www.lottecinema.co.kr"
API_URL = f"{BASE}/LCWS/Ticketing/TicketingData.aspx"
SCHEDULE_PAGE = f"{BASE}/NLCHS/Ticketing/Schedule"



def _call(session, method: str, **params) -> dict:
    payload = {
        "MethodName": method,
        "channelType": "HO",
        "osType": "W",
        "osVersion": common.USER_AGENT,
        **params,
    }
    headers = {"User-Agent": common.USER_AGENT, "Referer": SCHEDULE_PAGE, "Origin": BASE}
    # The site posts paramList as a multipart form field
    resp = session.post(API_URL, files={"paramList": (None, json.dumps(payload))}, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise common.FetchError(f"Lotte Cinema HTTP {resp.status_code} ({method})")
    try:
        return resp.json()
    except ValueError as e:
        raise common.FetchError(f"Lotte Cinema returned non-JSON: {resp.text[:200]!r}") from e


def _ticketing_page(session) -> dict:
    data = _call(session, "GetTicketingPageTOBE", memberOnNo="")
    if "Cinemas" not in data or "MoviePlayDates" not in data:
        raise common.FetchError(f"Lotte Cinema unexpected page response: {data.get('ResultMessage')}")
    return data


def _cinema_param(page: dict, cinema_id: str) -> str:
    """Build the 'DivisionCode|DetailDivisionCode|CinemaID' value the API expects."""
    for c in (page["Cinemas"].get("Cinemas") or {}).get("Items") or []:
        if str(c.get("CinemaID")) == str(cinema_id) and c.get("DivisionCode") == 1:
            return f"1|{c['DetailDivisionCode']}|{c['CinemaID']}"
    raise common.FetchError(f"Lotte Cinema branch {cinema_id} not found")


def _normalize(s: dict) -> dict:
    date = (s.get("PlayDt") or "").replace("-", "")
    return {
        "chain": "lotte",
        "branch_id": str(s["CinemaID"]),
        "branch_name": "롯데시네마 " + (s.get("CinemaNameKR") or ""),
        "date": date,
        "view_date": f"{date[4:6]}/{date[6:8]}({s.get('PlayDayKR', '')})" if len(date) == 8 else date,
        "movie_id": str(s.get("MovieCode")),
        "movie": (s.get("MovieNameKR") or "").strip(),
        "movie_en": (s.get("MovieNameUS") or "").strip(),
        "screen_kind": str(s.get("ScreenDivisionCode") or ""),
        "screen_name": " ".join(
            x for x in [s.get("ScreenNameKR"), s.get("ScreenDivisionNameKR"), s.get("FilmNameKR")] if x
        ),
        "start": s.get("StartTime"),
        "rest": s.get("BookingSeatCount"),
        "total": s.get("TotalSeatCount"),
        "bookable": s.get("IsBookingYN") == "Y",
        "url": SCHEDULE_PAGE,
    }


def fetch_showtimes(session, branch: str) -> list[dict]:
    page = _ticketing_page(session)
    cinema = _cinema_param(page, branch)
    dates = [d["PlayDate"] for d in ((page["MoviePlayDates"].get("Items") or {}).get("Items") or [])]
    shows: list[dict] = []
    for i, play_date in enumerate(dates):
        if i:
            time.sleep(common.REQUEST_DELAY_SEC)
        day = _call(session, "GetPlaySequence", playDate=play_date, cinemaID=cinema, representationMovieCode="")
        if "PlaySeqs" not in day:
            raise common.FetchError(f"Lotte Cinema unexpected schedule response: {day.get('ResultMessage')}")
        shows.extend(_normalize(s) for s in ((day["PlaySeqs"] or {}).get("Items") or []))
    return shows

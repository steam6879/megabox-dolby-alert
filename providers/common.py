from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

REQUEST_DELAY_SEC = 1.0  # pause between per-date requests to keep server load low


class FetchError(RuntimeError):
    pass


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y%m%d")

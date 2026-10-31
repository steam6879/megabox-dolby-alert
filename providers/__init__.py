"""Theater chain providers.

Each provider exposes ``fetch_showtimes(session, branch) -> list[dict]`` returning
showtimes normalized to the same shape:

    chain, branch_id, branch_name, date (YYYYMMDD), view_date, movie_id, movie,
    movie_en, screen_kind, screen_name, start, rest, total, bookable, url
"""

from . import lotte, megabox

PROVIDERS = {
    "megabox": megabox,
    "lotte": lotte,
}

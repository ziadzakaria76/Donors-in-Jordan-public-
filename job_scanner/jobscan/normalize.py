"""Turning whatever a portal returned into comparable postings.

Date parsing is deliberately conservative. A string that does not parse
becomes None -- unknown -- rather than today's date, because "unknown" keeps a
stale posting visible as stale while "today" silently launders it past
max_age_days. The same reasoning drives keep_recent()'s treatment of unknown
dates: they are kept and flagged, never quietly dropped and never treated as
fresh.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Iterable

from .model import Posting

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d-%b-%Y",
)


def parse_date(value: Any) -> _dt.date | None:
    """Best-effort date parse. Returns None when unsure, never a guess."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value

    # Epoch milliseconds/seconds, as SuccessFactors and Elevatus both emit.
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        number = int(value)
        if number > 10_000_000_000:      # milliseconds
            number //= 1000
        if 0 < number < 4_102_444_800:   # sane range, up to year 2100
            try:
                return _dt.datetime.fromtimestamp(number, _dt.timezone.utc).date()
            except (OverflowError, OSError, ValueError):
                return None
        return None

    text = str(value).strip()
    if not text:
        return None

    # /Date(1699999999000)/ -- the .NET serialiser shape SAP sites still emit.
    dotnet = re.match(r"^/Date\((\d+)[^)]*\)/$", text)
    if dotnet:
        return parse_date(int(dotnet.group(1)))

    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def dedupe(postings: Iterable[Posting]) -> list[Posting]:
    """Collapse repeats, keeping the first sighting of each identity.

    Cross-posting is common: an employer lists the same requisition on its own
    site and through a platform tenant. Identity is the apply URL where there
    is one, falling back to source+title+location.
    """
    seen: set[str] = set()
    unique: list[Posting] = []
    for posting in postings:
        if posting.identity in seen:
            continue
        seen.add(posting.identity)
        unique.append(posting)
    return unique


def keep_recent(
    postings: Iterable[Posting], max_age_days: int
) -> tuple[list[Posting], list[Posting], int]:
    """Split postings by age against the frozen max_age_days.

    Returns (kept, dropped, unknown_date_count). Postings with no parseable
    date are KEPT -- dropping them would hide real vacancies from portals that
    simply do not publish a posting date -- but they are counted so the run
    report can say how much of the result rests on an unknown date.
    """
    kept: list[Posting] = []
    dropped: list[Posting] = []
    unknown = 0
    for posting in postings:
        age = posting.age_days
        if age is None:
            unknown += 1
            kept.append(posting)
        elif age <= max_age_days:
            kept.append(posting)
        else:
            dropped.append(posting)
    return kept, dropped, unknown


def dig(payload: Any, path: str) -> Any:
    """Walk a dotted path into a JSON body. '' returns the payload itself.

    Supports list indices ('items.0.requisitionList') because Oracle ORC wraps
    its results exactly that way.
    """
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if not part.isdigit() or int(part) >= len(current):
                return None
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current

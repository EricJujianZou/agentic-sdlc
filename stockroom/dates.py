"""Calendar dates, in one spelling.

Every date the system stores - order dates, arrival dates, price-change
dates, shipment dates - is a zero-padded ISO ``YYYY-MM-DD`` string, so
two dates written a day apart compare and sort the way the days
themselves do.  People type them with the leading zeros left off, and
state files written before this was settled hold whatever was typed, so
dates are put into that one spelling the moment they arrive: on the way
in from a command, and on the way in off disk.
"""

import datetime


def parse_date(text: str) -> datetime.date:
    """Read a typed date as a real date.

    Both ``YYYY-MM-DD`` and the unpadded ``YYYY-M-D`` are accepted.
    Anything that is not a real day on the calendar - a month of 13, the
    30th of February, a word - raises ``ValueError``, which the CLI turns
    into exit code 1 before anything is written.
    """
    parts = text.strip().split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid date {text}: expected YYYY-MM-DD")
    year, month, day = (int(part) for part in parts)
    try:
        return datetime.date(year, month, day)
    except ValueError:
        raise ValueError(f"invalid date {text}: no such day") from None


def normalize_date(text: str) -> str:
    """The canonical ``YYYY-MM-DD`` spelling of a typed date."""
    return parse_date(text).isoformat()


def normalize_stored(date: str | None) -> str | None:
    """The canonical spelling of a date read out of a state file.

    Old files hold dates as they were typed, so a stored "2026-1-5" is
    read back as "2026-01-05" and is written back that way on the next
    save.  A record with no date at all keeps having none, and anything
    that will not parse is handed back untouched: a file we cannot make
    sense of should still load, rather than costing the user the rest of
    their state.
    """
    if not date:
        return date
    try:
        return normalize_date(date)
    except ValueError:
        return date

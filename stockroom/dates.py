"""Date helpers.

Dates arrive typed by hand, so "2026-1-5" and "2026-01-05" both mean the
5th of January.  Everything that compares, sorts or filters dates goes
through here so the two spellings behave identically.
"""

import datetime


def parse_date(value: str) -> datetime.date | None:
    """Parse a YYYY-M-D style date, padded or not.

    Returns None when the string is not a real calendar date, so callers
    can decide whether that is an error or just something to skip.
    """
    if isinstance(value, datetime.date):
        return value
    parts = str(value).split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
        return datetime.date(year, month, day)
    except ValueError:
        return None


def normalize_date(value: str) -> str:
    """Return *value* as a zero-padded ISO date, or raise ValueError."""
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"invalid date: {value}")
    return parsed.isoformat()


def normalize_stored_date(value):
    """Normalize a date read from an old data file.

    Legacy files hold whatever someone typed ("2026-1-5"); anything we
    can read as a date comes back zero-padded.  Values we cannot parse
    (and None) are handed back untouched rather than losing the data.
    """
    if not value:
        return value
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else value


def sort_key(value: str) -> tuple:
    """Sort key that orders parseable dates chronologically.

    Unparseable dates sort after every real date, by their raw text, so
    ordering stays stable instead of blowing up.
    """
    parsed = parse_date(value)
    if parsed is None:
        return (1, str(value))
    return (0, parsed.isoformat())

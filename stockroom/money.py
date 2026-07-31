"""The one place money is turned into text.

Every report used to spell its own amounts, so the same price could come
out as ``19.99`` in one column and ``19.990`` in the next.  Printing goes
through :func:`format_money` instead, so a figure looks the same wherever
it lands.  Money we did not write ourselves comes back in through
:func:`parse_money`, which reads the spellings other people use.
"""

import re

from .models import to_cents

# An amount as people and supplier files write it: an optional sign, an
# optional dollar sign, then the digits, with any spacing around the lot.
_MONEY_RE = re.compile(r"^(-?)\$?(\d+(?:\.\d+)?|\.\d+)$")


def format_amount(amount: int | float) -> str:
    """Return an amount as a bare money string, e.g. ``"19.99"``.

    The same figure :func:`format_money` shows, without the ``$``, for
    the places where an amount is data rather than something a person
    reads: a CSV price cell has to carry exactly two decimals and still
    be a number.

    Args:
        amount: whole cents when an ``int`` (``1999`` is ``"19.99"``),
            dollars when a ``float`` (``3.5`` is ``"3.50"``).
    """
    cents = amount if isinstance(amount, int) else to_cents(amount)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def format_money(amount: int | float) -> str:
    """Return an amount as a plain money string, e.g. ``"$19.99"``.

    Args:
        amount: whole cents when an ``int`` (``1999`` is ``"$19.99"``),
            dollars when a ``float`` (``3.5`` is ``"$3.50"``).

    Returns:
        The amount with a leading ``$``, exactly two decimals and no
        thousands separators.  A negative amount reads ``-$12.50``.
    """
    text = format_amount(amount)
    if text.startswith("-"):
        return f"-${text[1:]}"
    return f"${text}"


def parse_money(text: str) -> float:
    """Return a written amount as dollars, however it was spelled.

    Supplier files spell the same price as ``3.5``, ``3.50`` or
    ``$3.50``, and pad the cell while they are at it, so all of those
    read as the one amount.  A cell that is not money at all is a
    ValueError - the caller's cue to treat the file as the user's
    mistake.  This is the inverse of :func:`format_money`, so it takes
    that function's leading ``-`` too.
    """
    match = _MONEY_RE.match(str(text).strip())
    if match is None:
        raise ValueError(f"not a price: {text!r}")
    return float(match.group(1) + match.group(2))

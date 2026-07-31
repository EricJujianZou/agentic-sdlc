"""Money handling.

Dollar amounts are held as whole cents everywhere inside the system, so
sums and line values can never drift by a fraction of a cent.  The
public surface still speaks dollars: prices go in and come out as
ordinary decimal numbers.

``format_money`` is the one place money turns into text.  An ``int``
amount is cents (``1999`` -> ``"$19.99"``); a ``float`` is dollars
(``3.5`` -> ``"$3.50"``).
"""

from decimal import ROUND_HALF_UP, Decimal


def to_cents(amount) -> int:
    """Convert a dollar amount to whole cents, rounding half up."""
    if isinstance(amount, int):
        return amount * 100
    quantized = (Decimal(str(amount)) * 100).quantize(Decimal("1"),
                                                      rounding=ROUND_HALF_UP)
    return int(quantized)


def to_dollars(cents: int) -> float:
    """Convert whole cents back to a dollar amount."""
    return int(cents) / 100


def format_money(amount) -> str:
    """Format an amount as ``$X.XX`` (``-$X.XX`` when negative).

    An ``int`` amount means cents, a ``float`` means dollars.
    """
    cents = amount if isinstance(amount, int) else to_cents(amount)
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}${cents // 100}.{cents % 100:02d}"

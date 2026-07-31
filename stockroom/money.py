"""The one place money is turned into text.

Every report used to spell its own amounts, so the same price could come
out as ``19.99`` in one column and ``19.990`` in the next.  Printing goes
through :func:`format_money` instead, so a figure looks the same wherever
it lands.
"""

from .models import to_cents


def format_money(amount: int | float) -> str:
    """Return an amount as a plain money string, e.g. ``"$19.99"``.

    Args:
        amount: whole cents when an ``int`` (``1999`` is ``"$19.99"``),
            dollars when a ``float`` (``3.5`` is ``"$3.50"``).

    Returns:
        The amount with a leading ``$``, exactly two decimals and no
        thousands separators.  A negative amount reads ``-$12.50``.
    """
    cents = amount if isinstance(amount, int) else to_cents(amount)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100}.{cents % 100:02d}"

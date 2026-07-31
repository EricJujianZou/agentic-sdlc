"""Data model for the stockroom package.

Three record types cover everything the app tracks:

* ``Item`` - a thing on the shelf, identified by its SKU.
* ``Supplier`` - somewhere we buy items from.
* ``Order`` - a purchase order for more of an item.

Each type has ``to_dict`` / ``from_dict`` helpers so the store can
serialise state to JSON without any extra machinery.  The dict shape is
what ends up on disk, so keep the keys stable -- and ``from_dict`` has to
read every shape we have ever written: plain integer quantities from
before warehouses, fractional dollars from before money moved to cents,
and dates typed without their leading zeros.
"""

from dataclasses import dataclass

from .dates import normalize_stored_date
from .money import to_cents, to_dollars

# Order lifecycle: an order starts out pending, then is either received
# (goods arrived and were added to stock) or cancelled.
STATUS_PENDING = "pending"
STATUS_RECEIVED = "received"
STATUS_CANCELLED = "cancelled"

# Items that were never filed under a shelf area land here.
DEFAULT_CATEGORY = "uncategorized"

# The original stockroom; stock with no warehouse of its own lives here.
MAIN_WAREHOUSE = "main"


def canonical_sku(sku: str) -> str:
    """SKUs are not case sensitive; we write and store them uppercase."""
    return str(sku).strip().upper()


def _price_entry(entry: dict) -> dict:
    """Normalize a stored price-history entry to whole cents."""
    if "old_cents" in entry or "new_cents" in entry:
        return {"date": normalize_stored_date(entry["date"]),
                "old_cents": int(entry.get("old_cents", 0)),
                "new_cents": int(entry.get("new_cents", 0))}
    return {"date": normalize_stored_date(entry["date"]),
            "old_cents": to_cents(entry.get("old", 0.0)),
            "new_cents": to_cents(entry.get("new", 0.0))}


class Item:
    """A single stocked item.

    Stock is held per warehouse, but the item still answers ``qty`` with
    the total across all of them, which is what reports and CSV exports
    have always meant.

    Attributes:
        sku: the stock keeping unit, our unique identifier for the item.
        name: human readable description.
        quantities: mapping of warehouse name -> units held there.
        unit_price_cents: what we pay per unit, in whole cents.
        unit_price: the same price as an ordinary dollar amount.
        supplier_id: id of the Supplier we buy this from, or None for
            items we do not reorder.
        category: shelf area the item lives in.
        last_actor: who last created or changed this item, if recorded.
    """

    def __init__(self, sku: str, name: str, qty: int = 0,
                 unit_price: float = 0.0, supplier_id: str | None = None,
                 category: str = DEFAULT_CATEGORY,
                 last_actor: str | None = None,
                 quantities: dict | None = None,
                 unit_price_cents: int | None = None,
                 price_history: list | None = None):
        self.sku = canonical_sku(sku)
        self.name = name
        self.quantities = {w: int(q) for w, q in (quantities or {}).items()}
        # A starting quantity lands in the main room.
        if qty or not self.quantities:
            self.quantities[MAIN_WAREHOUSE] = (
                self.quantities.get(MAIN_WAREHOUSE, 0) + int(qty))
        self.unit_price_cents = (to_cents(unit_price)
                                 if unit_price_cents is None
                                 else int(unit_price_cents))
        self.supplier_id = supplier_id
        self.category = category or DEFAULT_CATEGORY
        self.last_actor = last_actor
        # Each entry is {"date": ..., "old_cents": ..., "new_cents": ...}.
        self.price_history_cents = [dict(e) for e in (price_history or [])]

    def __repr__(self) -> str:
        return (f"Item(sku={self.sku!r}, name={self.name!r}, "
                f"quantities={self.quantities!r})")

    @property
    def qty(self) -> int:
        """Units on hand across every warehouse."""
        return sum(self.quantities.values())

    @property
    def unit_price(self) -> float:
        """What we pay per unit, in dollars."""
        return to_dollars(self.unit_price_cents)

    @unit_price.setter
    def unit_price(self, value) -> None:
        self.unit_price_cents = to_cents(value)

    @property
    def price_history(self) -> list[dict]:
        """Recorded price changes, with the amounts in dollars."""
        return [{"date": entry["date"],
                 "old": to_dollars(entry["old_cents"]),
                 "new": to_dollars(entry["new_cents"])}
                for entry in self.price_history_cents]

    def record_price(self, price_cents: int, date: str) -> None:
        """Set a new price, remembering what it was before."""
        self.price_history_cents.append({
            "date": date,
            "old_cents": self.unit_price_cents,
            "new_cents": int(price_cents),
        })
        self.unit_price_cents = int(price_cents)

    def qty_in(self, warehouse: str) -> int:
        """Units held in one warehouse (0 if it never held this item)."""
        return self.quantities.get(warehouse, 0)

    def set_qty(self, warehouse: str, qty: int) -> None:
        """Set the units held in one warehouse."""
        self.quantities[warehouse] = int(qty)

    def add_qty(self, warehouse: str, qty: int) -> None:
        """Add (or, with a negative qty, remove) units in one warehouse."""
        self.quantities[warehouse] = self.qty_in(warehouse) + int(qty)

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this item."""
        return {
            "sku": self.sku,
            "name": self.name,
            "qty": dict(self.quantities),
            "unit_price_cents": self.unit_price_cents,
            "supplier_id": self.supplier_id,
            "category": self.category,
            "last_actor": self.last_actor,
            "price_history": [dict(e) for e in self.price_history_cents],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Build an Item from a dict previously produced by to_dict.

        Files written before warehouses existed carry a plain integer
        quantity; all of that stock belongs to the main room.  Files
        written before money moved to cents carry fractional dollars.
        """
        stored_qty = data.get("qty", 0)
        if isinstance(stored_qty, dict):
            quantities, qty = stored_qty, 0
        else:
            quantities, qty = None, stored_qty
        if "unit_price_cents" in data:
            price_cents = int(data["unit_price_cents"])
        else:
            price_cents = to_cents(data.get("unit_price", 0.0))
        return cls(
            sku=data["sku"],
            name=data["name"],
            qty=qty,
            supplier_id=data.get("supplier_id"),
            category=data.get("category") or DEFAULT_CATEGORY,
            last_actor=data.get("last_actor"),
            quantities=quantities,
            unit_price_cents=price_cents,
            price_history=[_price_entry(e)
                           for e in data.get("price_history", [])],
        )


@dataclass
class Supplier:
    """A supplier we can order items from.

    Attributes:
        id: short handle used to reference the supplier from items.
        name: the supplier's business name.
        email: where purchase orders get sent.
        lead_time_days: how many days they typically take to deliver.
    """

    id: str
    name: str
    email: str
    lead_time_days: int = 0

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this supplier."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "lead_time_days": self.lead_time_days,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Supplier":
        """Build a Supplier from a dict previously produced by to_dict."""
        return cls(
            id=data["id"],
            name=data["name"],
            email=data.get("email", ""),
            lead_time_days=data.get("lead_time_days", 0),
        )


@dataclass
class Order:
    """A purchase order for one item.

    Attributes:
        id: small integer id, unique within the store.
        sku: the item being ordered.
        qty: how many units were ordered.
        date: the date the order was placed, as a string (whatever the
            user typed, normally YYYY-MM-DD).
        status: one of "pending", "received" or "cancelled".
        shipped_qty: units delivered so far; suppliers deliver an order
            in parts, and the order flips to received once this reaches
            the ordered quantity.
        received_date: the day the goods actually arrived, or None.
        supplier_id: who the order was placed with, or None.
        last_actor: who last created or changed this order, if recorded.
    """

    id: int
    sku: str
    qty: int
    date: str
    status: str = STATUS_PENDING
    shipped_qty: int = 0
    received_date: str | None = None
    supplier_id: str | None = None
    last_actor: str | None = None

    @property
    def outstanding(self) -> int:
        """Units still to be delivered on this order."""
        return self.qty - self.shipped_qty

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this order."""
        return {
            "id": self.id,
            "sku": self.sku,
            "qty": self.qty,
            "date": self.date,
            "status": self.status,
            "shipped_qty": self.shipped_qty,
            "received_date": self.received_date,
            "supplier_id": self.supplier_id,
            "last_actor": self.last_actor,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        """Build an Order from a dict previously produced by to_dict."""
        return cls(
            id=data["id"],
            sku=data["sku"],
            qty=data["qty"],
            date=normalize_stored_date(data["date"]),
            status=data.get("status", STATUS_PENDING),
            shipped_qty=data.get("shipped_qty", 0),
            received_date=normalize_stored_date(data.get("received_date")),
            supplier_id=data.get("supplier_id"),
            last_actor=data.get("last_actor"),
        )

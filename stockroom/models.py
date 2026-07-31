"""Data model for the stockroom package.

Three record types cover everything the app tracks:

* ``Item`` - a thing on the shelf, identified by its SKU.
* ``Supplier`` - somewhere we buy items from.
* ``Order`` - a purchase order for more of an item.

Each type is a small dataclass with ``to_dict`` / ``from_dict`` helpers so
the store can serialise state to JSON without any extra machinery.  The
dict shape is exactly what ends up on disk, so keep the keys stable.
"""

from dataclasses import dataclass

# Order lifecycle: an order starts out pending, then is either received
# (goods arrived and were added to stock) or cancelled.
STATUS_PENDING = "pending"
STATUS_RECEIVED = "received"
STATUS_CANCELLED = "cancelled"

# Shelf area an item lives in.  Items created without one land here.
DEFAULT_CATEGORY = "uncategorized"


def normalize_sku(sku: str) -> str:
    """Return the canonical spelling of a SKU.

    SKUs are not case sensitive - ``wid-1`` is the same item as ``WID-1``
    - and we write ours in upper case, so that is the spelling we store
    and show.  Suppliers whose exports lower case (or mix) the spelling
    land on the same item instead of a near-duplicate.
    """
    return sku.upper()


@dataclass
class Item:
    """A single stocked item.

    Attributes:
        sku: the stock keeping unit, our unique identifier for the item.
        name: human readable description.
        qty: number of units currently on hand.
        unit_price: what we pay per unit, in dollars.
        supplier_id: id of the Supplier we buy this from, or None for
            items we do not reorder.
        category: shelf area the item belongs to.
    """

    sku: str
    name: str
    qty: int = 0
    unit_price: float = 0.0
    supplier_id: str | None = None
    category: str = DEFAULT_CATEGORY

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this item."""
        return {
            "sku": self.sku,
            "name": self.name,
            "qty": self.qty,
            "unit_price": self.unit_price,
            "supplier_id": self.supplier_id,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Build an Item from a dict previously produced by to_dict."""
        return cls(
            sku=data["sku"],
            name=data["name"],
            qty=data.get("qty", 0),
            unit_price=data.get("unit_price", 0.0),
            supplier_id=data.get("supplier_id"),
            category=data.get("category") or DEFAULT_CATEGORY,
        )


@dataclass
class Supplier:
    """A supplier we can order items from.

    Attributes:
        id: short handle used to reference the supplier from items.
        name: the supplier's business name.
        email: where purchase orders get sent.
        lead_time_days: whole days between placing an order and the goods
            turning up.
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
    """

    id: int
    sku: str
    qty: int
    date: str
    status: str = STATUS_PENDING

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this order."""
        return {
            "id": self.id,
            "sku": self.sku,
            "qty": self.qty,
            "date": self.date,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        """Build an Order from a dict previously produced by to_dict."""
        return cls(
            id=data["id"],
            sku=data["sku"],
            qty=data["qty"],
            date=data["date"],
            status=data.get("status", STATUS_PENDING),
        )

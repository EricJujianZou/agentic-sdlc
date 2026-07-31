"""Data model for the stockroom package.

Three record types cover everything the app tracks:

* ``Item`` - a thing on the shelf, identified by its SKU.
* ``Supplier`` - somewhere we buy items from.
* ``Order`` - a purchase order for more of an item.

Each type is a small dataclass with ``to_dict`` / ``from_dict`` helpers so
the store can serialise state to JSON without any extra machinery.  The
dict shape is exactly what ends up on disk, so keep the keys stable.
"""

from dataclasses import dataclass, field

# Order lifecycle: an order starts out pending, then is either received
# (goods arrived and were added to stock) or cancelled.
STATUS_PENDING = "pending"
STATUS_RECEIVED = "received"
STATUS_CANCELLED = "cancelled"

# Shelf area an item lives in.  Items created without one land here.
DEFAULT_CATEGORY = "uncategorized"

# Room the stock physically sits in.  Stock that arrives without a
# warehouse named - and all stock in state files written before we rented
# the second room - lives here.
DEFAULT_WAREHOUSE = "main"


def normalize_sku(sku: str) -> str:
    """Return the canonical spelling of a SKU.

    SKUs are not case sensitive - ``wid-1`` is the same item as ``WID-1``
    - and we write ours in upper case, so that is the spelling we store
    and show.  Suppliers whose exports lower case (or mix) the spelling
    land on the same item instead of a near-duplicate.
    """
    return sku.upper()


def record_actor(record, actor: str | None) -> None:
    """Note who last changed an item or order.

    Commands pass the ``--actor`` name through; when one was given it
    overwrites whatever was there, so ``last_actor`` always names the
    most recent change.  Without a name the record is left alone.
    """
    if actor is not None:
        record.last_actor = actor


@dataclass
class Item:
    """A single stocked item.

    Stock is tracked per warehouse in ``quantities``; that mapping is the
    source of truth and ``qty`` is the total across all of them, kept up
    to date by the methods below.  Everything that thinks in totals
    (reports, CSV export) can go on reading ``qty``.

    Attributes:
        sku: the stock keeping unit, our unique identifier for the item.
        name: human readable description.
        qty: number of units currently on hand, across all warehouses.
            Passed to the constructor as the starting stock, which lands
            in ``DEFAULT_WAREHOUSE``.
        unit_price: what we pay per unit, in dollars.
        supplier_id: id of the Supplier we buy this from, or None for
            items we do not reorder.
        category: shelf area the item belongs to.
        last_actor: name of whoever last changed this item, or None if
            no change has been made with an actor named.
        quantities: units on hand per warehouse name.
    """

    sku: str
    name: str
    qty: int = 0
    unit_price: float = 0.0
    supplier_id: str | None = None
    category: str = DEFAULT_CATEGORY
    last_actor: str | None = None
    quantities: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Seed the breakdown, then make ``qty`` agree with it.

        An item built without one - ``Item(qty=5)``, or a state file
        from before warehouses existed - starts with all its stock in
        the default warehouse.
        """
        if not self.quantities:
            self.quantities = {DEFAULT_WAREHOUSE: self.qty}
        self.qty = sum(self.quantities.values())

    def qty_in(self, warehouse: str) -> int:
        """Units on hand in one warehouse (0 if it never held this item)."""
        return self.quantities.get(warehouse, 0)

    def adjust(self, qty: int, warehouse: str = DEFAULT_WAREHOUSE) -> None:
        """Add ``qty`` units to one warehouse (negative to take them out)."""
        self.quantities[warehouse] = self.qty_in(warehouse) + qty
        self.qty = sum(self.quantities.values())

    def set_stock(self, qty: int, warehouse: str = DEFAULT_WAREHOUSE) -> None:
        """Replace all stock of this item with ``qty`` units in one warehouse.

        A CSV row carries one total and no idea of where the goods sit,
        so importing one puts the whole count in the default warehouse.
        """
        self.quantities = {warehouse: qty}
        self.qty = qty

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this item."""
        return {
            "sku": self.sku,
            "name": self.name,
            "qty": dict(self.quantities),
            "unit_price": self.unit_price,
            "supplier_id": self.supplier_id,
            "category": self.category,
            "last_actor": self.last_actor,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Build an Item from a dict previously produced by to_dict.

        ``qty`` is a per-warehouse mapping in the current layout and a
        plain total in files written before warehouses existed; a total
        is read as that many units in the default warehouse.
        """
        stored_qty = data.get("qty", 0)
        quantities = dict(stored_qty) if isinstance(stored_qty, dict) else {}
        return cls(
            sku=data["sku"],
            name=data["name"],
            qty=0 if quantities else stored_qty,
            unit_price=data.get("unit_price", 0.0),
            supplier_id=data.get("supplier_id"),
            category=data.get("category") or DEFAULT_CATEGORY,
            last_actor=data.get("last_actor"),
            quantities=quantities,
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
        skus: the supplier's catalogue - the SKUs they told us they can
            supply, in canonical spelling.
    """

    id: str
    name: str
    email: str
    lead_time_days: int = 0
    skus: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this supplier."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "lead_time_days": self.lead_time_days,
            "skus": list(self.skus),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Supplier":
        """Build a Supplier from a dict previously produced by to_dict.

        Suppliers written before catalogues existed have not sent us one
        yet, so theirs is empty.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            email=data.get("email", ""),
            lead_time_days=data.get("lead_time_days", 0),
            skus=list(data.get("skus", [])),
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
        supplier_id: id of the Supplier the order was placed with, or
            None when we could not work out who supplies the item.
        last_actor: name of whoever last changed this order, or None if
            no change has been made with an actor named.
        shipped_qty: units of the order delivered so far.  Suppliers
            deliver in parts, so this climbs from 0 to ``qty`` over one
            or more deliveries; the order is received once it gets
            there.
    """

    id: int
    sku: str
    qty: int
    date: str
    status: str = STATUS_PENDING
    supplier_id: str | None = None
    last_actor: str | None = None
    shipped_qty: int = 0

    @property
    def outstanding(self) -> int:
        """Units of this order still to be delivered."""
        return self.qty - self.shipped_qty

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this order."""
        return {
            "id": self.id,
            "sku": self.sku,
            "qty": self.qty,
            "date": self.date,
            "status": self.status,
            "supplier_id": self.supplier_id,
            "last_actor": self.last_actor,
            "shipped_qty": self.shipped_qty,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        """Build an Order from a dict previously produced by to_dict.

        Orders written before deliveries could be split carry no
        ``shipped_qty``; a pending one of those has had nothing
        delivered, and a received one arrived whole.
        """
        status = data.get("status", STATUS_PENDING)
        default_shipped = data["qty"] if status == STATUS_RECEIVED else 0
        return cls(
            id=data["id"],
            sku=data["sku"],
            qty=data["qty"],
            date=data["date"],
            status=status,
            supplier_id=data.get("supplier_id"),
            last_actor=data.get("last_actor"),
            shipped_qty=data.get("shipped_qty", default_shipped),
        )

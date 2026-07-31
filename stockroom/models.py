"""Data model for the stockroom package.

Four record types cover everything the app tracks:

* ``Item`` - a thing on the shelf, identified by its SKU.
* ``Supplier`` - somewhere we buy items from.
* ``Order`` - a purchase order for more of an item.
* ``Shipment`` - units of an item sent out of the stockroom.

Each type is a small dataclass with ``to_dict`` / ``from_dict`` helpers so
the store can serialise state to JSON without any extra machinery.  The
dict shape is exactly what ends up on disk, so keep the keys stable.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from .dates import normalize_stored

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


def to_cents(dollars: float) -> int:
    """Return a dollar amount as a whole number of cents.

    Money is held in cents everywhere inside the system: a fraction of a
    dollar has no exact binary form, so keeping dollars around lets a
    long column of them drift off what the same sum does on paper.
    Dollars are what people type and read, so they are converted the
    moment they arrive - through the decimal spelling of the amount, and
    rounding a half cent up, the way a till does.
    """
    cents = Decimal(str(dollars)) * 100
    return int(cents.to_integral_value(rounding=ROUND_HALF_UP))


def to_dollars(cents: int) -> float:
    """Return whole cents as a dollar amount, for showing and reporting."""
    return cents / 100


def percent_of(cents: int, percent: float) -> int:
    """Return ``percent`` of an amount of cents, as whole cents.

    Rates land on fractions of a cent all the time - 5% of $17.55 is
    87.75 - and money only comes in whole ones, so the result is rounded
    half up, the way a till does.  Working from cents rather than
    dollars keeps a breakdown adding up to its own total.
    """
    share = Decimal(cents) * Decimal(str(percent)) / 100
    return int(share.to_integral_value(rounding=ROUND_HALF_UP))


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
        unit_price_cents: what we pay per unit, in whole cents.  This is
            the figure the item actually holds and the one all money
            arithmetic uses.
        unit_price: the same price in dollars.  Reading and writing it
            (including ``Item(unit_price=3.5)``) goes through the cents
            above, so an item never holds a fraction of a cent.
        supplier_id: id of the Supplier we buy this from, or None for
            items we do not reorder.
        category: shelf area the item belongs to.
        last_actor: name of whoever last changed this item, or None if
            no change has been made with an actor named.
        quantities: units on hand per warehouse name.
        price_history: one entry per price change, oldest first, each a
            dict of date / old price / new price, the prices in dollars.
            An item whose price has never been changed has an empty
            history.
    """

    sku: str
    name: str
    qty: int = 0
    unit_price: float = 0.0
    supplier_id: str | None = None
    category: str = DEFAULT_CATEGORY
    last_actor: str | None = None
    quantities: dict[str, int] = field(default_factory=dict)
    price_history: list[dict] = field(default_factory=list)

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

    def set_warehouse_stock(
        self, qty: int, warehouse: str = DEFAULT_WAREHOUSE
    ) -> None:
        """Set one warehouse's count, leaving the other warehouses alone.

        A CSV row that names its warehouse only speaks for that room, so
        several rows for one SKU build the breakdown up between them.
        """
        self.quantities[warehouse] = qty
        self.qty = sum(self.quantities.values())

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this item.

        Prices go to disk as whole cents - ``unit_price_cents`` and, on
        each history entry, ``old_cents`` / ``new_cents`` - so a state
        file holds no fractional amount either.
        """
        return {
            "sku": self.sku,
            "name": self.name,
            "qty": dict(self.quantities),
            "unit_price_cents": self.unit_price_cents,
            "supplier_id": self.supplier_id,
            "category": self.category,
            "last_actor": self.last_actor,
            "price_history": [
                {
                    "date": entry["date"],
                    "old_cents": to_cents(entry["old"]),
                    "new_cents": to_cents(entry["new"]),
                }
                for entry in self.price_history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Build an Item from a dict previously produced by to_dict.

        ``qty`` is a per-warehouse mapping in the current layout and a
        plain total in files written before warehouses existed; a total
        is read as that many units in the default warehouse.  Items
        written before prices were tracked have no history, which is
        simply an empty one.  Prices are stored as whole cents; files
        written before that carry them as fractional dollars, which are
        converted on the way in.
        """
        stored_qty = data.get("qty", 0)
        quantities = dict(stored_qty) if isinstance(stored_qty, dict) else {}
        item = cls(
            sku=data["sku"],
            name=data["name"],
            qty=0 if quantities else stored_qty,
            supplier_id=data.get("supplier_id"),
            category=data.get("category") or DEFAULT_CATEGORY,
            last_actor=data.get("last_actor"),
            quantities=quantities,
            price_history=[_price_change_from_dict(entry)
                           for entry in data.get("price_history", [])],
        )
        if "unit_price_cents" in data:
            item.unit_price_cents = int(data["unit_price_cents"])
        else:
            item.unit_price = data.get("unit_price", 0.0)
        return item


def _read_unit_price(item: Item) -> float:
    """The unit price in dollars, worked out from the cents held."""
    return to_dollars(item.unit_price_cents)


def _write_unit_price(item: Item, dollars: float) -> None:
    """Set the unit price from a dollar amount, holding it as cents."""
    item.unit_price_cents = to_cents(dollars)


#: ``unit_price`` stays an ordinary field of the dataclass - so
#: ``Item(unit_price=3.5)`` and ``item.unit_price`` still speak dollars -
#: but nothing is kept behind it: this property turns every read and write
#: into ``unit_price_cents``, which is what the item holds.  It is attached
#: after the decorator has run so the field keeps its plain 0.0 default.
Item.unit_price = property(_read_unit_price, _write_unit_price)


def _price_change_from_dict(entry: dict) -> dict:
    """Read one stored price-change entry, in dollars.

    Entries record whole cents (``old_cents`` / ``new_cents``); ones
    written before that carry fractional dollars under ``old`` / ``new``
    and are taken as they are.  The date is normalized either way, so a
    change stored as "2026-1-5" reports as "2026-01-05".
    """
    if "old_cents" in entry:
        return {
            "date": normalize_stored(entry["date"]),
            "old": to_dollars(entry["old_cents"]),
            "new": to_dollars(entry["new_cents"]),
        }
    change = dict(entry)
    change["date"] = normalize_stored(change.get("date"))
    return change


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
class Shipment:
    """Units of one item sent out of the stockroom.

    Stock levels say what is sitting still; the shipment log says what
    actually moved out, so reports can look at turnover over time.  Only
    goods leaving the building are recorded here - walking stock between
    warehouses is an internal move, and receiving is the opposite
    direction entirely.

    Attributes:
        sku: the item that went out.
        qty: how many units went.
        warehouse: the room they were picked from.
        date: the day they went out, as a ``YYYY-MM-DD`` string.
    """

    sku: str
    qty: int
    warehouse: str = DEFAULT_WAREHOUSE
    date: str = ""

    def to_dict(self) -> dict:
        """Return a JSON-ready dict for this shipment."""
        return {
            "sku": self.sku,
            "qty": self.qty,
            "warehouse": self.warehouse,
            "date": self.date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Shipment":
        """Build a Shipment from a dict previously produced by to_dict.

        A date stored unpadded is read back in the canonical spelling.
        """
        return cls(
            sku=data["sku"],
            qty=data["qty"],
            warehouse=data.get("warehouse", DEFAULT_WAREHOUSE),
            date=normalize_stored(data.get("date", "")),
        )


@dataclass
class Order:
    """A purchase order for one item.

    Attributes:
        id: small integer id, unique within the store.
        sku: the item being ordered.
        qty: how many units were ordered.
        date: the date the order was placed, as a ``YYYY-MM-DD`` string.
        status: one of "pending", "received" or "cancelled".
        supplier_id: id of the Supplier the order was placed with, or
            None when we could not work out who supplies the item.
        last_actor: name of whoever last changed this order, or None if
            no change has been made with an actor named.
        shipped_qty: units of the order delivered so far.  Suppliers
            deliver in parts, so this climbs from 0 to ``qty`` over one
            or more deliveries; the order is received once it gets
            there.
        received_date: the day the goods actually turned up, as a
            ``YYYY-MM-DD`` string, or None for an order that has not
            arrived - or one received before we started noting the day.
    """

    id: int
    sku: str
    qty: int
    date: str
    status: str = STATUS_PENDING
    supplier_id: str | None = None
    last_actor: str | None = None
    shipped_qty: int = 0
    received_date: str | None = None

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
            "received_date": self.received_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        """Build an Order from a dict previously produced by to_dict.

        Orders written before deliveries could be split carry no
        ``shipped_qty``; a pending one of those has had nothing
        delivered, and a received one arrived whole.  Ones written
        before arrival days were noted carry no ``received_date``, so we
        do not know when they turned up.  Dates stored unpadded, as they
        were typed, are read back in the canonical spelling.
        """
        status = data.get("status", STATUS_PENDING)
        default_shipped = data["qty"] if status == STATUS_RECEIVED else 0
        return cls(
            id=data["id"],
            sku=data["sku"],
            qty=data["qty"],
            date=normalize_stored(data["date"]),
            status=status,
            supplier_id=data.get("supplier_id"),
            last_actor=data.get("last_actor"),
            shipped_qty=data.get("shipped_qty", default_shipped),
            received_date=normalize_stored(data.get("received_date")),
        )

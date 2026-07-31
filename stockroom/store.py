"""Persistence and business operations for the stockroom.

The whole application state lives in one JSON file, stamped with the
schema version it was written by::

    {
        "version":   4,
        "items":     {sku: {...}, ...},
        "suppliers": {supplier_id: {...}, ...},
        "orders":    [{...}, ...],
        "shipments": [{...}, ...],
        "discounts": {category: percent, ...},
        "tax_rate":  percent
    }

Version 4 keeps every price as a whole number of cents; version 3 and
earlier wrote fractional dollars.  Version 3 broke each item's ``qty``
down per warehouse; version 2 and the original unversioned layout
(version 1, no ``"version"`` key) store it as one total.  All of them
still load - their prices are converted and their stock lands in the
default warehouse - and are rewritten in the current layout the next
time state is saved.

``Store`` loads that file into dataclasses, lets callers mutate the state
through simple methods, and writes it back out with ``save()``.  All the
"business rules" (such as they are) live here too, so the CLI stays a
thin layer of argument parsing and printing.

Errors are reported by raising ``ValueError`` with a human readable
message; the CLI turns those into exit code 1.
"""

import datetime
import json
import os
import shutil

from .models import (
    DEFAULT_CATEGORY,
    DEFAULT_WAREHOUSE,
    Item,
    Order,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_RECEIVED,
    Shipment,
    Supplier,
    normalize_sku,
    record_actor,
)

#: Schema version stamped into every state file we write.  Version 1 is
#: the original unversioned layout, which carries no ``"version"`` key.
SCHEMA_VERSION = 4

#: What separates the state file's name from a backup's timestamp.
BACKUP_SUFFIX = ".bak-"


def _backup_stamp() -> str:
    """Timestamp for a backup name: sortable, and legal in a filename.

    No colons (Windows refuses them), so this is safe on any OS, and the
    fields run big-endian, so sorting the names sorts them by age.  The
    microseconds are there to keep two backups a moment apart distinct.
    """
    return datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")


class Store:
    """Holds the full application state and knows how to load/save it.

    Attributes:
        path: the JSON file backing this store.
        items: mapping of SKU -> Item.
        suppliers: mapping of supplier id -> Supplier.
        orders: list of Order, in the order they were placed.
        shipments: list of Shipment, in the order they went out.
        discounts: mapping of category -> discount percent.
        tax_rate: the flat sales tax percent charged on an order.
    """

    def __init__(self, path: str):
        self.path = path
        self.items: dict[str, Item] = {}
        self.suppliers: dict[str, Supplier] = {}
        self.orders: list[Order] = []
        self.shipments: list[Shipment] = []
        self.discounts: dict[str, float] = {}
        self.tax_rate: float = 0.0

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Read state from the JSON file.

        A missing file just means a fresh, empty store.  A file that is
        not valid JSON raises ``json.JSONDecodeError`` for the caller to
        deal with.  Older layouts (version 2, and version 1 - which
        carries no ``"version"`` key) are read the same way; the item
        records themselves know how to read an older quantity.  A file
        written before shipments were logged has none, which is simply
        an empty log, and one written before discounts were negotiated
        has no rules and no tax.
        """
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            raw = json.load(f)
        self.items = {
            sku: Item.from_dict(data) for sku, data in raw.get("items", {}).items()
        }
        self.suppliers = {
            sid: Supplier.from_dict(data)
            for sid, data in raw.get("suppliers", {}).items()
        }
        self.orders = [Order.from_dict(data) for data in raw.get("orders", [])]
        self.shipments = [
            Shipment.from_dict(data) for data in raw.get("shipments", [])
        ]
        self.discounts = {
            category: float(percent)
            for category, percent in raw.get("discounts", {}).items()
        }
        self.tax_rate = float(raw.get("tax_rate", 0.0))

    def save(self) -> None:
        """Write the current state back to the JSON file.

        The file always declares the schema version it was written by.
        """
        self._write(self.path)

    def _write(self, path: str) -> None:
        """Serialize the current state to ``path`` in the current layout."""
        raw = {
            "version": SCHEMA_VERSION,
            "items": {sku: item.to_dict() for sku, item in self.items.items()},
            "suppliers": {sid: s.to_dict() for sid, s in self.suppliers.items()},
            "orders": [order.to_dict() for order in self.orders],
            "shipments": [s.to_dict() for s in self.shipments],
            "discounts": dict(self.discounts),
            "tax_rate": self.tax_rate,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
            f.write("\n")

    # ------------------------------------------------------------------
    # backups
    # ------------------------------------------------------------------

    def _backup_dir(self) -> str:
        """The directory backups live in - the state file's own."""
        return os.path.dirname(self.path) or "."

    def _backup_prefix(self) -> str:
        """What every backup name for this state file starts with."""
        return os.path.basename(self.path) + BACKUP_SUFFIX

    def backup(self) -> str:
        """Snapshot the current state beside the state file.

        Returns the backup's name (not its full path) - the same name
        ``list_backups`` reports and ``restore`` takes.
        """
        name = self._backup_prefix() + _backup_stamp()
        self._write(os.path.join(self._backup_dir(), name))
        return name

    def list_backups(self) -> list[str]:
        """The existing backup names, oldest first.

        The stamp sorts the same way it ages, so plain name order is age
        order.  Having no backups at all is not a problem, just an empty
        list.
        """
        directory = self._backup_dir()
        if not os.path.isdir(directory):
            return []
        prefix = self._backup_prefix()
        return sorted(name for name in os.listdir(directory)
                      if name.startswith(prefix))

    def restore(self, name: str) -> str:
        """Put the state back to what the named backup captured.

        A name that is not one of ours is refused with ``ValueError``
        before anything is written, so a typo cannot cost you the state
        you were trying to protect.  On success the state file *is* the
        backup, and this store is reloaded from it.
        """
        if name not in self.list_backups():
            raise ValueError(f"unknown backup {name}")
        shutil.copyfile(os.path.join(self._backup_dir(), name), self.path)
        self.load()
        return name

    # ------------------------------------------------------------------
    # items
    # ------------------------------------------------------------------

    def add_item(
        self,
        sku: str,
        name: str,
        qty: int = 0,
        unit_price: float = 0.0,
        supplier_id: str | None = None,
        category: str = DEFAULT_CATEGORY,
        actor: str | None = None,
    ) -> Item:
        """Create a new item.

        The SKU must not already exist, and if a supplier is given it
        must be one we know about.  SKUs are stored in their canonical
        (upper case) spelling.  ``actor``, when given, is recorded as
        the item's last actor.
        """
        sku = normalize_sku(sku)
        if sku in self.items:
            raise ValueError(f"item {sku} already exists")
        if supplier_id is not None and supplier_id not in self.suppliers:
            raise ValueError(f"unknown supplier {supplier_id}")
        item = Item(sku=sku, name=name, qty=qty, unit_price=unit_price,
                    supplier_id=supplier_id,
                    category=category or DEFAULT_CATEGORY)
        record_actor(item, actor)
        self.items[sku] = item
        return item

    def get_item(self, sku: str) -> Item:
        """Look up an item by SKU (any case) or raise ValueError."""
        sku = normalize_sku(sku)
        if sku not in self.items:
            raise ValueError(f"unknown item {sku}")
        return self.items[sku]

    def list_items(self) -> list[Item]:
        """All items, sorted by SKU for stable output."""
        return [self.items[sku] for sku in sorted(self.items)]

    def receive(self, sku: str, qty: int, warehouse: str = DEFAULT_WAREHOUSE,
                actor: str | None = None) -> Item:
        """Add ``qty`` units of an item to one warehouse (goods arrived)."""
        item = self.get_item(sku)
        item.adjust(qty, warehouse)
        record_actor(item, actor)
        return item

    def ship(self, sku: str, qty: int, warehouse: str = DEFAULT_WAREHOUSE,
             actor: str | None = None, date: str | None = None) -> Item:
        """Remove ``qty`` units from one warehouse (goods sent out).

        The shelf cannot go negative: shipping more than that warehouse
        holds raises ``ValueError`` and leaves the item untouched - what
        sits in the other room is no help loading this van.  Shipping
        exactly the on-hand quantity is fine.

        Every shipment that does go out is written to the shipment log,
        dated ``date`` or today when no date is given, so reports can
        tell movement from mere stock levels later on.
        """
        item = self.get_item(sku)
        on_hand = item.qty_in(warehouse)
        if qty > on_hand:
            raise ValueError(
                f"cannot ship {qty} x {sku}: only {on_hand} on hand"
            )
        item.adjust(-qty, warehouse)
        record_actor(item, actor)
        if date is None:
            date = datetime.date.today().isoformat()
        self.shipments.append(
            Shipment(sku=item.sku, qty=qty, warehouse=warehouse, date=date)
        )
        return item

    def set_price(self, sku: str, price: float, date: str | None = None,
                  actor: str | None = None) -> Item:
        """Change what an item costs per unit, and remember the change.

        The old and new price are noted on the item's ``price_history``,
        dated ``date`` or today when no date is given, so a report can
        say later what anything cost at the time.  The history records
        the price the item ended up holding, rounded to whole cents,
        rather than whatever was typed.
        """
        item = self.get_item(sku)
        if date is None:
            date = datetime.date.today().isoformat()
        old_price = item.unit_price
        item.unit_price = price
        item.price_history.append({
            "date": date,
            "old": old_price,
            "new": item.unit_price,
        })
        record_actor(item, actor)
        return item

    def transfer(self, sku: str, qty: int, src: str, dst: str,
                 actor: str | None = None) -> Item:
        """Walk ``qty`` units of an item from one warehouse to another.

        You cannot move more than the source room actually holds: an
        overdraw raises ``ValueError`` before anything moves, same as
        shipping below zero.  A successful transfer touches only the two
        warehouses named - the item's total is unchanged.
        """
        item = self.get_item(sku)
        on_hand = item.qty_in(src)
        if qty > on_hand:
            raise ValueError(
                f"cannot transfer {qty} x {sku} out of {src}: "
                f"only {on_hand} on hand"
            )
        item.adjust(-qty, src)
        item.adjust(qty, dst)
        record_actor(item, actor)
        return item

    # ------------------------------------------------------------------
    # discounts
    # ------------------------------------------------------------------

    def set_discount(self, category: str, percent: float) -> float:
        """Set (or replace) the discount rule for a category.

        A percent is anything from 0 to 100, fractions included; a rate
        outside that raises ``ValueError`` and leaves the old rule - if
        any - alone.  Categories the store has no items in are fine: a
        rule can be negotiated before the first delivery.
        """
        if not 0 <= percent <= 100:
            raise ValueError(
                f"discount for {category} must be between 0 and 100, "
                f"not {percent}"
            )
        self.discounts[category] = float(percent)
        return self.discounts[category]

    def get_discount(self, category: str) -> float:
        """The discount percent for a category - 0 when there is no rule."""
        return self.discounts.get(category, 0.0)

    def list_discounts(self) -> list[tuple[str, float]]:
        """Every rule as (category, percent) pairs, sorted by category."""
        return [(category, self.discounts[category])
                for category in sorted(self.discounts)]

    def remove_discount(self, category: str) -> float:
        """Drop a category's discount rule and return what it was.

        Removing a category that has no rule raises ``ValueError``: it
        is more likely a typo than a no-op worth being quiet about.
        """
        if category not in self.discounts:
            raise ValueError(f"no discount rule for {category}")
        return self.discounts.pop(category)

    def set_tax_rate(self, percent: float) -> float:
        """Set the flat tax percent charged on an order.

        Every order is taxed at the same rate, so this is one setting
        rather than a rule per category.  A negative rate is refused
        with ``ValueError`` - that would be a rebate, not a tax - and
        leaves the old rate alone.
        """
        if percent < 0:
            raise ValueError(f"tax rate must not be negative, not {percent}")
        self.tax_rate = float(percent)
        return self.tax_rate

    # ------------------------------------------------------------------
    # suppliers
    # ------------------------------------------------------------------

    def add_supplier(self, supplier_id: str, name: str, email: str,
                     lead_time_days: int = 0) -> Supplier:
        """Create a new supplier.  The id must not already exist."""
        if supplier_id in self.suppliers:
            raise ValueError(f"supplier {supplier_id} already exists")
        supplier = Supplier(id=supplier_id, name=name, email=email,
                            lead_time_days=lead_time_days)
        self.suppliers[supplier_id] = supplier
        return supplier

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Look up a supplier by id or raise ValueError."""
        if supplier_id not in self.suppliers:
            raise ValueError(f"unknown supplier {supplier_id}")
        return self.suppliers[supplier_id]

    def list_suppliers(self) -> list[Supplier]:
        """All suppliers, sorted by id for stable output."""
        return [self.suppliers[sid] for sid in sorted(self.suppliers)]

    def add_supplier_sku(self, supplier_id: str, sku: str) -> Supplier:
        """Note that a supplier can supply a SKU.

        The supplier must be one we know about; the SKU need not be an
        item we stock, since a catalogue is the supplier's list, not
        ours.  Listing the same SKU twice changes nothing.
        """
        supplier = self.get_supplier(supplier_id)
        sku = normalize_sku(sku)
        if sku not in supplier.skus:
            supplier.skus.append(sku)
        return supplier

    def catalog_skus(self, supplier_id: str) -> list[str]:
        """The SKUs one supplier's catalogue lists, sorted."""
        return sorted(self.get_supplier(supplier_id).skus)

    def suppliers_for(self, sku: str) -> list[str]:
        """Ids of the suppliers whose catalogue lists a SKU, sorted."""
        sku = normalize_sku(sku)
        return sorted(sid for sid, supplier in self.suppliers.items()
                      if sku in supplier.skus)

    # ------------------------------------------------------------------
    # orders
    # ------------------------------------------------------------------

    def next_order_id(self) -> int:
        """Return the next free order id (ids are small integers)."""
        if not self.orders:
            return 1
        return max(order.id for order in self.orders) + 1

    def place_order(self, sku: str, qty: int, date: str,
                    supplier_id: str | None = None,
                    actor: str | None = None) -> Order:
        """Record a new pending purchase order for an existing item.

        ``date`` is stored as given; the CLI defaults it to today when
        the user does not pass one.  The order remembers who it was
        placed with - ``supplier_id`` when one is named, otherwise
        whoever ``_order_supplier`` works out.
        """
        item = self.get_item(sku)  # validates the SKU
        if supplier_id is not None:
            self.get_supplier(supplier_id)  # validates the supplier
        else:
            supplier_id = self._order_supplier(item)
        order = Order(id=self.next_order_id(), sku=item.sku, qty=qty, date=date,
                      supplier_id=supplier_id)
        record_actor(order, actor)
        self.orders.append(order)
        return order

    def _order_supplier(self, item: Item) -> str | None:
        """Work out who to order an item from when nobody said.

        One catalogue listing the SKU settles it.  Several is a real
        choice - which one gets the business is not ours to guess - so
        it raises ``ValueError`` and the caller has to name one.  With
        no catalogue listing it we fall back to the item's own supplier,
        which may be nobody.
        """
        candidates = self.suppliers_for(item.sku)
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            raise ValueError(
                f"several suppliers list {item.sku} "
                f"({', '.join(candidates)}): pass --supplier"
            )
        return item.supplier_id

    def get_order(self, order_id: int) -> Order:
        """Look up an order by id or raise ValueError."""
        for order in self.orders:
            if order.id == order_id:
                return order
        raise ValueError(f"unknown order {order_id}")

    def ship_order(self, order_id: int, qty: int,
                   actor: str | None = None) -> Order:
        """Book ``qty`` units of a pending order arriving.

        Suppliers deliver an order in parts, so this puts one delivery
        into stock and adds it to the order's running ``shipped_qty``.
        The order stays pending while any of it is outstanding and
        becomes received the moment the last unit lands.

        A delivery has to be at least one unit and cannot be for more
        than is still outstanding, and only a pending order can take one
        at all; either way ``ValueError`` is raised before anything is
        booked.
        """
        order = self.get_order(order_id)
        self._require_pending(order, "deliver")
        if qty < 1 or qty > order.outstanding:
            raise ValueError(
                f"cannot deliver {qty} x {order.sku} against order "
                f"{order.id}: {order.outstanding} outstanding"
            )
        self._book_delivery(order, qty, actor)
        return order

    def receive_order(self, order_id: int, actor: str | None = None,
                      date: str | None = None) -> Order:
        """Mark a pending order received: the rest of it just arrived.

        Only what is still outstanding goes into stock, so receiving an
        order that has already had part of it delivered tops the item up
        rather than counting the delivered units twice.

        ``date`` is the day the goods turned up, today when no date is
        given; it is what the on-time report measures the supplier
        against, so it is worth passing when booking in a late delivery
        after the fact.

        Only a pending order can be received; receiving an already
        received or cancelled one raises ``ValueError`` and adds nothing
        to stock.
        """
        order = self.get_order(order_id)
        self._require_pending(order, "receive")
        self._book_delivery(order, order.outstanding, actor, date)
        return order

    def _book_delivery(self, order: Order, qty: int, actor: str | None,
                       date: str | None = None) -> None:
        """Put ``qty`` of an order's goods on the shelf and note it down.

        Deliveries are booked into the default warehouse, and the order
        is received once every unit ordered has turned up - which is the
        moment the arrival day is settled, so that is where it is
        stamped on, dated ``date`` or today when no date is given.  Both
        the order and the restocked item record the actor, since both
        change.
        """
        order.shipped_qty += qty
        if order.outstanding <= 0:
            order.status = STATUS_RECEIVED
            order.received_date = (date if date is not None
                                   else datetime.date.today().isoformat())
        record_actor(order, actor)
        item = self.get_item(order.sku)
        item.adjust(qty)
        record_actor(item, actor)

    def cancel_order(self, order_id: int, actor: str | None = None) -> Order:
        """Mark a pending order cancelled.  Stock is not affected.

        Only a pending order can be cancelled; cancelling an already
        received or cancelled one raises ``ValueError`` and leaves the
        order as it was.
        """
        order = self.get_order(order_id)
        self._require_pending(order, "cancel")
        order.status = STATUS_CANCELLED
        record_actor(order, actor)
        return order

    @staticmethod
    def _require_pending(order: Order, action: str) -> None:
        """Guard a lifecycle move: pending is the only state you can leave.

        An order starts pending and may move to received or cancelled;
        anything else is refused before any state changes.
        """
        if order.status != STATUS_PENDING:
            raise ValueError(
                f"cannot {action} order {order.id}: it is already "
                f"{order.status}"
            )

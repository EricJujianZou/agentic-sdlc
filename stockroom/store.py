"""Persistence and business operations for the stockroom.

The whole application state lives in one JSON file, stamped with the
schema version it was written by::

    {
        "version":   6,
        "items":     {sku: {...}, ...},
        "suppliers": {supplier_id: {...}, ...},
        "orders":    [{...}, ...],
        "shipments": [{...}, ...],
        "discounts": {category: percent, ...},
        "tax_rate":  percent
    }

Version 6 keeps the audit trail out of that file and in a sidecar of
its own beside it - ``state.json`` gets a ``state.events.json`` holding
``{"events": [...]}`` - so the state file stays about the state, and a
backup of it is not mostly log.  Version 5 and earlier embedded the
events under an ``"events"`` key; those files still load, and the next
save moves their trail out to the sidecar.
Version 5 writes every date zero-padded as ``YYYY-MM-DD``; earlier
versions wrote them however they were typed.  Version 4 keeps every
price as a whole number of cents; version 3 and earlier wrote fractional
dollars.  Version 3 broke each item's ``qty`` down per warehouse;
version 2 and the original unversioned layout (version 1, no
``"version"`` key) store it as one total.  All of them still load -
their dates are normalized, their prices converted and their stock lands
in the default warehouse - and are rewritten in the current layout the
next time state is saved.

``Store`` loads that file into dataclasses, lets callers mutate the state
through simple methods, and writes it back out with ``save()``.  All the
"business rules" (such as they are) live here too, so the CLI stays a
thin layer of argument parsing and printing.

Errors are reported by raising ``ValueError`` with a human readable
message; the CLI turns those into exit code 1.
"""

import copy
import datetime
import json
import os
import shutil

from .dates import normalize_date
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
SCHEMA_VERSION = 6

#: What separates the state file's name from a backup's timestamp.
BACKUP_SUFFIX = ".bak-"

#: What the sidecar holding the audit trail is called: the state file's
#: name with its ``.json`` suffix replaced by this one.
EVENTS_SUFFIX = ".events.json"

#: What the marker file saying this data is read-only is called: the
#: state file's own name with this suffix appended.
LOCK_SUFFIX = ".lock"

#: The stock movements a batch file may ask for, spelled as its ``op``
#: cell spells them.
BATCH_OPS = ("receive", "ship", "transfer")


def _backup_stamp() -> str:
    """Timestamp for a backup name: sortable, and legal in a filename.

    No colons (Windows refuses them), so this is safe on any OS, and the
    fields run big-endian, so sorting the names sorts them by age.  The
    microseconds are there to keep two backups a moment apart distinct.
    """
    return datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")


def _batch_qty(raw: str | None) -> int:
    """A batch row's quantity: a whole number of units, at least one.

    Anything else - blank, fractional, a word, zero or negative - is a
    typo on the paper sheet rather than a movement, and raises
    ``ValueError``.
    """
    text = (raw or "").strip()
    try:
        qty = int(text)
    except ValueError:
        raise ValueError(f"bad quantity {text!r}") from None
    if qty < 1:
        raise ValueError(f"bad quantity {qty}")
    return qty


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
        events: the audit trail - one dict per change, oldest first.
    """

    def __init__(self, path: str):
        self.path = path
        self.items: dict[str, Item] = {}
        self.suppliers: dict[str, Supplier] = {}
        self.orders: list[Order] = []
        self.shipments: list[Shipment] = []
        self.discounts: dict[str, float] = {}
        self.tax_rate: float = 0.0
        self.events: list[dict] = []

    # ------------------------------------------------------------------
    # audit trail
    # ------------------------------------------------------------------

    def log_event(self, op: str, args: dict | None = None,
                  actor: str | None = None) -> dict:
        """Append one entry to the audit trail and return it.

        Every operation that changes the state logs exactly one entry, so
        the trail read back in order is the story of how the state got
        this way.  ``op`` is the operation named as the CLI spells it
        ("receive", "place-order", ...) whether the change came in
        through the CLI or through a script calling the method itself;
        ``actor`` is whoever ``--actor`` named, and nobody (``None``)
        when the change came from a script or a command that took no
        name.

        The methods below call this themselves - after their own
        validation, so a refused operation logs nothing - which is what
        makes a library change land in the trail too.  Reading the state
        (reports, exports, backups) changes nothing and logs nothing.
        """
        event = {
            "op": op,
            "args": dict(args or {}),
            "actor": actor,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        self.events.append(event)
        return event

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def events_path(self) -> str:
        """Where this store's audit trail is kept.

        The sidecar sits beside the state file under the same name, with
        the ``.json`` suffix swapped for ``.events.json``; a state file
        named anything else simply gets the suffix appended.
        """
        base = self.path
        if base.endswith(".json"):
            base = base[:-len(".json")]
        return base + EVENTS_SUFFIX

    def lock_path(self) -> str:
        """Where the read-only marker for this state file lives."""
        return self.path + LOCK_SUFFIX

    def is_locked(self) -> bool:
        """Whether this data has been marked read-only.

        The mark is the marker file's existence, and it sits with the
        data rather than inside the state file - so it survives across
        invocations and machines, and restoring an older backup cannot
        quietly unlock a stockroom somebody locked on purpose.
        """
        return os.path.exists(self.lock_path())

    def lock(self) -> str:
        """Mark this data read-only and return the marker's path."""
        path = self.lock_path()
        with open(path, "w", encoding="utf-8") as f:
            f.write("read-only\n")
        return path

    def unlock(self) -> None:
        """Clear the read-only mark; unlocking an unlocked store is fine."""
        if self.is_locked():
            os.remove(self.lock_path())

    def load(self) -> None:
        """Read state from the JSON file.

        A missing file just means a fresh, empty store.  A file that is
        not valid JSON raises ``json.JSONDecodeError`` for the caller to
        deal with.  Older layouts (version 2, and version 1 - which
        carries no ``"version"`` key) are read the same way; the item
        records themselves know how to read an older quantity.  A file
        written before shipments were logged has none, which is simply
        an empty log, and one written before discounts were negotiated
        has no rules and no tax.  A file written before changes were
        audited carries no events, which is likewise an empty trail.

        The audit trail comes from the sidecar when there is one, and
        from the state file itself when there is not - which is how a
        version 5 file, whose trail is still embedded, reads back whole.
        No sidecar and nothing embedded is a store nothing has happened
        to yet.
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
        self.events = self._load_events(raw)

    def _load_events(self, raw: dict) -> list[dict]:
        """The audit trail: the sidecar's when it exists, else ``raw``'s."""
        path = self.events_path()
        if not os.path.exists(path):
            return [dict(event) for event in raw.get("events", [])]
        with open(path, encoding="utf-8") as f:
            sidecar = json.load(f)
        return [dict(event) for event in sidecar.get("events", [])]

    def save(self) -> None:
        """Write the current state back to the JSON file.

        The file always declares the schema version it was written by.
        The audit trail goes to the sidecar rather than into that file -
        every time, so a trail that has been undone back to nothing does
        not come back to life out of a stale sidecar.
        """
        self._write(self.path)
        self._write_events(self.events_path())

    def _write(self, path: str) -> None:
        """Serialize the current state to ``path`` in the current layout.

        The events are not part of it: they live in their own file, so
        what this writes - including a backup - is state alone.
        """
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

    def _write_events(self, path: str) -> None:
        """Serialize the audit trail to its sidecar at ``path``."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"events": [dict(event) for event in self.events]},
                      f, indent=2)
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
        self.log_event("add-item", {
            "sku": sku, "name": name, "qty": qty, "unit_price": unit_price,
            "supplier_id": supplier_id, "category": item.category,
        }, actor)
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
        self.log_event("receive",
                       {"sku": item.sku, "qty": qty, "warehouse": warehouse},
                       actor)
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
        tell movement from mere stock levels later on.  The date is
        stored zero-padded; one that is not a real day raises
        ``ValueError`` before any stock moves.
        """
        date = (datetime.date.today().isoformat() if date is None
                else normalize_date(date))
        item = self.get_item(sku)
        on_hand = item.qty_in(warehouse)
        if qty > on_hand:
            raise ValueError(
                f"cannot ship {qty} x {sku}: only {on_hand} on hand"
            )
        item.adjust(-qty, warehouse)
        record_actor(item, actor)
        self.shipments.append(
            Shipment(sku=item.sku, qty=qty, warehouse=warehouse, date=date)
        )
        self.log_event("ship", {"sku": item.sku, "qty": qty,
                                "warehouse": warehouse, "date": date}, actor)
        return item

    def set_price(self, sku: str, price: float, date: str | None = None,
                  actor: str | None = None) -> Item:
        """Change what an item costs per unit, and remember the change.

        The old and new price are noted on the item's ``price_history``,
        dated ``date`` or today when no date is given, so a report can
        say later what anything cost at the time.  The history records
        the price the item ended up holding, rounded to whole cents, and
        the date zero-padded, rather than whatever was typed; a date
        that is not a real day raises ``ValueError`` and the price is
        left alone.
        """
        date = (datetime.date.today().isoformat() if date is None
                else normalize_date(date))
        item = self.get_item(sku)
        old_price = item.unit_price
        item.unit_price = price
        item.price_history.append({
            "date": date,
            "old": old_price,
            "new": item.unit_price,
        })
        record_actor(item, actor)
        self.log_event("set-price",
                       {"sku": item.sku, "price": item.unit_price,
                        "date": date}, actor)
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
        self.log_event("transfer",
                       {"sku": item.sku, "qty": qty, "src": src, "dst": dst},
                       actor)
        return item

    def apply_batch(self, rows: list[dict], actor: str | None = None) -> int:
        """Apply a list of stock movements, all of them or none.

        A row is a mapping with the batch file's columns - ``op``
        (:data:`BATCH_OPS`), ``sku``, ``qty``, ``warehouse`` (empty
        meaning the default one) and, for a transfer, ``to_warehouse``,
        which may name a room that has never held anything.  The rows
        are applied in the order given.

        The first row that will not go through - an op we do not know, a
        SKU we do not stock, a quantity that is not a whole number of
        units, more units than the shelf holds - aborts the whole batch:
        the rows already applied are rolled back, so a caller who
        ``save()``s only on success writes exactly what was there
        before, and the raised ``ValueError`` names the row (counting
        the data rows from 1, the header not among them) along with the
        reason it gave.  The movements that do land are logged one by
        one, as though they had been keyed in by hand, which is what
        lets ``undo`` walk back through them afterwards.

        Returns:
            The number of rows applied.
        """
        # The items are mutated in place, so they need copying in full;
        # the two logs are only ever appended to, so their own order is
        # the whole of what has to be put back.
        saved = (copy.deepcopy(self.items), list(self.shipments),
                 list(self.events))
        for number, row in enumerate(rows, 1):
            try:
                self._apply_batch_row(row, actor)
            except ValueError as exc:
                self.items, self.shipments, self.events = saved
                raise ValueError(
                    f"batch failed at row {number}: {exc}"
                ) from exc
        return len(rows)

    def _apply_batch_row(self, row: dict, actor: str | None) -> None:
        """Carry out one batch row, or raise ValueError saying why not."""
        op = (row.get("op") or "").strip()
        if op not in BATCH_OPS:
            raise ValueError(f"unknown op {op!r}")
        sku = (row.get("sku") or "").strip()
        qty = _batch_qty(row.get("qty"))
        warehouse = (row.get("warehouse") or "").strip() or DEFAULT_WAREHOUSE
        if op == "receive":
            self.receive(sku, qty, warehouse=warehouse, actor=actor)
        elif op == "ship":
            self.ship(sku, qty, warehouse=warehouse, actor=actor)
        else:
            destination = (row.get("to_warehouse") or "").strip()
            if not destination:
                raise ValueError("transfer needs a to_warehouse")
            self.transfer(sku, qty, warehouse, destination, actor=actor)

    # ------------------------------------------------------------------
    # discounts
    # ------------------------------------------------------------------

    def set_discount(self, category: str, percent: float,
                     actor: str | None = None) -> float:
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
        self.log_event("set-discount",
                       {"category": category, "percent": percent}, actor)
        return self.discounts[category]

    def get_discount(self, category: str) -> float:
        """The discount percent for a category - 0 when there is no rule."""
        return self.discounts.get(category, 0.0)

    def list_discounts(self) -> list[tuple[str, float]]:
        """Every rule as (category, percent) pairs, sorted by category."""
        return [(category, self.discounts[category])
                for category in sorted(self.discounts)]

    def remove_discount(self, category: str,
                        actor: str | None = None) -> float:
        """Drop a category's discount rule and return what it was.

        Removing a category that has no rule raises ``ValueError``: it
        is more likely a typo than a no-op worth being quiet about.
        """
        if category not in self.discounts:
            raise ValueError(f"no discount rule for {category}")
        percent = self.discounts.pop(category)
        self.log_event("remove-discount", {"category": category}, actor)
        return percent

    def set_tax_rate(self, percent: float,
                     actor: str | None = None) -> float:
        """Set the flat tax percent charged on an order.

        Every order is taxed at the same rate, so this is one setting
        rather than a rule per category.  A negative rate is refused
        with ``ValueError`` - that would be a rebate, not a tax - and
        leaves the old rate alone.
        """
        if percent < 0:
            raise ValueError(f"tax rate must not be negative, not {percent}")
        self.tax_rate = float(percent)
        self.log_event("set-tax-rate", {"percent": percent}, actor)
        return self.tax_rate

    # ------------------------------------------------------------------
    # suppliers
    # ------------------------------------------------------------------

    def add_supplier(self, supplier_id: str, name: str, email: str,
                     lead_time_days: int = 0,
                     actor: str | None = None) -> Supplier:
        """Create a new supplier.  The id must not already exist.

        A supplier record carries no last actor of its own, but adding
        one is still a change, so ``actor`` is noted on the audit trail.
        """
        if supplier_id in self.suppliers:
            raise ValueError(f"supplier {supplier_id} already exists")
        supplier = Supplier(id=supplier_id, name=name, email=email,
                            lead_time_days=lead_time_days)
        self.suppliers[supplier_id] = supplier
        self.log_event("add-supplier", {
            "id": supplier_id, "name": name, "email": email,
            "lead_time_days": lead_time_days,
        }, actor)
        return supplier

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Look up a supplier by id or raise ValueError."""
        if supplier_id not in self.suppliers:
            raise ValueError(f"unknown supplier {supplier_id}")
        return self.suppliers[supplier_id]

    def list_suppliers(self) -> list[Supplier]:
        """All suppliers, sorted by id for stable output."""
        return [self.suppliers[sid] for sid in sorted(self.suppliers)]

    def add_supplier_sku(self, supplier_id: str, sku: str,
                         actor: str | None = None) -> Supplier:
        """Note that a supplier can supply a SKU.

        The supplier must be one we know about; the SKU need not be an
        item we stock, since a catalogue is the supplier's list, not
        ours.  Listing the same SKU twice changes nothing.
        """
        supplier = self.get_supplier(supplier_id)
        sku = normalize_sku(sku)
        if sku not in supplier.skus:
            supplier.skus.append(sku)
        self.log_event("catalog-add",
                       {"supplier": supplier_id, "sku": sku}, actor)
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

        ``date`` is stored zero-padded, however it was typed, and one
        that is not a real day raises ``ValueError`` before the order is
        recorded; the CLI defaults it to today when the user does not
        pass one.  The order remembers who it was placed with -
        ``supplier_id`` when one is named, otherwise whoever
        ``_order_supplier`` works out.
        """
        date = normalize_date(date)
        item = self.get_item(sku)  # validates the SKU
        if supplier_id is not None:
            self.get_supplier(supplier_id)  # validates the supplier
        else:
            supplier_id = self._order_supplier(item)
        order = Order(id=self.next_order_id(), sku=item.sku, qty=qty, date=date,
                      supplier_id=supplier_id)
        record_actor(order, actor)
        self.orders.append(order)
        self.log_event("place-order", {
            "id": order.id, "sku": order.sku, "qty": qty, "date": date,
            "supplier_id": order.supplier_id,
        }, actor)
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
        self.log_event("ship-order", {"id": order.id, "qty": qty}, actor)
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
        after the fact.  It is stored zero-padded, and one that is not a
        real day raises ``ValueError`` before anything is booked in.

        Only a pending order can be received; receiving an already
        received or cancelled one raises ``ValueError`` and adds nothing
        to stock.
        """
        if date is not None:
            date = normalize_date(date)
        order = self.get_order(order_id)
        self._require_pending(order, "receive")
        self._book_delivery(order, order.outstanding, actor, date)
        self.log_event("receive-order",
                       {"id": order.id, "date": order.received_date}, actor)
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
        self.log_event("cancel-order", {"id": order.id}, actor)
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

    # ------------------------------------------------------------------
    # undo
    # ------------------------------------------------------------------

    def undo(self) -> dict:
        """Reverse the most recent change and return the event undone.

        The audit trail is the undo history: its last entry says what
        changed and with which arguments, so backing that change out is
        a matter of applying the entry's inverse.  The entry is then
        dropped - the trail is the story of how the state got this way,
        and a change that has been reversed is no longer part of it -
        which is also what makes a second undo step back to the change
        before it, and a third to the one before that.  Since the trail
        is saved alongside the state, undo reaches into earlier sessions
        just as well as into this one.

        An empty trail leaves nothing to undo, and some changes cannot
        be reversed from what was recorded at all - nobody wrote down
        the discount rate a ``set-discount`` replaced, so putting it
        back would be a guess.  Either way ``ValueError`` is raised
        before anything is touched, rather than a wrong reversal being
        applied quietly.

        Only the records themselves are put back.  Whoever an undone
        change named as the item's or order's last actor stays named:
        undo is a correction, not a way to make a change unhappen.
        """
        if not self.events:
            raise ValueError("nothing to undo")
        event = self.events[-1]
        reverse = self._UNDO.get(event.get("op"))
        if reverse is None:
            raise ValueError(f"cannot undo {event.get('op')}")
        reverse(self, event.get("args") or {})
        self.events.pop()
        return event

    def _undo_add_item(self, args: dict) -> None:
        """Take back an ``add-item``: the item goes away again."""
        self.items.pop(normalize_sku(args["sku"]), None)

    def _undo_add_supplier(self, args: dict) -> None:
        """Take back an ``add-supplier``: the supplier goes away again."""
        self.suppliers.pop(args["id"], None)

    def _undo_receive(self, args: dict) -> None:
        """Take back a ``receive``: the units arrived off again."""
        item = self.get_item(args["sku"])
        item.adjust(-args["qty"], args.get("warehouse", DEFAULT_WAREHOUSE))

    def _undo_ship(self, args: dict) -> None:
        """Take back a ``ship``: the units come back on the shelf.

        The shipment it logged goes with them - the goods never left,
        so leaving the movement in the log would have reports counting
        turnover that did not happen.
        """
        warehouse = args.get("warehouse", DEFAULT_WAREHOUSE)
        item = self.get_item(args["sku"])
        item.adjust(args["qty"], warehouse)
        for index in range(len(self.shipments) - 1, -1, -1):
            shipment = self.shipments[index]
            if (shipment.sku == item.sku and shipment.qty == args["qty"]
                    and shipment.warehouse == warehouse
                    and shipment.date == args.get("date")):
                del self.shipments[index]
                break

    def _undo_transfer(self, args: dict) -> None:
        """Take back a ``transfer``: the units walk back where they were."""
        item = self.get_item(args["sku"])
        item.adjust(-args["qty"], args["dst"])
        item.adjust(args["qty"], args["src"])

    def _undo_place_order(self, args: dict) -> None:
        """Take back a ``place-order``: the order was never placed."""
        self.orders = [order for order in self.orders
                       if order.id != args["id"]]

    def _undo_cancel_order(self, args: dict) -> None:
        """Take back a ``cancel-order``: the order is pending again."""
        self.get_order(args["id"]).status = STATUS_PENDING

    def _undo_set_price(self, args: dict) -> None:
        """Take back a ``set-price``: the old price is the price again.

        What it was is on the item's own price history, which is where
        the change wrote it down, so that entry both restores the price
        and comes off with it.
        """
        item = self.get_item(args["sku"])
        if not item.price_history:
            raise ValueError(
                f"cannot undo set-price: no price change recorded "
                f"for {item.sku}"
            )
        item.unit_price = item.price_history.pop()["old"]

    #: How each kind of change is reversed, keyed by the op the trail
    #: records.  An operation missing here is one the trail does not
    #: carry enough to reverse exactly (what a ``set-tax-rate`` or an
    #: ``import-csv`` overwrote is simply gone), so ``undo`` refuses it
    #: rather than guess at it.
    _UNDO = {
        "add-item": _undo_add_item,
        "add-supplier": _undo_add_supplier,
        "receive": _undo_receive,
        "ship": _undo_ship,
        "transfer": _undo_transfer,
        "place-order": _undo_place_order,
        "cancel-order": _undo_cancel_order,
        "set-price": _undo_set_price,
    }

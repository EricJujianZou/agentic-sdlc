"""Persistence and business operations for the stockroom.

The whole application state lives in one JSON file with three top-level
keys::

    {
        "items":     {sku: {...}, ...},
        "suppliers": {supplier_id: {...}, ...},
        "orders":    [{...}, ...]
    }

``Store`` loads that file into dataclasses, lets callers mutate the state
through simple methods, and writes it back out with ``save()``.  All the
"business rules" (such as they are) live here too, so the CLI stays a
thin layer of argument parsing and printing.

Errors are reported by raising ``ValueError`` with a human readable
message; the CLI turns those into exit code 1.
"""

import datetime
import glob
import json
import os

from .dates import normalize_date, normalize_stored_date
from .money import to_cents
from .models import (
    DEFAULT_CATEGORY,
    Item,
    MAIN_WAREHOUSE,
    Order,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_RECEIVED,
    Supplier,
    canonical_sku,
)

# Schema version written to the state file.  Version 1 is the original
# unversioned layout; 2 added the version stamp; 3 broke item quantities
# down per warehouse; 4 moved money to whole cents; 5 stores every
# date as a zero-padded ISO date; 6 moved the activity history to a
# sidecar file.
SCHEMA_VERSION = 6


def _record_actor(record, actor: str | None) -> None:
    """Stamp *record* with who changed it, when we were told."""
    if actor:
        record.last_actor = actor


def _require_pending(order: Order, what: str) -> None:
    """Guard the order lifecycle: only pending orders may move on."""
    if order.status != STATUS_PENDING:
        raise ValueError(
            f"cannot {what} order {order.id}: it is {order.status}")


class Store:
    """Holds the full application state and knows how to load/save it.

    Attributes:
        path: the JSON file backing this store.
        items: mapping of SKU -> Item.
        suppliers: mapping of supplier id -> Supplier.
        orders: list of Order, in the order they were placed.
    """

    def __init__(self, path: str):
        self.path = path
        self.items: dict[str, Item] = {}
        self.suppliers: dict[str, Supplier] = {}
        self.orders: list[Order] = []
        # supplier id -> the SKUs that supplier can supply
        self.catalogs: dict[str, list[str]] = {}
        # one entry per shipment out of the room: sku, qty, warehouse, date
        self.shipments: list[dict] = []
        # category -> negotiated discount percent
        self.discounts: dict[str, float] = {}
        # odds and ends we keep with the data, such as the tax rate
        self.settings: dict = {}
        # activity history, oldest first
        self.events: list[dict] = []
        # what undo would step back through, and what redo would replay
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        # bumped by every mutation; readers use it to spot stale caches
        self.revision: int = 0

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Read state from the JSON file.

        A missing file just means a fresh, empty store.  A file that is
        not valid JSON raises ``json.JSONDecodeError`` for the caller to
        deal with.
        """
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            raw = json.load(f)
        # Events used to be embedded in the state file; since version 6
        # they live in a sidecar next to it.
        if "events" not in raw and os.path.exists(self.events_path):
            with open(self.events_path, encoding="utf-8") as f:
                raw = {**raw, "events": json.load(f).get("events", [])}
        self._apply_raw(raw)

    def _apply_raw(self, raw: dict) -> None:
        """Replace the in-memory state with a state dict from disk."""
        self.items = {}
        for sku, data in raw.get("items", {}).items():
            item = Item.from_dict({**data, "sku": data.get("sku", sku)})
            self.items[item.sku] = item
        self.suppliers = {
            sid: Supplier.from_dict(data)
            for sid, data in raw.get("suppliers", {}).items()
        }
        self.orders = [Order.from_dict(data) for data in raw.get("orders", [])]
        self.catalogs = {
            sid: sorted(canonical_sku(sku) for sku in skus)
            for sid, skus in raw.get("catalogs", {}).items()
        }
        self.shipments = [{**entry,
                           "date": normalize_stored_date(entry.get("date"))}
                          for entry in raw.get("shipments", [])]
        self.discounts = {c: float(p) for c, p in raw.get("discounts", {}).items()}
        self.settings = dict(raw.get("settings", {}))
        self.events = [dict(entry) for entry in raw.get("events", [])]
        self.undo_stack = [dict(entry) for entry in raw.get("undo_stack", [])]
        self.redo_stack = [dict(entry) for entry in raw.get("redo_stack", [])]

    def _raw_state(self) -> dict:
        """The current state as the plain dict we write to disk."""
        return {
            "version": SCHEMA_VERSION,
            "items": {sku: item.to_dict() for sku, item in self.items.items()},
            "suppliers": {sid: s.to_dict() for sid, s in self.suppliers.items()},
            "orders": [order.to_dict() for order in self.orders],
            "catalogs": {sid: list(skus) for sid, skus in self.catalogs.items()},
            "shipments": [dict(entry) for entry in self.shipments],
            "discounts": dict(self.discounts),
            "settings": dict(self.settings),
            "events": [dict(entry) for entry in self.events],
            "undo_stack": [dict(entry) for entry in self.undo_stack],
            "redo_stack": [dict(entry) for entry in self.redo_stack],
        }

    @property
    def events_path(self) -> str:
        """The sidecar file holding the activity history."""
        base = self.path
        if base.endswith(".json"):
            base = base[:-len(".json")]
        return base + ".events.json"

    def save(self) -> None:
        """Write the current state back to disk.

        The activity history goes to its own sidecar file so the state
        file stays small.
        """
        raw = self._raw_state()
        events = raw.pop("events")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
            f.write("\n")
        with open(self.events_path, "w", encoding="utf-8") as f:
            json.dump({"events": events}, f, indent=2)
            f.write("\n")

    # ------------------------------------------------------------------
    # activity history and undo
    # ------------------------------------------------------------------

    def log_event(self, op: str, args: dict | None = None,
                  actor: str | None = None,
                  changes: list | None = None) -> dict:
        """Record one change in the activity history.

        *changes* describes how to walk the change back (and forward
        again), which is what ``undo`` and ``redo`` work from.  Any new
        change makes whatever was undone unredoable, as usual.
        """
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "op": op,
            "args": dict(args or {}),
            "actor": actor,
        }
        self.events.append(entry)
        self.revision += 1
        if changes is not None:
            self.undo_stack.append({"op": op, "args": dict(args or {}),
                                    "changes": changes})
            self.redo_stack = []
        return entry

    def undo(self, steps: int = 1) -> list[dict]:
        """Step back through the *steps* most recent changes, newest first."""
        if steps < 1:
            raise ValueError("steps must be at least 1")
        if len(self.undo_stack) < steps:
            raise ValueError(
                f"nothing to undo (asked for {steps}, "
                f"have {len(self.undo_stack)})")
        undone = []
        for _ in range(steps):
            entry = self.undo_stack.pop()
            for change in reversed(entry["changes"]):
                self._revert_change(change)
            self.redo_stack.append(entry)
            undone.append(entry)
        self.log_event("undo", {"steps": steps})
        return undone

    def redo(self, steps: int = 1) -> list[dict]:
        """Walk forward again through changes that were undone."""
        if steps < 1:
            raise ValueError("steps must be at least 1")
        if len(self.redo_stack) < steps:
            raise ValueError(
                f"nothing to redo (asked for {steps}, "
                f"have {len(self.redo_stack)})")
        redone = []
        for _ in range(steps):
            entry = self.redo_stack.pop()
            for change in entry["changes"]:
                self._reapply_change(change)
            self.undo_stack.append(entry)
            redone.append(entry)
        self.log_event("redo", {"steps": steps})
        return redone

    def _revert_change(self, change: dict) -> None:
        """Walk one recorded change backwards."""
        kind = change["kind"]
        if kind == "qty":
            self.items[change["sku"]].add_qty(change["warehouse"],
                                              -change["delta"])
        elif kind == "item-add":
            self.items.pop(change["sku"], None)
        elif kind == "supplier-add":
            self.suppliers.pop(change["id"], None)
        elif kind == "order-add":
            self.orders = [o for o in self.orders
                           if o.id != change["order"]["id"]]
        elif kind == "order-set":
            self._replace_order(Order.from_dict(change["before"]))
        elif kind == "price":
            item = self.items[change["sku"]]
            item.unit_price_cents = change["before_cents"]
            if item.price_history_cents:
                item.price_history_cents.pop()
        elif kind == "shipment":
            if self.shipments:
                self.shipments.pop()
        elif kind == "catalog":
            skus = self.catalogs.get(change["supplier"], [])
            if change["sku"] in skus:
                skus.remove(change["sku"])
        elif kind == "settings":
            self.discounts = dict(change["before"]["discounts"])
            self.settings = dict(change["before"]["settings"])
        elif kind == "snapshot":
            self._restore_snapshot(change["before"])
        else:
            raise ValueError(f"cannot undo {kind}")

    def _reapply_change(self, change: dict) -> None:
        """Walk one recorded change forwards again."""
        kind = change["kind"]
        if kind == "qty":
            self.items[change["sku"]].add_qty(change["warehouse"],
                                              change["delta"])
        elif kind == "item-add":
            item = Item.from_dict(change["item"])
            self.items[item.sku] = item
        elif kind == "supplier-add":
            supplier = Supplier.from_dict(change["supplier"])
            self.suppliers[supplier.id] = supplier
        elif kind == "order-add":
            self.orders.append(Order.from_dict(change["order"]))
        elif kind == "order-set":
            self._replace_order(Order.from_dict(change["after"]))
        elif kind == "price":
            item = self.items[change["sku"]]
            item.unit_price_cents = change["after_cents"]
            item.price_history_cents.append(dict(change["entry"]))
        elif kind == "shipment":
            self.shipments.append(dict(change["entry"]))
        elif kind == "catalog":
            self.add_supplier_sku(change["supplier"], change["sku"])
        elif kind == "settings":
            self.discounts = dict(change["after"]["discounts"])
            self.settings = dict(change["after"]["settings"])
        elif kind == "snapshot":
            self._restore_snapshot(change["after"])
        else:
            raise ValueError(f"cannot redo {kind}")

    def _replace_order(self, order: Order) -> None:
        """Put *order* back in place of the one with the same id."""
        for index, existing in enumerate(self.orders):
            if existing.id == order.id:
                self.orders[index] = order
                return
        self.orders.append(order)

    def _snapshot(self) -> dict:
        """Everything a bulk operation might disturb, for undoing it."""
        raw = self._raw_state()
        return {key: raw[key] for key in
                ("items", "suppliers", "orders", "catalogs", "shipments",
                 "discounts", "settings")}

    def _restore_snapshot(self, snapshot: dict) -> None:
        """Put back the state a bulk operation was applied to."""
        keep = {"events": self.events, "undo_stack": self.undo_stack,
                "redo_stack": self.redo_stack}
        self._apply_raw(snapshot)
        self.events = keep["events"]
        self.undo_stack = keep["undo_stack"]
        self.redo_stack = keep["redo_stack"]

    def _log_settings(self, op: str, args: dict, before: dict) -> None:
        """Log a change to the discount rules or settings."""
        self.log_event(op, args, None,
                       [{"kind": "settings", "before": before,
                         "after": self._settings_state()}])

    def _settings_state(self) -> dict:
        return {"discounts": dict(self.discounts),
                "settings": dict(self.settings)}

    # ------------------------------------------------------------------
    # backups
    # ------------------------------------------------------------------

    def _backup_prefix(self) -> str:
        return self.path + ".bak-"

    def backup(self) -> str:
        """Snapshot the current state next to the state file.

        Returns:
            The name (not the full path) of the backup written.  The
            timestamp in it avoids characters no OS allows in filenames.
        """
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
        path = self._backup_prefix() + stamp
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._raw_state(), f, indent=2)
            f.write("\n")
        return os.path.basename(path)

    def list_backups(self) -> list[str]:
        """Names of the backups taken so far, oldest first."""
        return sorted(os.path.basename(p)
                      for p in glob.glob(self._backup_prefix() + "*"))

    def restore(self, name: str) -> None:
        """Bring the state back to what the named backup captured."""
        name = os.path.basename(name)
        if name not in self.list_backups():
            raise ValueError(f"unknown backup {name}")
        before = self._snapshot()
        with open(os.path.join(os.path.dirname(self.path) or ".", name),
                  encoding="utf-8") as f:
            snapshot = json.load(f)
        self._restore_snapshot(snapshot)
        self.log_event("restore", {"name": name}, None,
                       [{"kind": "snapshot", "before": before,
                         "after": self._snapshot()}])

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
        category: str | None = None,
        actor: str | None = None,
    ) -> Item:
        """Create a new item.

        The SKU must not already exist (case does not distinguish two
        SKUs), and if a supplier is given it must be one we know about.
        """
        sku = canonical_sku(sku)
        if sku in self.items:
            raise ValueError(f"item {sku} already exists")
        if supplier_id is not None and supplier_id not in self.suppliers:
            raise ValueError(f"unknown supplier {supplier_id}")
        item = Item(sku=sku, name=name, qty=qty, unit_price=unit_price,
                    supplier_id=supplier_id,
                    category=category or DEFAULT_CATEGORY,
                    last_actor=actor)
        self.items[sku] = item
        self.log_event("add-item",
                       {"sku": sku, "name": name, "qty": qty,
                        "category": item.category},
                       actor,
                       [{"kind": "item-add", "sku": sku,
                         "item": item.to_dict()}])
        return item

    def get_item(self, sku: str) -> Item:
        """Look up an item by SKU (any case) or raise ValueError."""
        key = canonical_sku(sku)
        if key not in self.items:
            raise ValueError(f"unknown item {sku}")
        return self.items[key]

    def list_items(self) -> list[Item]:
        """All items, sorted by SKU for stable output."""
        return [self.items[sku] for sku in sorted(self.items)]

    def receive(self, sku: str, qty: int, warehouse: str = MAIN_WAREHOUSE,
                actor: str | None = None) -> Item:
        """Add ``qty`` units of an item to one warehouse (goods arrived)."""
        item = self.get_item(sku)
        item.add_qty(warehouse, qty)
        _record_actor(item, actor)
        self.log_event("receive",
                       {"sku": item.sku, "qty": qty, "warehouse": warehouse},
                       actor,
                       [{"kind": "qty", "sku": item.sku,
                         "warehouse": warehouse, "delta": qty}])
        return item

    def ship(self, sku: str, qty: int, warehouse: str = MAIN_WAREHOUSE,
             date: str | None = None, actor: str | None = None) -> Item:
        """Remove ``qty`` units of an item from one warehouse.

        The shelf cannot go negative: shipping more than that warehouse
        holds is refused and leaves the item untouched.  Every shipment
        that does go out is recorded, which is what the turnover and
        weekly reports read.
        """
        item = self.get_item(sku)
        on_hand = item.qty_in(warehouse)
        if qty > on_hand:
            raise ValueError(
                f"cannot ship {qty} x {item.sku} from {warehouse}: "
                f"only {on_hand} on hand")
        item.add_qty(warehouse, -qty)
        shipment = {
            "sku": item.sku,
            "qty": qty,
            "warehouse": warehouse,
            "date": normalize_date(date or datetime.date.today().isoformat()),
        }
        self.shipments.append(shipment)
        _record_actor(item, actor)
        self.log_event("ship",
                       {"sku": item.sku, "qty": qty, "warehouse": warehouse,
                        "date": shipment["date"]},
                       actor,
                       [{"kind": "qty", "sku": item.sku,
                         "warehouse": warehouse, "delta": -qty},
                        {"kind": "shipment", "entry": dict(shipment)}])
        return item

    def transfer(self, sku: str, qty: int, src: str, dst: str,
                 actor: str | None = None) -> Item:
        """Walk ``qty`` units of an item from one warehouse to another.

        Never moves more than the source actually holds; a refused
        transfer leaves both warehouses untouched.
        """
        item = self.get_item(sku)
        on_hand = item.qty_in(src)
        if qty > on_hand:
            raise ValueError(
                f"cannot transfer {qty} x {item.sku} from {src}: "
                f"only {on_hand} on hand")
        item.add_qty(src, -qty)
        item.add_qty(dst, qty)
        _record_actor(item, actor)
        self.log_event("transfer",
                       {"sku": item.sku, "qty": qty, "src": src, "dst": dst},
                       actor,
                       [{"kind": "qty", "sku": item.sku, "warehouse": src,
                         "delta": -qty},
                        {"kind": "qty", "sku": item.sku, "warehouse": dst,
                         "delta": qty}])
        return item

    def set_price(self, sku: str, price, date: str | None = None,
                  actor: str | None = None) -> Item:
        """Set an item's unit price, remembering the old one."""
        item = self.get_item(sku)
        before_cents = item.unit_price_cents
        item.record_price(
            to_cents(price),
            normalize_date(date or datetime.date.today().isoformat()))
        _record_actor(item, actor)
        self.log_event("set-price",
                       {"sku": item.sku, "price": item.unit_price},
                       actor,
                       [{"kind": "price", "sku": item.sku,
                         "before_cents": before_cents,
                         "after_cents": item.unit_price_cents,
                         "entry": dict(item.price_history_cents[-1])}])
        return item

    def scheduled_reorders(self, as_of: str | None = None,
                           threshold: int | None = None,
                           actor: str | None = None) -> list:
        """Place the purchase orders today's reorder suggestions call for.

        Idempotent per day and SKU: once a SKU has been auto-ordered for
        a given day, that day is done for it.
        """
        from . import reports  # imported here to avoid a circular import

        date = normalize_date(as_of or datetime.date.today().isoformat())
        if threshold is None:
            threshold = reports.DEFAULT_THRESHOLD
        done = self.settings.setdefault("auto_ordered", {}).setdefault(date, [])
        placed = []
        for row in reports.reorder_suggestions(self, threshold=threshold):
            if row["suggested_qty"] < 1 or row["sku"] in done:
                continue
            placed.append(self.place_order(row["sku"], row["suggested_qty"],
                                           date, actor=actor))
            done.append(row["sku"])
        return placed

    # ------------------------------------------------------------------
    # discounts and settings
    # ------------------------------------------------------------------

    def set_discount(self, category: str, percent) -> None:
        """Create or replace the discount rule for a category."""
        percent = float(percent)
        if not 0 <= percent <= 100:
            raise ValueError(
                f"discount percent must be between 0 and 100, got {percent}")
        before = self._settings_state()
        self.discounts[category] = percent
        self._log_settings("set-discount",
                           {"category": category, "percent": percent}, before)

    def get_discount(self, category: str) -> float:
        """The discount percent for a category, 0 when there is no rule."""
        return self.discounts.get(category, 0)

    def remove_discount(self, category: str) -> None:
        """Delete a category's discount rule."""
        if category not in self.discounts:
            raise ValueError(f"no discount rule for {category}")
        before = self._settings_state()
        del self.discounts[category]
        self._log_settings("remove-discount", {"category": category}, before)

    @property
    def tax_rate(self) -> float:
        """The flat tax rate, as a percent."""
        return float(self.settings.get("tax_rate", 0))

    def set_tax_rate(self, percent) -> None:
        """Set the flat tax rate, as a percent."""
        percent = float(percent)
        if percent < 0:
            raise ValueError(f"tax rate cannot be negative, got {percent}")
        before = self._settings_state()
        self.settings["tax_rate"] = percent
        self._log_settings("set-tax-rate", {"percent": percent}, before)

    # ------------------------------------------------------------------
    # suppliers
    # ------------------------------------------------------------------

    def add_supplier(self, supplier_id: str, name: str, email: str,
                     lead_time_days: int = 0,
                     actor: str | None = None) -> Supplier:
        """Create a new supplier.  The id must not already exist."""
        if supplier_id in self.suppliers:
            raise ValueError(f"supplier {supplier_id} already exists")
        supplier = Supplier(id=supplier_id, name=name, email=email,
                            lead_time_days=lead_time_days)
        self.suppliers[supplier_id] = supplier
        self.log_event("add-supplier",
                       {"id": supplier_id, "name": name,
                        "lead_time_days": lead_time_days},
                       actor,
                       [{"kind": "supplier-add", "id": supplier_id,
                         "supplier": supplier.to_dict()}])
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
                         actor: str | None = None) -> None:
        """Record that a supplier can supply a SKU."""
        self.get_supplier(supplier_id)
        item_sku = canonical_sku(sku)
        skus = self.catalogs.setdefault(supplier_id, [])
        if item_sku not in skus:
            skus.append(item_sku)
            skus.sort()
            self.log_event("catalog-add",
                           {"supplier": supplier_id, "sku": item_sku},
                           actor,
                           [{"kind": "catalog", "supplier": supplier_id,
                             "sku": item_sku}])

    def supplier_skus(self, supplier_id: str) -> list[str]:
        """The SKUs one supplier lists, sorted."""
        self.get_supplier(supplier_id)
        return list(self.catalogs.get(supplier_id, []))

    def suppliers_for(self, sku: str) -> list[str]:
        """Supplier ids whose catalogue lists *sku*, sorted."""
        item_sku = canonical_sku(sku)
        return sorted(sid for sid, skus in self.catalogs.items()
                      if item_sku in skus)

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
        the user does not pass one.  The supplier is worked out from the
        catalogues unless one is named explicitly.
        """
        item = self.get_item(sku)  # validates the SKU
        supplier_id = self._order_supplier(item, supplier_id)
        order = Order(id=self.next_order_id(), sku=item.sku, qty=qty,
                      date=normalize_date(date), supplier_id=supplier_id,
                      last_actor=actor)
        self.orders.append(order)
        self.log_event("place-order",
                       {"id": order.id, "sku": order.sku, "qty": qty,
                        "date": order.date, "supplier": supplier_id},
                       actor,
                       [{"kind": "order-add", "order": order.to_dict()}])
        return order

    def _order_supplier(self, item: Item, supplier_id: str | None) -> str | None:
        """Who an order for *item* goes to; an explicit id always wins."""
        if supplier_id is not None:
            self.get_supplier(supplier_id)  # validates the id
            return supplier_id
        candidates = self.suppliers_for(item.sku)
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise ValueError(
                f"{item.sku} is listed by several suppliers "
                f"({', '.join(candidates)}); pass --supplier")
        return item.supplier_id

    def get_order(self, order_id: int) -> Order:
        """Look up an order by id or raise ValueError."""
        for order in self.orders:
            if order.id == order_id:
                return order
        raise ValueError(f"unknown order {order_id}")

    def receive_order(self, order_id: int, date: str | None = None,
                      actor: str | None = None) -> Order:
        """Mark an order received and put its quantity into stock.

        Only a pending order can be received, so goods never get booked
        in twice.
        """
        order = self.get_order(order_id)
        _require_pending(order, "receive")
        before = order.to_dict()
        item = self.get_item(order.sku)
        delivered = order.outstanding
        item.add_qty(MAIN_WAREHOUSE, delivered)
        order.shipped_qty = order.qty
        order.status = STATUS_RECEIVED
        order.received_date = normalize_date(
            date or datetime.date.today().isoformat())
        _record_actor(order, actor)
        _record_actor(item, actor)
        self.log_event("receive-order",
                       {"id": order.id, "sku": order.sku, "qty": delivered,
                        "date": order.received_date},
                       actor,
                       [{"kind": "qty", "sku": order.sku,
                         "warehouse": MAIN_WAREHOUSE, "delta": delivered},
                        {"kind": "order-set", "id": order.id,
                         "before": before, "after": order.to_dict()}])
        return order

    def ship_order(self, order_id: int, qty: int,
                   actor: str | None = None) -> Order:
        """Book a partial delivery of *qty* units against an order.

        The order stays pending while anything is outstanding and flips
        to received on its own once the whole quantity has arrived.
        """
        order = self.get_order(order_id)
        _require_pending(order, "deliver against")
        if qty < 1:
            raise ValueError(f"delivery quantity must be at least 1, got {qty}")
        if qty > order.outstanding:
            raise ValueError(
                f"cannot deliver {qty} against order {order.id}: "
                f"only {order.outstanding} outstanding")
        before = order.to_dict()
        item = self.get_item(order.sku)
        item.add_qty(MAIN_WAREHOUSE, qty)
        order.shipped_qty += qty
        if order.outstanding == 0:
            order.status = STATUS_RECEIVED
        _record_actor(order, actor)
        _record_actor(item, actor)
        self.log_event("ship-order",
                       {"id": order.id, "sku": order.sku, "qty": qty},
                       actor,
                       [{"kind": "qty", "sku": order.sku,
                         "warehouse": MAIN_WAREHOUSE, "delta": qty},
                        {"kind": "order-set", "id": order.id,
                         "before": before, "after": order.to_dict()}])
        return order

    def cancel_order(self, order_id: int, actor: str | None = None) -> Order:
        """Mark a pending order cancelled.  Stock is not affected."""
        order = self.get_order(order_id)
        _require_pending(order, "cancel")
        before = order.to_dict()
        order.status = STATUS_CANCELLED
        _record_actor(order, actor)
        self.log_event("cancel-order", {"id": order.id, "sku": order.sku},
                       actor,
                       [{"kind": "order-set", "id": order.id,
                         "before": before, "after": order.to_dict()}])
        return order

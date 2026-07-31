"""Persistence and business operations for the stockroom.

The whole application state lives in one JSON file, stamped with the
schema version it was written by::

    {
        "version":   2,
        "items":     {sku: {...}, ...},
        "suppliers": {supplier_id: {...}, ...},
        "orders":    [{...}, ...]
    }

Files written before versioning existed have no ``"version"`` key; they
are version 1 and still load, and are rewritten with a version the next
time state is saved.

``Store`` loads that file into dataclasses, lets callers mutate the state
through simple methods, and writes it back out with ``save()``.  All the
"business rules" (such as they are) live here too, so the CLI stays a
thin layer of argument parsing and printing.

Errors are reported by raising ``ValueError`` with a human readable
message; the CLI turns those into exit code 1.
"""

import json
import os

from .models import (
    DEFAULT_CATEGORY,
    Item,
    Order,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_RECEIVED,
    Supplier,
    normalize_sku,
    record_actor,
)

#: Schema version stamped into every state file we write.  Version 1 is
#: the original unversioned layout, which carries no ``"version"`` key.
SCHEMA_VERSION = 2


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

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Read state from the JSON file.

        A missing file just means a fresh, empty store.  A file that is
        not valid JSON raises ``json.JSONDecodeError`` for the caller to
        deal with.  A missing ``"version"`` key means the original
        (version 1) layout, which is read exactly the same way.
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

    def save(self) -> None:
        """Write the current state back to the JSON file.

        The file always declares the schema version it was written by.
        """
        raw = {
            "version": SCHEMA_VERSION,
            "items": {sku: item.to_dict() for sku, item in self.items.items()},
            "suppliers": {sid: s.to_dict() for sid, s in self.suppliers.items()},
            "orders": [order.to_dict() for order in self.orders],
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
            f.write("\n")

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

    def receive(self, sku: str, qty: int, actor: str | None = None) -> Item:
        """Add ``qty`` units of an item to stock (goods arrived)."""
        item = self.get_item(sku)
        item.qty += qty
        record_actor(item, actor)
        return item

    def ship(self, sku: str, qty: int, actor: str | None = None) -> Item:
        """Remove ``qty`` units of an item from stock (goods sent out).

        The shelf cannot go negative: shipping more than we have on hand
        raises ``ValueError`` and leaves the item untouched.  Shipping
        exactly the on-hand quantity is fine.
        """
        item = self.get_item(sku)
        if qty > item.qty:
            raise ValueError(
                f"cannot ship {qty} x {sku}: only {item.qty} on hand"
            )
        item.qty -= qty
        record_actor(item, actor)
        return item

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

    # ------------------------------------------------------------------
    # orders
    # ------------------------------------------------------------------

    def next_order_id(self) -> int:
        """Return the next free order id (ids are small integers)."""
        if not self.orders:
            return 1
        return max(order.id for order in self.orders) + 1

    def place_order(self, sku: str, qty: int, date: str,
                    actor: str | None = None) -> Order:
        """Record a new pending purchase order for an existing item.

        ``date`` is stored as given; the CLI defaults it to today when
        the user does not pass one.
        """
        item = self.get_item(sku)  # validates the SKU
        order = Order(id=self.next_order_id(), sku=item.sku, qty=qty, date=date)
        record_actor(order, actor)
        self.orders.append(order)
        return order

    def get_order(self, order_id: int) -> Order:
        """Look up an order by id or raise ValueError."""
        for order in self.orders:
            if order.id == order_id:
                return order
        raise ValueError(f"unknown order {order_id}")

    def receive_order(self, order_id: int, actor: str | None = None) -> Order:
        """Mark a pending order received and put its quantity into stock.

        Only a pending order can be received; receiving an already
        received or cancelled one raises ``ValueError`` and adds nothing
        to stock.  Both the order and the restocked item record the
        actor, since both change.
        """
        order = self.get_order(order_id)
        self._require_pending(order, "receive")
        order.status = STATUS_RECEIVED
        record_actor(order, actor)
        item = self.get_item(order.sku)
        item.qty += order.qty
        record_actor(item, actor)
        return order

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

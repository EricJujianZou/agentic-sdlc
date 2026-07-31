"""Command line interface for the stockroom.

Usage::

    python -m stockroom.cli --data <dir> <command> [args...]

``--data`` names a directory; state is kept in ``<dir>/state.json``.

Exit codes: 0 on success, 1 on a user error (unknown SKU, bad order id,
missing file, ...), 2 when the state file cannot be parsed.
"""

import argparse
import datetime
import json
import os
import sys

from . import __version__, csv_io, dates, reports
from .models import DEFAULT_CATEGORY, DEFAULT_WAREHOUSE, normalize_sku
from .money import format_money
from .store import Store


# ----------------------------------------------------------------------
# command handlers -- each takes (store, args) and returns an exit code
# ----------------------------------------------------------------------

def cmd_add_item(store: Store, args) -> int:
    """Handle ``add-item``: create a new item in the catalogue."""
    item = store.add_item(
        args.sku,
        args.name,
        qty=args.qty,
        unit_price=args.price,
        supplier_id=args.supplier,
        category=args.category,
        actor=args.actor,
    )
    store.save()
    print(f"added item {item.sku} ({item.name})")
    return 0


def cmd_add_supplier(store: Store, args) -> int:
    """Handle ``add-supplier``: register a new supplier.

    Only items and orders carry an actor of their own, but ``--actor``
    still says who made the change on the audit trail.
    """
    supplier = store.add_supplier(args.id, args.name, args.email,
                                  lead_time_days=args.lead_time,
                                  actor=args.actor)
    store.save()
    print(f"added supplier {supplier.id} ({supplier.name})")
    return 0


def cmd_receive(store: Store, args) -> int:
    """Handle ``receive``: goods arrived outside of an order."""
    item = store.receive(args.sku, args.qty, warehouse=args.warehouse,
                         actor=args.actor)
    store.save()
    print(f"received {args.qty} x {item.sku}, now {item.qty} on hand")
    return 0


def cmd_ship(store: Store, args) -> int:
    """Handle ``ship``: send units out of the stockroom.

    ``--date`` says when the goods went out; the store dates the
    shipment today when it is left off.
    """
    item = store.ship(args.sku, args.qty, warehouse=args.warehouse,
                      actor=args.actor, date=args.date)
    store.save()
    print(f"shipped {args.qty} x {item.sku}, now {item.qty} on hand")
    return 0


def cmd_set_price(store: Store, args) -> int:
    """Handle ``set-price``: change an item's unit price.

    ``--date`` says when the new price took effect; the store dates the
    change today when it is left off.
    """
    item = store.set_price(args.sku, args.price, date=args.date,
                           actor=args.actor)
    store.save()
    print(f"{item.sku} now {format_money(item.unit_price)} per unit")
    return 0


def cmd_transfer(store: Store, args) -> int:
    """Handle ``transfer``: walk units from one warehouse to another."""
    item = store.transfer(args.sku, args.qty, args.src, args.dst,
                          actor=args.actor)
    store.save()
    print(f"transferred {args.qty} x {item.sku} from {args.src} to "
          f"{args.dst}, now {item.qty_in(args.dst)} there")
    return 0


def _format_percent(percent: float) -> str:
    """A discount rate as typed: no trailing zeros, no bare ``.0``."""
    return f"{percent:g}%"


def cmd_set_discount(store: Store, args) -> int:
    """Handle ``set-discount``: agree a rate for one category."""
    percent = store.set_discount(args.category, args.percent,
                                 actor=args.actor)
    store.save()
    print(f"{args.category} discount {_format_percent(percent)}")
    return 0


def cmd_list_discounts(store: Store, args) -> int:
    """Handle ``list-discounts``: print every rule, one per line."""
    for category, percent in store.list_discounts():
        print(f"{category:<16} {_format_percent(percent)}")
    return 0


def cmd_remove_discount(store: Store, args) -> int:
    """Handle ``remove-discount``: drop one category's rule."""
    store.remove_discount(args.category, actor=args.actor)
    store.save()
    print(f"removed {args.category} discount")
    return 0


def cmd_set_tax_rate(store: Store, args) -> int:
    """Handle ``set-tax-rate``: set the flat tax charged on orders."""
    percent = store.set_tax_rate(args.percent, actor=args.actor)
    store.save()
    print(f"tax rate {_format_percent(percent)}")
    return 0


def _invoice_text(store: Store, order_id: int, breakdown: dict) -> str:
    """The invoice for one order as a plain-text document.

    The same breakdown the screen shows, with the order's own details
    above it so the file stands on its own once it has been mailed out.
    Nothing here depends on when it was generated, so invoicing the same
    order twice gives the same bytes.
    """
    order = store.get_order(order_id)
    lines = [
        f"invoice for order {order.id}",
        f"  item       {order.sku}",
        f"  quantity   {order.qty}",
        f"  date       {order.date}",
        "",
    ]
    lines += [f"  {label:<10} {format_money(breakdown[label]):>10}"
              for label in ("subtotal", "discount", "tax", "total")]
    return "\n".join(lines) + "\n"


def cmd_invoice(store: Store, args) -> int:
    """Handle ``invoice``: print what one order comes to, line by line.

    With ``--output`` the same invoice is also written to that path as a
    text file; an order id we cannot price fails before the file is
    opened, so nothing is left behind.
    """
    breakdown = reports.order_total(store, args.id)
    if args.output is not None:
        text = _invoice_text(store, args.id, breakdown)
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print(f"invoice for order {args.id}")
    for label in ("subtotal", "discount", "tax", "total"):
        print(f"  {label:<10} {format_money(breakdown[label]):>10}")
    if args.output is not None:
        print(f"wrote invoice to {args.output}")
    return 0


def cmd_place_order(store: Store, args) -> int:
    """Handle ``place-order``: record a pending purchase order."""
    date = args.date
    if date is None:
        date = datetime.date.today().isoformat()
    order = store.place_order(args.sku, args.qty, date,
                              supplier_id=args.supplier, actor=args.actor)
    store.save()
    print(f"placed order {order.id}: {order.qty} x {order.sku} on {order.date}"
          f" from {order.supplier_id or 'no supplier'}")
    return 0


def cmd_scheduled_reorders(store: Store, args) -> int:
    """Handle ``scheduled-reorders``: place the day's reorder suggestions.

    The same suggestions ``report low`` prints, typed in for you: one
    pending order per suggested SKU, for the suggested quantity, dated
    the as-of day.  A SKU that already has an order dated that day is
    left alone - once it has been ordered for a given day, that day is
    done for it - so running the job twice for the same date changes
    nothing.  Later days look after themselves: the orders placed here
    are pending, so they net out of the next round of suggestions.
    """
    as_of = dates.normalize_date(args.as_of)
    ordered_today = {order.sku for order in store.orders if order.date == as_of}
    placed = []
    for row in reports.reorder_suggestions(store, threshold=args.threshold):
        if row["suggested_qty"] <= 0 or row["sku"] in ordered_today:
            continue
        placed.append(store.place_order(row["sku"], row["suggested_qty"], as_of,
                                        supplier_id=row["supplier_id"],
                                        actor=args.actor))
    if not placed:
        print(f"nothing to reorder on {as_of}")
        return 0
    store.save()
    for order in placed:
        print(f"placed order {order.id}: {order.qty} x {order.sku} "
              f"from {order.supplier_id} on {order.date}")
    return 0


def cmd_catalog_add(store: Store, args) -> int:
    """Handle ``catalog-add``: note that a supplier can supply a SKU."""
    supplier = store.add_supplier_sku(args.supplier, args.sku,
                                      actor=args.actor)
    store.save()
    print(f"{supplier.id} supplies {normalize_sku(args.sku)}")
    return 0


def cmd_catalog_list(store: Store, args) -> int:
    """Handle ``catalog-list``: print one supplier's catalogue."""
    for sku in store.catalog_skus(args.supplier):
        print(sku)
    return 0


def cmd_ship_order(store: Store, args) -> int:
    """Handle ``ship-order``: part of an order arrived; stock it."""
    order = store.ship_order(args.id, args.qty, actor=args.actor)
    store.save()
    print(f"order {order.id}: {args.qty} x {order.sku} delivered, "
          f"{order.shipped_qty} of {order.qty} in ({order.status})")
    return 0


def cmd_receive_order(store: Store, args) -> int:
    """Handle ``receive-order``: the rest of an order arrived; stock it.

    ``--date`` says when the goods turned up; the store dates the
    arrival today when it is left off.
    """
    remainder = store.get_order(args.id).outstanding
    order = store.receive_order(args.id, actor=args.actor, date=args.date)
    store.save()
    print(f"order {order.id} received, {remainder} x {order.sku} added to stock")
    return 0


def cmd_cancel_order(store: Store, args) -> int:
    """Handle ``cancel-order``: mark an order cancelled."""
    order = store.cancel_order(args.id, actor=args.actor)
    store.save()
    print(f"order {order.id} cancelled")
    return 0


def cmd_undo(store: Store, args) -> int:
    """Handle ``undo``: reverse the most recent change.

    Nothing is saved unless the reversal went through, so an undo with
    no history behind it (or one the store refuses) leaves the state
    file exactly as it was.
    """
    event = store.undo()
    store.save()
    print(f"undid {event['op']}")
    return 0


def _print_stock_header() -> None:
    print(f"{'SKU':<12} {'NAME':<24} {'QTY':>6} {'PRICE':>10} {'VALUE':>10}")


def _print_stock_rows(rows: list[dict]) -> None:
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6} "
              f"{format_money(row['unit_price']):>10} "
              f"{format_money(row['value']):>10}")


def cmd_report_stock(store: Store, args) -> int:
    """Handle ``report stock``: print the full stock listing, optionally
    grouped under one heading per shelf area or narrowed to one
    warehouse."""
    report = reports.stock_report(store, by_category=args.by_category,
                                  warehouse=args.warehouse)
    if args.by_category:
        for category in sorted(report["categories"]):
            print(f"[{category}]")
            _print_stock_header()
            _print_stock_rows(report["categories"][category])
            print()
    else:
        _print_stock_header()
        _print_stock_rows(report["rows"])
    print(f"Total value: {format_money(report['total_value'])}")
    return 0


def _print_low_rows(rows: list[dict]) -> None:
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6}")


def cmd_report_low(store: Store, args) -> int:
    """Handle ``report low``: print items running low, optionally under
    one heading per shelf area, plus reorder suggestions for the ones we
    can actually reorder."""
    if args.by_category:
        grouped = reports.low_stock_by_category(store,
                                                threshold=args.threshold)
        if not grouped:
            print("no items at or below threshold")
            return 0
        for category in sorted(grouped):
            print(f"[{category}]")
            _print_low_rows(grouped[category])
            print()
    else:
        rows = reports.low_stock(store, threshold=args.threshold)
        if not rows:
            print("no items at or below threshold")
            return 0
        _print_low_rows(rows)
    suggestions = reports.reorder_suggestions(store, threshold=args.threshold)
    if suggestions:
        print()
        print("reorder suggestions:")
        for row in suggestions:
            print(f"  {row['sku']}: order {row['suggested_qty']} "
                  f"from {row['supplier_id']} "
                  f"(lead time {row['lead_time_days']} days)")
    return 0


def cmd_report_monthly(store: Store, args) -> int:
    """Handle ``report monthly``: print orders for one month."""
    rows = reports.monthly_orders(store, args.month)
    if not rows:
        print(f"no orders in {args.month}")
        return 0
    for row in rows:
        print(f"{row['date']:<12} order {row['id']:>4}  "
              f"{row['qty']:>4} x {row['sku']:<12} {row['status']}")
    print(f"{len(rows)} orders in {args.month}")
    return 0


def cmd_report_revenue(store: Store, args) -> int:
    """Handle ``report revenue``: print what one month's received orders
    were worth."""
    revenue = reports.monthly_revenue(store, args.month)
    for row in revenue["rows"]:
        print(f"order {row['id']:>4}  {row['sku']:<12} "
              f"{format_money(row['total']):>10}")
    print(f"Total revenue: {format_money(revenue['total'])}")
    return 0


def cmd_report_on_time(store: Store, args) -> int:
    """Handle ``report on-time``: print each supplier's delivery record."""
    rows = reports.supplier_on_time(store)
    if not rows:
        print("no deliveries with an arrival date recorded")
        return 0
    for row in rows:
        print(f"{row['supplier_id']:<16} {row['on_time']:>4}/{row['total']:<4} "
              f"{row['pct']:>6.1f}%")
    return 0


def cmd_report_aging(store: Store, args) -> int:
    """Handle ``report aging``: print the orders still outstanding, grouped
    by how long they have been waiting."""
    as_of = (dates.normalize_date(args.as_of) if args.as_of
             else datetime.date.today().isoformat())
    aging = reports.order_aging(store, as_of)
    print(f"Open orders as of {as_of}")
    for bucket in reports.AGING_BUCKETS:
        print(f"{bucket} days")
        if not aging[bucket]:
            print("  (none)")
            continue
        for row in aging[bucket]:
            print(f"  {row['date']:<12} order {row['id']:>4}  "
                  f"{row['qty']:>4} x {row['sku']}")
    return 0


def cmd_report_turnover(store: Store, args) -> int:
    """Handle ``report turnover``: print units shipped per category per
    month."""
    totals = reports.turnover(store)
    if not totals:
        print("nothing shipped yet")
        return 0
    for category in sorted(totals):
        for month in sorted(totals[category]):
            print(f"{category:<16} {month:<8} {totals[category][month]:>6}")
    return 0


def cmd_report_price_changes(store: Store, args) -> int:
    """Handle ``report price-changes``: print every price change."""
    rows = reports.price_changes(store)
    if not rows:
        print("no price changes recorded")
        return 0
    for row in rows:
        print(f"{row['date']:<12} {row['sku']:<12} "
              f"{format_money(row['old']):>10} -> "
              f"{format_money(row['new']):>10}")
    return 0


def cmd_report_history(store: Store, args) -> int:
    """Handle ``report history``: print all orders for a SKU."""
    store.get_item(args.sku)  # complain early about unknown SKUs
    rows = reports.order_history(store, args.sku)
    if not rows:
        print(f"no orders for {args.sku}")
        return 0
    for row in rows:
        print(f"{row['date']:<12} order {row['id']:>4}  "
              f"{row['qty']:>4}  {row['status']}")
    return 0


def cmd_search(store: Store, args) -> int:
    """Handle ``search``: print the items matching a query."""
    rows = reports.search_items(store, args.query)
    if not rows:
        print(f"no items match {args.query}")
        return 0
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6}")
    return 0


def cmd_export_csv(store: Store, args) -> int:
    """Handle ``export-csv``: write the item list to a file."""
    count = csv_io.export_items(store, args.path)
    print(f"exported {count} items to {args.path}")
    return 0


def cmd_import_csv(store: Store, args) -> int:
    """Handle ``import-csv``: merge items from a CSV file."""
    if not os.path.exists(args.path):
        raise ValueError(f"no such file: {args.path}")
    count = csv_io.import_items(store, args.path, actor=args.actor)
    store.save()
    print(f"imported {count} rows from {args.path}")
    return 0


def cmd_backup(store: Store, args) -> int:
    """Handle ``backup``: snapshot the state beside the state file."""
    name = store.backup()
    print(f"created backup {name}")
    return 0


def cmd_list_backups(store: Store, args) -> int:
    """Handle ``list-backups``: print the backup names, oldest first."""
    for name in store.list_backups():
        print(name)
    return 0


def cmd_restore(store: Store, args) -> int:
    """Handle ``restore``: put the state back to a named backup.

    Nothing is saved afterwards - the backup is the state file now, and
    writing this session's stale copy over it would undo the restore.
    """
    name = store.restore(args.name)
    print(f"restored from {name}")
    return 0


# ----------------------------------------------------------------------
# argument parsing
# ----------------------------------------------------------------------

EXAMPLES = """\
examples:
  stockroom --data ./data add-supplier acme "Acme Supply" orders@acme.example
  stockroom --data ./data add-item WID-1 "Widget" --qty 10 --price 19.99 --supplier acme
  stockroom --data ./data ship WID-1 3
  stockroom --data ./data receive WID-1 5 --warehouse east
  stockroom --data ./data transfer WID-1 2 main east
  stockroom --data ./data set-price WID-1 24.50 --date 2026-07-05
  stockroom --data ./data set-discount widgets 12.5
  stockroom --data ./data list-discounts
  stockroom --data ./data remove-discount widgets
  stockroom --data ./data set-tax-rate 5
  stockroom --data ./data invoice 1
  stockroom --data ./data invoice 1 --output invoice-1.txt
  stockroom --data ./data scheduled-reorders --as-of 2026-08-01
  stockroom --data ./data catalog-add acme WID-1
  stockroom --data ./data catalog-list acme
  stockroom --data ./data place-order WID-1 20 --date 2026-07-01 --supplier acme
  stockroom --data ./data ship-order 1 --qty 5
  stockroom --data ./data receive-order 1 --date 2026-07-06
  stockroom --data ./data undo
  stockroom --data ./data report stock
  stockroom --data ./data report monthly 2026-07
  stockroom --data ./data report revenue 2026-07
  stockroom --data ./data report on-time
  stockroom --data ./data report aging --as-of 2026-08-01
  stockroom --data ./data report turnover
  stockroom --data ./data report price-changes
  stockroom --data ./data search widget
  stockroom --data ./data export-csv items.csv
  stockroom --data ./data backup
  stockroom --data ./data restore state.json.bak-20260101T090000000000
"""


def _add_actor(parser: argparse.ArgumentParser) -> None:
    """Attach the optional ``--actor`` flag to a state-changing command."""
    parser.add_argument("--actor", default=None,
                        help="who is running this, recorded on the records "
                             "it changes")


def _add_warehouse(parser: argparse.ArgumentParser) -> None:
    """Attach the optional ``--warehouse`` flag to a stock movement."""
    parser.add_argument("--warehouse", default=DEFAULT_WAREHOUSE,
                        help=f"room the stock moves in or out of "
                             f"(default: {DEFAULT_WAREHOUSE})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stockroom",
        description="Track stockroom inventory, suppliers and orders.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version",
                        version=f"stockroom {__version__}")
    parser.add_argument("--data", required=True,
                        help="directory holding state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-item", help="create a new item")
    p.add_argument("sku")
    p.add_argument("name")
    p.add_argument("--qty", type=int, default=0)
    p.add_argument("--price", type=float, default=0.0)
    p.add_argument("--supplier", default=None)
    p.add_argument("--category", default=DEFAULT_CATEGORY,
                   help=f"shelf area (default: {DEFAULT_CATEGORY})")
    _add_actor(p)
    p.set_defaults(func=cmd_add_item)

    p = sub.add_parser("add-supplier", help="create a new supplier")
    p.add_argument("id")
    p.add_argument("name")
    p.add_argument("email")
    p.add_argument("--lead-time", type=int, default=0, dest="lead_time",
                   help="days between placing an order and delivery")
    _add_actor(p)
    p.set_defaults(func=cmd_add_supplier)

    p = sub.add_parser("receive", help="add units of an item to stock")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    _add_warehouse(p)
    _add_actor(p)
    p.set_defaults(func=cmd_receive)

    p = sub.add_parser("ship", help="remove units of an item from stock")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("--date", default=None,
                   help="date the goods went out (default: today)")
    _add_warehouse(p)
    _add_actor(p)
    p.set_defaults(func=cmd_ship)

    p = sub.add_parser("set-price", help="change an item's unit price")
    p.add_argument("sku")
    p.add_argument("price", type=float)
    p.add_argument("--date", default=None,
                   help="date the new price took effect (default: today)")
    _add_actor(p)
    p.set_defaults(func=cmd_set_price)

    p = sub.add_parser("transfer",
                       help="move units of an item between warehouses")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("src", help="warehouse the stock leaves")
    p.add_argument("dst", help="warehouse the stock arrives in")
    _add_actor(p)
    p.set_defaults(func=cmd_transfer)

    p = sub.add_parser("set-discount",
                       help="set a category's discount rate")
    p.add_argument("category")
    p.add_argument("percent", type=float, help="0 to 100, decimals allowed")
    _add_actor(p)
    p.set_defaults(func=cmd_set_discount)

    p = sub.add_parser("list-discounts", help="print the discount rules")
    p.set_defaults(func=cmd_list_discounts)

    p = sub.add_parser("remove-discount", help="drop a category's discount")
    p.add_argument("category")
    _add_actor(p)
    p.set_defaults(func=cmd_remove_discount)

    p = sub.add_parser("set-tax-rate", help="set the flat tax rate on orders")
    p.add_argument("percent", type=float, help="a percent, decimals allowed")
    _add_actor(p)
    p.set_defaults(func=cmd_set_tax_rate)

    p = sub.add_parser("invoice", help="print an order's cost breakdown")
    p.add_argument("id", type=int)
    p.add_argument("--output", default=None,
                   help="also write the invoice to this file")
    p.set_defaults(func=cmd_invoice)

    p = sub.add_parser("place-order", help="record a purchase order")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("--date", default=None,
                   help="order date (default: today)")
    p.add_argument("--supplier", default=None,
                   help="who to order from (default: whoever's catalogue "
                        "lists the SKU, else the item's own supplier)")
    _add_actor(p)
    p.set_defaults(func=cmd_place_order)

    p = sub.add_parser("scheduled-reorders",
                       help="place an order for every reorder suggestion")
    p.add_argument("--as-of", required=True,
                   help="day to order for, YYYY-MM-DD")
    p.add_argument("--threshold", type=int, default=reports.DEFAULT_THRESHOLD)
    _add_actor(p)
    p.set_defaults(func=cmd_scheduled_reorders)

    p = sub.add_parser("catalog-add",
                       help="record that a supplier can supply a SKU")
    p.add_argument("supplier")
    p.add_argument("sku")
    _add_actor(p)
    p.set_defaults(func=cmd_catalog_add)

    p = sub.add_parser("catalog-list", help="print a supplier's catalogue")
    p.add_argument("supplier")
    p.set_defaults(func=cmd_catalog_list)

    p = sub.add_parser("ship-order",
                       help="stock part of an order the supplier delivered")
    p.add_argument("id", type=int)
    p.add_argument("--qty", type=int, required=True,
                   help="units delivered (at most what is outstanding)")
    _add_actor(p)
    p.set_defaults(func=cmd_ship_order)

    p = sub.add_parser("receive-order",
                       help="stock the rest of an order and mark it received")
    p.add_argument("id", type=int)
    p.add_argument("--date", default=None,
                   help="date the goods arrived (default: today)")
    _add_actor(p)
    p.set_defaults(func=cmd_receive_order)

    p = sub.add_parser("cancel-order", help="cancel an order")
    p.add_argument("id", type=int)
    _add_actor(p)
    p.set_defaults(func=cmd_cancel_order)

    p = sub.add_parser("undo", help="reverse the most recent change")
    p.set_defaults(func=cmd_undo)

    report = sub.add_parser("report", help="print a report")
    report_sub = report.add_subparsers(dest="report_kind", required=True)

    p = report_sub.add_parser("stock", help="full stock listing with values")
    p.add_argument("--by-category", action="store_true",
                   help="group the listing by shelf area")
    p.add_argument("--warehouse", default=None,
                   help="report on one warehouse alone (default: all of them)")
    p.set_defaults(func=cmd_report_stock)

    p = report_sub.add_parser("low", help="items running low")
    p.add_argument("--threshold", type=int, default=reports.DEFAULT_THRESHOLD)
    p.add_argument("--by-category", action="store_true",
                   help="group the low items under one heading per shelf area")
    p.set_defaults(func=cmd_report_low)

    p = report_sub.add_parser("monthly", help="orders placed in a month")
    p.add_argument("month", help="month prefix, e.g. 2026-01")
    p.set_defaults(func=cmd_report_monthly)

    p = report_sub.add_parser("revenue",
                              help="what a month's received orders were worth")
    p.add_argument("month", help="month prefix, e.g. 2026-01")
    p.set_defaults(func=cmd_report_revenue)

    p = report_sub.add_parser("on-time",
                              help="how well each supplier keeps to its "
                                   "lead time")
    p.set_defaults(func=cmd_report_on_time)

    p = report_sub.add_parser("aging",
                              help="how long open orders have been waiting")
    p.add_argument("--as-of", default=None,
                   help="day to count the ages up to (default: today)")
    p.set_defaults(func=cmd_report_aging)

    p = report_sub.add_parser("turnover",
                              help="units shipped per category per month")
    p.set_defaults(func=cmd_report_turnover)

    p = report_sub.add_parser("price-changes",
                              help="every recorded price change")
    p.set_defaults(func=cmd_report_price_changes)

    p = report_sub.add_parser("history", help="order history for one SKU")
    p.add_argument("sku")
    p.set_defaults(func=cmd_report_history)

    p = sub.add_parser("search", help="find items by name or SKU")
    p.add_argument("query", help="text to look for in the name or SKU")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("export-csv", help="write items to a CSV file")
    p.add_argument("path")
    p.set_defaults(func=cmd_export_csv)

    p = sub.add_parser("import-csv", help="read items from a CSV file")
    p.add_argument("path")
    _add_actor(p)
    p.set_defaults(func=cmd_import_csv)

    p = sub.add_parser("backup", help="snapshot the current state")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("list-backups", help="list the existing backups")
    p.set_defaults(func=cmd_list_backups)

    p = sub.add_parser("restore", help="put the state back to a backup")
    p.add_argument("name", help="backup name, as printed by backup")
    p.set_defaults(func=cmd_restore)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    state_path = os.path.join(args.data, "state.json")
    store = Store(state_path)
    try:
        store.load()
    except json.JSONDecodeError as exc:
        print(f"error: state file {state_path} is corrupt: {exc}",
              file=sys.stderr)
        return 2

    try:
        return args.func(store, args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

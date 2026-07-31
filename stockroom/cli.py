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

from . import __version__, csv_io, reports
from .models import MAIN_WAREHOUSE
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
    """Handle ``add-supplier``: register a new supplier."""
    supplier = store.add_supplier(args.id, args.name, args.email,
                                  lead_time_days=args.lead_time)
    store.save()
    print(f"added supplier {supplier.id} ({supplier.name})")
    return 0


def cmd_receive(store: Store, args) -> int:
    """Handle ``receive``: goods arrived outside of an order."""
    item = store.receive(args.sku, args.qty, warehouse=args.warehouse,
                         actor=args.actor)
    store.save()
    print(f"received {args.qty} x {item.sku} into {args.warehouse}, "
          f"now {item.qty_in(args.warehouse)} there ({item.qty} in total)")
    return 0


def cmd_ship(store: Store, args) -> int:
    """Handle ``ship``: send units out of the stockroom."""
    item = store.ship(args.sku, args.qty, warehouse=args.warehouse,
                      date=args.date, actor=args.actor)
    store.save()
    print(f"shipped {args.qty} x {item.sku} from {args.warehouse}, "
          f"now {item.qty_in(args.warehouse)} there ({item.qty} in total)")
    return 0


def cmd_set_price(store: Store, args) -> int:
    """Handle ``set-price``: change an item's unit price."""
    item = store.set_price(args.sku, args.price, date=args.date,
                           actor=args.actor)
    store.save()
    print(f"{item.sku} now {format_money(item.unit_price)}")
    return 0


def cmd_transfer(store: Store, args) -> int:
    """Handle ``transfer``: walk stock from one warehouse to another."""
    item = store.transfer(args.sku, args.qty, args.src, args.dst,
                          actor=args.actor)
    store.save()
    print(f"transferred {args.qty} x {item.sku} from {args.src} "
          f"to {args.dst}")
    return 0


def cmd_place_order(store: Store, args) -> int:
    """Handle ``place-order``: record a pending purchase order."""
    date = args.date
    if date is None:
        date = datetime.date.today().isoformat()
    order = store.place_order(args.sku, args.qty, date,
                              supplier_id=args.supplier, actor=args.actor)
    store.save()
    print(f"placed order {order.id}: {order.qty} x {order.sku} on {order.date}")
    return 0


def cmd_receive_order(store: Store, args) -> int:
    """Handle ``receive-order``: an order arrived; stock it."""
    order = store.receive_order(args.id, actor=args.actor)
    store.save()
    print(f"order {order.id} received, {order.qty} x {order.sku} added to stock")
    return 0


def cmd_cancel_order(store: Store, args) -> int:
    """Handle ``cancel-order``: mark an order cancelled."""
    order = store.cancel_order(args.id, actor=args.actor)
    store.save()
    print(f"order {order.id} cancelled")
    return 0


def _print_stock_rows(rows) -> None:
    """Print the body of a stock listing (no header, no total)."""
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6} "
              f"{format_money(row['unit_price']):>10} "
              f"{format_money(row['value']):>10}")


def cmd_ship_order(store: Store, args) -> int:
    """Handle ``ship-order``: book a partial delivery of an order."""
    order = store.ship_order(args.id, args.qty, actor=args.actor)
    store.save()
    print(f"delivered {args.qty} x {order.sku} against order {order.id}; "
          f"{order.shipped_qty}/{order.qty} received, order is {order.status}")
    return 0


def cmd_catalog_add(store: Store, args) -> int:
    """Handle ``catalog-add``: record that a supplier stocks a SKU."""
    store.add_supplier_sku(args.supplier, args.sku)
    store.save()
    print(f"{args.supplier} can supply {args.sku.upper()}")
    return 0


def cmd_catalog_list(store: Store, args) -> int:
    """Handle ``catalog-list``: print one supplier's catalogue."""
    for sku in store.supplier_skus(args.supplier):
        print(sku)
    return 0


def cmd_backup(store: Store, args) -> int:
    """Handle ``backup``: snapshot the state file."""
    print(store.backup())
    return 0


def cmd_list_backups(store: Store, args) -> int:
    """Handle ``list-backups``: print the snapshots we hold, oldest first."""
    for name in store.list_backups():
        print(name)
    return 0


def cmd_restore(store: Store, args) -> int:
    """Handle ``restore``: put a snapshot back."""
    store.restore(args.name)
    store.save()
    print(f"restored {args.name}")
    return 0


def cmd_report_stock(store: Store, args) -> int:
    """Handle ``report stock``: print the full stock listing."""
    header = f"{'SKU':<12} {'NAME':<24} {'QTY':>6} {'PRICE':>10} {'VALUE':>10}"
    if args.warehouse:
        print(f"warehouse: {args.warehouse}")
    if args.by_category:
        report = reports.stock_report(store, by_category=True,
                                      warehouse=args.warehouse)
        for category in sorted(report["categories"]):
            print(category)
            print(header)
            _print_stock_rows(report["categories"][category])
            print()
    else:
        report = reports.stock_report(store, warehouse=args.warehouse)
        print(header)
        _print_stock_rows(report["rows"])
    print(f"Total value: {format_money(report['total_value'])}")
    return 0


def _print_low_rows(rows) -> None:
    """Print the body of a low-stock listing."""
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6}")


def cmd_report_low(store: Store, args) -> int:
    """Handle ``report low``: print items running low, plus
    reorder suggestions for the ones we can actually reorder."""
    if args.by_category:
        grouped = reports.low_stock_by_category(store, threshold=args.threshold)
        if not grouped:
            print("no items at or below threshold")
            return 0
        for category in sorted(grouped):
            print(category)
            _print_low_rows(grouped[category])
            print()
        return 0
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
                  f"from {row['supplier_id']}")
    return 0


def cmd_report_price_changes(store: Store, args) -> int:
    """Handle ``report price-changes``: every recorded price change."""
    for row in reports.price_changes(store):
        print(f"{row['date']:<12} {row['sku']:<12} "
              f"{format_money(row['old'])} -> {format_money(row['new'])}")
    return 0


def cmd_report_turnover(store: Store, args) -> int:
    """Handle ``report turnover``: units shipped per category per month."""
    report = reports.turnover(store)
    for category in sorted(report):
        for month in sorted(report[category]):
            print(f"{category:<16} {month}  {report[category][month]:>6}")
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
    """Handle ``search``: print items matching a query."""
    for row in reports.search_items(store, args.query):
        print(f"{row['sku']:<12} {row['name']}")
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


# ----------------------------------------------------------------------
# argument parsing
# ----------------------------------------------------------------------

EXAMPLES = """\
examples:
  stockroom --data ./data add-supplier acme "Acme Supply" orders@acme.example
  stockroom --data ./data add-item WID-1 "Widget" --qty 10 --price 19.99 --supplier acme
  stockroom --data ./data ship WID-1 3
  stockroom --data ./data place-order WID-1 20 --date 2026-07-01
  stockroom --data ./data receive-order 1
  stockroom --data ./data report stock
  stockroom --data ./data report monthly 2026-07
  stockroom --data ./data export-csv items.csv
"""


# Commands that change state; each of these takes --actor.
MUTATING_COMMANDS = [
    "add-item", "add-supplier", "receive", "ship", "place-order",
    "receive-order", "cancel-order", "import-csv", "transfer", "ship-order",
    "catalog-add", "restore", "set-price",
]


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
    p.add_argument("--category", default=None,
                   help="shelf area (default: uncategorized)")
    p.set_defaults(func=cmd_add_item)

    p = sub.add_parser("add-supplier", help="create a new supplier")
    p.add_argument("id")
    p.add_argument("name")
    p.add_argument("email")
    p.add_argument("--lead-time", type=int, default=0,
                   help="typical delivery time in whole days")
    p.set_defaults(func=cmd_add_supplier)

    p = sub.add_parser("receive", help="add units of an item to stock")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("--warehouse", default=MAIN_WAREHOUSE)
    p.set_defaults(func=cmd_receive)

    p = sub.add_parser("ship", help="remove units of an item from stock")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("--warehouse", default=MAIN_WAREHOUSE)
    p.add_argument("--date", default=None,
                   help="shipment date (default: today)")
    p.set_defaults(func=cmd_ship)

    p = sub.add_parser("set-price", help="change an item's unit price")
    p.add_argument("sku")
    p.add_argument("price", type=float)
    p.add_argument("--date", default=None,
                   help="date of the change (default: today)")
    p.set_defaults(func=cmd_set_price)

    p = sub.add_parser("transfer", help="move stock between warehouses")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("src", help="warehouse to take the stock from")
    p.add_argument("dst", help="warehouse to move the stock to")
    p.set_defaults(func=cmd_transfer)

    p = sub.add_parser("place-order", help="record a purchase order")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("--date", default=None,
                   help="order date (default: today)")
    p.add_argument("--supplier", default=None,
                   help="who to order from (default: worked out from "
                        "the supplier catalogues)")
    p.set_defaults(func=cmd_place_order)

    p = sub.add_parser("receive-order",
                       help="mark an order received and stock the goods")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_receive_order)

    p = sub.add_parser("cancel-order", help="cancel an order")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_cancel_order)

    p = sub.add_parser("ship-order", help="book a partial delivery")
    p.add_argument("id", type=int)
    p.add_argument("--qty", type=int, required=True,
                   help="units delivered now")
    p.set_defaults(func=cmd_ship_order)

    p = sub.add_parser("catalog-add", help="record a SKU a supplier stocks")
    p.add_argument("supplier")
    p.add_argument("sku")
    p.set_defaults(func=cmd_catalog_add)

    p = sub.add_parser("catalog-list", help="list a supplier's SKUs")
    p.add_argument("supplier")
    p.set_defaults(func=cmd_catalog_list)

    p = sub.add_parser("backup", help="snapshot the current state")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("list-backups", help="list snapshots, oldest first")
    p.set_defaults(func=cmd_list_backups)

    p = sub.add_parser("restore", help="restore a snapshot by name")
    p.add_argument("name")
    p.set_defaults(func=cmd_restore)

    report = sub.add_parser("report", help="print a report")
    report_sub = report.add_subparsers(dest="report_kind", required=True)

    p = report_sub.add_parser("stock", help="full stock listing with values")
    p.add_argument("--by-category", action="store_true",
                   help="group the listing by shelf area")
    p.add_argument("--warehouse", default=None,
                   help="show only what one warehouse holds")
    p.set_defaults(func=cmd_report_stock)

    p = report_sub.add_parser("low", help="items running low")
    p.add_argument("--threshold", type=int, default=reports.DEFAULT_THRESHOLD)
    p.add_argument("--by-category", action="store_true",
                   help="group the listing by shelf area")
    p.set_defaults(func=cmd_report_low)

    p = report_sub.add_parser("price-changes",
                              help="every recorded price change")
    p.set_defaults(func=cmd_report_price_changes)

    p = report_sub.add_parser("turnover",
                              help="units shipped per category per month")
    p.set_defaults(func=cmd_report_turnover)

    p = report_sub.add_parser("monthly", help="orders placed in a month")
    p.add_argument("month", help="month prefix, e.g. 2026-01")
    p.set_defaults(func=cmd_report_monthly)

    p = report_sub.add_parser("history", help="order history for one SKU")
    p.add_argument("sku")
    p.set_defaults(func=cmd_report_history)

    p = sub.add_parser("search", help="find items by name or SKU")
    p.add_argument("query")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("export-csv", help="write items to a CSV file")
    p.add_argument("path")
    p.set_defaults(func=cmd_export_csv)

    p = sub.add_parser("import-csv", help="read items from a CSV file")
    p.add_argument("path")
    p.set_defaults(func=cmd_import_csv)

    # Every command that changes state can say who ran it.
    for name in MUTATING_COMMANDS:
        sub.choices[name].add_argument("--actor", default=None,
                                       help="who is running this command")

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
